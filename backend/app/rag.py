from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from openai import OpenAIError

from app.errors import ModelError
from app.schemas import QueryResponse, RetrievedDocument
from app.store import DocumentStore, ScoredChunk

SYSTEM_PROMPT = (
    "You are a transit operations assistant for Optibus. "
    "Answer the question using only the retrieved passages. "
    "If the passages do not contain the answer, say that the documents do not cover it. "
    "Mention concrete details such as route numbers, vehicles, times, and constraints "
    "when they are present. Refer to supporting passages by document id. "
    "Write plain prose in a few sentences. Do not use markdown headings or bullet lists."
)

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "Question:\n{question}\n\nRetrieved passages:\n{context}"),
    ]
)


class RagService:
    def __init__(self, store: DocumentStore, chat_model: BaseChatModel, top_k: int) -> None:
        self.store = store
        self.chain = PROMPT | chat_model | StrOutputParser()
        self.top_k = top_k

    def query(self, question: str, k: int | None = None) -> QueryResponse:
        try:
            hits = self.store.search(question, k or self.top_k)
            answer = self.chain.invoke(
                {"question": question, "context": format_context(hits)}
            ).strip()
        except OpenAIError as exc:
            raise ModelError("OpenAI request failed. Check OPENAI_API_KEY and try again.") from exc
        if not answer:
            raise ModelError("The model returned an empty answer")
        return QueryResponse(
            retrieved_docs=[
                RetrievedDocument(
                    id=hit.chunk.doc_id,
                    module=hit.chunk.module,
                    text=hit.chunk.text,
                    score=hit.score,
                )
                for hit in hits
            ],
            answer=answer,
        )


def format_context(hits: list[ScoredChunk]) -> str:
    if not hits:
        return "(no passages)"
    return "\n\n".join(
        f"[{hit.chunk.doc_id} | {hit.chunk.module} | similarity {hit.score:.2f}]\n{hit.chunk.text}"
        for hit in hits
    )

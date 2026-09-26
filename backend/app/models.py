from __future__ import annotations

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import Settings


def build_embeddings(settings: Settings) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        dimensions=settings.embedding_dimensions,
        api_key=settings.openai_api_key,
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )


def build_chat_model(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.openai_chat_model,
        api_key=settings.openai_api_key,
        temperature=0.2,
        max_tokens=600,
        timeout=settings.openai_timeout_seconds,
        max_retries=settings.openai_max_retries,
    )

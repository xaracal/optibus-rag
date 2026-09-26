from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SourceFormat = Literal["text", "markdown"]


class Document(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.\-]+$")
    module: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1)


class SourceDocument(Document):
    """A document as loaded for ingest, including how its text should be split."""

    format: SourceFormat = "text"


class RetrievedDocument(Document):
    score: float


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    k: int | None = Field(default=None, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be blank")
        return stripped


class QueryResponse(BaseModel):
    retrieved_docs: list[RetrievedDocument]
    answer: str


class ReadyResponse(BaseModel):
    ready: bool
    documents: int
    detail: str | None = None

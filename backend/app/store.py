from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from langchain_core.embeddings import Embeddings
from langchain_redis import RedisConfig, RedisVectorStore
from redis import Redis
from redis.exceptions import RedisError

from app.config import Settings
from app.errors import StoreUnavailableError
from app.schemas import Document

DOCUMENT_PREFIX = "doc"
CHUNK_PREFIX = "chunk"
CATALOG_KEY = "doc:ids"


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    module: str
    index: int
    text: str

    @property
    def key(self) -> str:
        return f"{self.doc_id}:{self.index}"


@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk
    score: float


def connect_redis(settings: Settings) -> Redis:
    return Redis.from_url(
        settings.redis_url,
        socket_timeout=settings.redis_timeout_seconds,
        socket_connect_timeout=settings.redis_timeout_seconds,
        retry_on_timeout=True,
        health_check_interval=30,
    )


class DocumentStore:
    """Chunks and vectors live in the LangChain vector index; source documents in a catalog."""

    def __init__(self, redis: Redis, embeddings: Embeddings, settings: Settings) -> None:
        self.redis = redis
        self.settings = settings
        self.vectors = RedisVectorStore(
            embeddings,
            config=RedisConfig(
                index_name=settings.index_name,
                key_prefix=CHUNK_PREFIX,
                legacy_key_format=False,
                redis_client=redis,
                storage_type="hash",
                distance_metric="COSINE",
                indexing_algorithm="HNSW",
                embedding_dimensions=settings.embedding_dimensions,
                metadata_schema=[
                    {"name": "doc_id", "type": "tag"},
                    {"name": "module", "type": "tag"},
                    {"name": "chunk", "type": "numeric"},
                ],
            ),
        )

    def ping(self) -> None:
        try:
            self.redis.ping()
        except RedisError as exc:
            raise StoreUnavailableError("Redis is not reachable") from exc

    def count_documents(self) -> int:
        try:
            return int(self.redis.zcard(CATALOG_KEY))
        except RedisError as exc:
            raise StoreUnavailableError("Redis is not reachable") from exc

    def list_documents(self, offset: int, limit: int) -> list[Document]:
        try:
            ids = [
                _decode(value)
                for value in self.redis.zrange(CATALOG_KEY, offset, offset + limit - 1)
            ]
            pipe = self.redis.pipeline()
            for doc_id in ids:
                pipe.hmget(_document_key(doc_id), "id", "module", "text")
            rows = pipe.execute()
        except RedisError as exc:
            raise StoreUnavailableError("Redis is not reachable") from exc
        return [
            Document(id=_decode(row[0]), module=_decode(row[1]), text=_decode(row[2]))
            for row in rows
            if row and row[0] is not None
        ]

    def list_ids(self) -> list[str]:
        return [_decode(value) for value in self.redis.zrange(CATALOG_KEY, 0, -1)]

    def fingerprint(self, doc_id: str) -> tuple[str | None, int]:
        stored_hash, chunks = self.redis.hmget(_document_key(doc_id), "content_hash", "chunks")
        return (_decode(stored_hash) if stored_hash else None, int(chunks or 0))

    def upsert(self, document: Document, chunks: list[Chunk], content_hash: str) -> None:
        _, previous_chunks = self.fingerprint(document.id)
        self.vectors.add_texts(
            [chunk.text for chunk in chunks],
            metadatas=[
                {"doc_id": chunk.doc_id, "module": chunk.module, "chunk": chunk.index}
                for chunk in chunks
            ],
            keys=[chunk.key for chunk in chunks],
        )
        stale = [f"{document.id}:{index}" for index in range(len(chunks), previous_chunks)]
        if stale:
            self.vectors.delete(stale)
        pipe = self.redis.pipeline()
        pipe.hset(
            _document_key(document.id),
            mapping={
                "id": document.id,
                "module": document.module,
                "text": document.text,
                "content_hash": content_hash,
                "chunks": len(chunks),
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )
        pipe.zadd(CATALOG_KEY, {document.id: 0})
        pipe.execute()

    def remove(self, doc_id: str) -> None:
        _, chunks = self.fingerprint(doc_id)
        if chunks:
            self.vectors.delete([f"{doc_id}:{index}" for index in range(chunks)])
        pipe = self.redis.pipeline()
        pipe.delete(_document_key(doc_id))
        pipe.zrem(CATALOG_KEY, doc_id)
        pipe.execute()

    def search(self, query: str, k: int) -> list[ScoredChunk]:
        try:
            results = self.vectors.similarity_search_with_score(query, k=k)
        except RedisError as exc:
            raise StoreUnavailableError("Redis is not reachable") from exc
        hits = []
        for document, distance in results:
            metadata = document.metadata
            hits.append(
                ScoredChunk(
                    chunk=Chunk(
                        doc_id=str(metadata["doc_id"]),
                        module=str(metadata["module"]),
                        index=int(metadata.get("chunk", 0)),
                        text=document.page_content,
                    ),
                    score=round(1.0 - float(distance), 4),
                )
            )
        return hits


def content_hash(document: Document, settings: Settings, source_format: str = "text") -> str:
    payload = json.dumps(
        {
            "module": document.module,
            "text": document.text,
            "format": source_format,
            "model": settings.openai_embedding_model,
            "dimensions": settings.embedding_dimensions,
            "chunk_size": settings.chunk_size_tokens,
            "chunk_overlap": settings.chunk_overlap_tokens,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _document_key(doc_id: str) -> str:
    return f"{DOCUMENT_PREFIX}:{doc_id}"


def _decode(value: bytes | str) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else value

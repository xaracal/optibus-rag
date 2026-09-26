from __future__ import annotations

import math
import os
import re
import uuid
from collections.abc import Iterator

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

import pytest
from langchain_core.embeddings import Embeddings
from redis import Redis
from testcontainers.community.redis import RedisContainer

from app.config import Settings
from app.store import DocumentStore

REDIS_IMAGE = os.environ.get("TEST_REDIS_IMAGE", "redis:8.0.2-alpine")

VOCABULARY = [
    "route",
    "driver",
    "shift",
    "rest",
    "break",
    "bus",
    "brake",
    "maintenance",
    "fuel",
    "marathon",
    "downtown",
    "airport",
    "express",
    "weekend",
    "night",
    "morning",
    "peak",
    "depot",
    "roster",
    "overcrowding",
    "delay",
    "stadium",
    "articulated",
    "labor",
]
DIMENSIONS = len(VOCABULARY)


class KeywordEmbeddings(Embeddings):
    """Bag-of-words vectors over a fixed vocabulary, so similar texts really rank together."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    @staticmethod
    def _vector(text: str) -> list[float]:
        words = re.findall(r"[a-z]+", text.lower())
        vector = [float(sum(word.startswith(term) for word in words)) for term in VOCABULARY]
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return [1.0 / math.sqrt(DIMENSIONS)] * DIMENSIONS
        return [value / norm for value in vector]


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    with RedisContainer(REDIS_IMAGE) as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


@pytest.fixture
def settings(redis_url: str) -> Settings:
    return Settings(
        _env_file=None,
        openai_api_key="test-key",
        redis_url=redis_url,
        index_name=f"test-{uuid.uuid4().hex[:8]}",
        embedding_dimensions=DIMENSIONS,
        chunk_size_tokens=60,
        chunk_overlap_tokens=10,
    )


@pytest.fixture
def redis_client(settings: Settings) -> Iterator[Redis]:
    client = Redis.from_url(settings.redis_url)
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


@pytest.fixture
def embeddings() -> KeywordEmbeddings:
    return KeywordEmbeddings()


@pytest.fixture
def store(redis_client: Redis, embeddings: KeywordEmbeddings, settings: Settings) -> DocumentStore:
    return DocumentStore(redis_client, embeddings, settings)

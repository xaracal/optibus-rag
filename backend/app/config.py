from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"
    embedding_dimensions: int = Field(default=1536, ge=1)
    openai_timeout_seconds: float = Field(default=30.0, gt=0)
    openai_max_retries: int = Field(default=3, ge=0)

    redis_url: str = "redis://localhost:6379/0"
    redis_timeout_seconds: float = Field(default=5.0, gt=0)
    index_name: str = "optibus-chunks"

    top_k: int = Field(default=5, ge=1, le=10)
    chunk_size_tokens: int = Field(default=400, ge=50)
    chunk_overlap_tokens: int = Field(default=50, ge=0)

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()

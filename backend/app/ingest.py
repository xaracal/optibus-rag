from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from langchain_text_splitters import Language, RecursiveCharacterTextSplitter
from openai import OpenAIError
from redis.exceptions import RedisError

from app.config import Settings, get_settings
from app.dataset import load_dataset
from app.errors import DatasetError
from app.models import build_embeddings
from app.schemas import Document, SourceDocument, SourceFormat
from app.store import Chunk, DocumentStore, connect_redis, content_hash

logger = logging.getLogger("app.ingest")


@dataclass
class IngestReport:
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    chunks: int = 0


def build_splitters(settings: Settings) -> dict[SourceFormat, RecursiveCharacterTextSplitter]:
    sizing = {
        "encoding_name": "cl100k_base",
        "chunk_size": settings.chunk_size_tokens,
        "chunk_overlap": settings.chunk_overlap_tokens,
    }
    return {
        "text": RecursiveCharacterTextSplitter.from_tiktoken_encoder(**sizing),
        "markdown": RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            separators=RecursiveCharacterTextSplitter.get_separators_for_language(
                Language.MARKDOWN
            ),
            is_separator_regex=True,
            **sizing,
        ),
    }


def ingest(
    documents: list[Document],
    store: DocumentStore,
    settings: Settings,
    *,
    prune: bool = False,
) -> IngestReport:
    splitters = build_splitters(settings)
    report = IngestReport()
    for document in documents:
        source_format = document.format if isinstance(document, SourceDocument) else "text"
        digest = content_hash(document, settings, source_format)
        stored_hash, _ = store.fingerprint(document.id)
        if stored_hash == digest:
            report.unchanged += 1
            continue
        texts = splitters[source_format].split_text(document.text) or [document.text]
        chunks = [
            Chunk(doc_id=document.id, module=document.module, index=index, text=text)
            for index, text in enumerate(texts)
        ]
        store.upsert(document, chunks, digest)
        report.chunks += len(chunks)
        if stored_hash is None:
            report.added += 1
        else:
            report.updated += 1

    if prune:
        wanted = {document.id for document in documents}
        for doc_id in store.list_ids():
            if doc_id not in wanted:
                store.remove(doc_id)
                report.removed += 1
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Embed documents into the Redis vector index.")
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="A JSON array file, a Markdown file, or a folder of Markdown files",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete indexed documents that are not in the source",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    settings = get_settings()
    if not settings.openai_api_key:
        logger.error("OPENAI_API_KEY is not set. Add it to .env before running ingest.")
        return 2
    try:
        documents = load_dataset(args.source)
        store = DocumentStore(connect_redis(settings), build_embeddings(settings), settings)
        report = ingest(documents, store, settings, prune=args.prune)
    except DatasetError as exc:
        logger.error("%s", exc)
        return 2
    except RedisError as exc:
        logger.error("Redis error at %s: %s", settings.redis_url, exc)
        return 1
    except OpenAIError as exc:
        logger.error("OpenAI embedding request failed: %s", exc)
        return 1

    logger.info(
        "Ingested %s documents: %s added, %s updated, %s unchanged, %s removed, %s chunks embedded",
        len(documents),
        report.added,
        report.updated,
        report.unchanged,
        report.removed,
        report.chunks,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Check that retrieval returns the expected documents for known questions.

Runs against the live Redis index with real OpenAI embeddings. Exits with 1 if any
question misses an expected document within the top k.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from app.config import get_settings
from app.models import build_embeddings
from app.store import DocumentStore, connect_redis

CASES = Path(__file__).with_name("retrieval_cases.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--k", type=int, default=None, help="Defaults to TOP_K")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)

    settings = get_settings()
    if not settings.openai_api_key:
        print("OPENAI_API_KEY is not set.", file=sys.stderr)
        return 2
    k = args.k or settings.top_k
    store = DocumentStore(connect_redis(settings), build_embeddings(settings), settings)
    if store.count_documents() == 0:
        print("No documents are indexed. Run the ingest command first.", file=sys.stderr)
        return 2

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    missed = 0
    for case in cases:
        expected = set(case["expected"])
        ranked = [hit.chunk.doc_id for hit in store.search(case["question"], k=k)]
        missing = sorted(expected - set(ranked))
        missed += bool(missing)
        status = f"MISS {', '.join(missing)}" if missing else "ok"
        print(f"{status:<22} {case['question']}")
        print(f"{'':<22} top {k}: {', '.join(ranked)}")

    print(f"\n{len(cases) - missed}/{len(cases)} questions retrieved every expected document")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())

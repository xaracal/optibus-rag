from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.errors import DatasetError
from app.schemas import Document, SourceDocument


def load_dataset(source: Path) -> list[SourceDocument]:
    """Load a JSON array file or a folder of Markdown files into validated documents."""
    if source.is_dir():
        documents = _load_markdown_folder(source)
    elif source.is_file() and source.suffix.lower() == ".json":
        documents = _load_json(source)
    elif source.is_file() and source.suffix.lower() == ".md":
        documents = [_load_markdown_file(source)]
    else:
        raise DatasetError(f"Unsupported or missing dataset source: {source}")

    seen: set[str] = set()
    for document in documents:
        if document.id in seen:
            raise DatasetError(f"Duplicate document id: {document.id}")
        seen.add(document.id)
    return documents


def _load_json(path: Path) -> list[SourceDocument]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, list):
        raise DatasetError(f"{path} must contain a JSON array of documents")
    try:
        documents = TypeAdapter(list[Document]).validate_python(raw)
    except ValidationError as exc:
        raise DatasetError(f"{path} failed validation:\n{exc}") from exc
    return [SourceDocument(**document.model_dump(), format="text") for document in documents]


def _load_markdown_folder(folder: Path) -> list[SourceDocument]:
    files = sorted(folder.rglob("*.md"))
    if not files:
        raise DatasetError(f"No Markdown files found in {folder}")
    return [_load_markdown_file(path) for path in files]


def _load_markdown_file(path: Path) -> SourceDocument:
    header, body = _split_front_matter(path.read_text(encoding="utf-8"))
    fields = {
        "id": header.get("id") or path.stem,
        "module": header.get("module") or path.parent.name,
        "text": body,
        "format": "markdown",
    }
    try:
        return SourceDocument.model_validate(fields)
    except ValidationError as exc:
        raise DatasetError(f"{path} failed validation:\n{exc}") from exc


def _split_front_matter(content: str) -> tuple[dict[str, str], str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, content
    for end, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            header: dict[str, str] = {}
            for entry in lines[1:end]:
                key, separator, value = entry.partition(":")
                if separator:
                    header[key.strip().lower()] = value.strip().strip("\"'")
            return header, "\n".join(lines[end + 1 :])
    return {}, content

import json
from pathlib import Path

import pytest

from app.dataset import load_dataset
from app.errors import DatasetError

SAMPLE = Path(__file__).resolve().parents[1] / "dataset" / "documents.json"


def test_sample_dataset_loads():
    documents = load_dataset(SAMPLE)
    assert len(documents) == 15
    assert {document.module for document in documents} == {"Planning", "Scheduling", "OPS"}


def test_duplicate_ids_are_rejected(tmp_path: Path):
    path = tmp_path / "documents.json"
    path.write_text(
        json.dumps(
            [
                {"id": "a", "module": "Planning", "text": "one"},
                {"id": "a", "module": "OPS", "text": "two"},
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(DatasetError, match="Duplicate document id"):
        load_dataset(path)


def test_invalid_record_is_rejected(tmp_path: Path):
    path = tmp_path / "documents.json"
    path.write_text(json.dumps([{"id": "a", "module": "Planning"}]), encoding="utf-8")
    with pytest.raises(DatasetError, match="failed validation"):
        load_dataset(path)


def test_markdown_folder_uses_front_matter_and_falls_back_to_paths(tmp_path: Path):
    ops = tmp_path / "OPS"
    ops.mkdir()
    (ops / "ops_9.md").write_text("Bus 99 needs new tyres.\n", encoding="utf-8")
    (tmp_path / "shift.md").write_text(
        "---\nid: scheduling_9\nmodule: Scheduling\n---\nShift B starts at 06:00.\n",
        encoding="utf-8",
    )
    documents = {document.id: document for document in load_dataset(tmp_path)}
    assert documents["ops_9"].module == "OPS"
    assert documents["ops_9"].text == "Bus 99 needs new tyres."
    assert documents["scheduling_9"].module == "Scheduling"
    assert documents["scheduling_9"].text == "Shift B starts at 06:00."


def test_missing_source_is_rejected(tmp_path: Path):
    with pytest.raises(DatasetError, match="Unsupported or missing"):
        load_dataset(tmp_path / "missing.json")

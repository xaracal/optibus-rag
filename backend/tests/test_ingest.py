from pathlib import Path

from app.dataset import load_dataset
from app.ingest import build_splitters, ingest
from app.schemas import Document

SAMPLE = Path(__file__).resolve().parents[1] / "dataset" / "documents.json"


def test_ingest_indexes_the_sample_and_retrieves_relevant_chunks(store, settings):
    documents = load_dataset(SAMPLE)
    report = ingest(documents, store, settings)
    assert report.added == 15
    assert store.count_documents() == 15

    hits = store.search("rest break rules for driver shifts", k=3)
    assert hits[0].chunk.doc_id == "scheduling_1"
    assert all(-1.0 <= hit.score <= 1.0 for hit in hits)


def test_reingest_skips_unchanged_and_reembeds_changed(store, settings, embeddings):
    documents = [
        Document(id="a", module="OPS", text="Bus 1 brake maintenance."),
        Document(id="b", module="OPS", text="Fuel delivery on Friday."),
    ]
    ingest(documents, store, settings)
    assert len(embeddings.calls) == 2

    report = ingest(documents, store, settings)
    assert report.unchanged == 2
    assert len(embeddings.calls) == 2

    changed = [
        documents[0],
        Document(id="b", module="OPS", text="Fuel delivery moved to Thursday."),
    ]
    report = ingest(changed, store, settings)
    assert (report.updated, report.unchanged) == (1, 1)
    assert embeddings.calls[-1] == ["Fuel delivery moved to Thursday."]


def test_long_documents_are_split_and_shrinking_removes_stale_chunks(store, settings, redis_client):
    long_text = " ".join(
        f"Sentence {index} describes route {index} and its morning peak demand."
        for index in range(40)
    )
    ingest([Document(id="long", module="Planning", text=long_text)], store, settings)
    _, chunks = store.fingerprint("long")
    assert chunks > 1
    assert len(redis_client.keys("chunk:long:*")) == chunks

    ingest([Document(id="long", module="Planning", text="Now short.")], store, settings)
    assert store.fingerprint("long")[1] == 1
    assert redis_client.keys("chunk:long:*") == [b"chunk:long:0"]


def test_markdown_documents_are_split_at_headings(store, settings, redis_client, tmp_path):
    sections = {
        "## Morning shifts": "Driver shift A starts at 05:45 and covers two morning trips on "
        "Route 5, with a 30-minute rest break after the first trip at the central depot.",
        "## Night shifts": "Night shifts must follow labor agreements that limit continuous "
        "driving to six hours, followed by a mandatory break before the next block starts.",
        "## Rosters": "The next bid period roster should balance weekly hours across drivers "
        "and keep split shifts to a minimum wherever the timetable allows it.",
    }
    body = "\n\n".join(f"{heading}\n\n{text}" for heading, text in sections.items())
    (tmp_path / "policy.md").write_text(
        f"---\nid: shift_policy\nmodule: Scheduling\n---\n# Shift policy\n\n{body}\n",
        encoding="utf-8",
    )
    documents = load_dataset(tmp_path)
    assert documents[0].format == "markdown"

    ingest(documents, store, settings)
    _, count = store.fingerprint("shift_policy")
    texts = [
        redis_client.hget(f"chunk:shift_policy:{index}", "text").decode() for index in range(count)
    ]
    assert count > 1
    for text in texts:
        assert text.startswith("#")
        assert not text.splitlines()[-1].startswith("#")
    assert all(heading in "\n".join(texts) for heading in sections)

    plain = build_splitters(settings)["text"].split_text(documents[0].text)
    assert any(chunk.splitlines()[-1].startswith("#") for chunk in plain)


def test_prune_removes_documents_missing_from_the_source(store, settings, redis_client):
    both = [
        Document(id="keep", module="OPS", text="Keep this."),
        Document(id="drop", module="OPS", text="Drop this."),
    ]
    ingest(both, store, settings)
    report = ingest(both[:1], store, settings, prune=True)
    assert report.removed == 1
    assert store.list_ids() == ["keep"]
    assert redis_client.keys("chunk:drop:*") == []
    assert redis_client.exists("doc:drop") == 0


def test_documents_page_in_stable_order(store, settings):
    documents = [
        Document(id=f"doc_{index:02d}", module="OPS", text=f"Note {index}") for index in range(7)
    ]
    ingest(documents, store, settings)
    first = store.list_documents(0, 3)
    rest = store.list_documents(3, 10)
    assert [document.id for document in first + rest] == [document.id for document in documents]

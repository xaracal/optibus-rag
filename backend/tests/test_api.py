from pathlib import Path

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.dataset import load_dataset
from app.ingest import ingest
from app.main import Services, create_app
from app.rag import RagService

SAMPLE = Path(__file__).resolve().parents[1] / "dataset" / "documents.json"
ANSWER = "Drivers on shift A get a 30-minute rest break after the first trip (scheduling_1)."


def _client(store, settings) -> TestClient:
    services = Services(
        store=store,
        rag=RagService(store, FakeListChatModel(responses=[ANSWER]), settings.top_k),
    )
    return TestClient(create_app(settings, services_factory=lambda _: services))


def test_documents_query_and_ready_contract(store, settings):
    ingest(load_dataset(SAMPLE), store, settings)
    with _client(store, settings) as client:
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json() == {"ready": True, "documents": 15, "detail": None}

        page = client.get("/documents", params={"limit": 10})
        assert page.status_code == 200
        assert page.headers["X-Total-Count"] == "15"
        assert len(page.json()) == 10
        assert set(page.json()[0]) == {"id", "module", "text"}

        response = client.post("/query", json={"query": "What rest break do drivers get?", "k": 2})
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"retrieved_docs", "answer"}
        assert body["answer"] == ANSWER
        assert len(body["retrieved_docs"]) == 2
        assert body["retrieved_docs"][0]["id"] == "scheduling_1"
        assert set(body["retrieved_docs"][0]) == {"id", "module", "text", "score"}


def test_query_before_ingest_returns_503(store, settings):
    with _client(store, settings) as client:
        assert client.get("/ready").status_code == 503
        response = client.post("/query", json={"query": "routes"})
        assert response.status_code == 503
        assert "ingest" in response.json()["detail"]


def test_missing_api_key_is_reported(settings):
    settings = settings.model_copy(update={"openai_api_key": ""})
    with TestClient(create_app(settings)) as client:
        response = client.get("/documents")
        assert response.status_code == 503
        assert "OPENAI_API_KEY" in response.json()["detail"]


def test_blank_query_is_rejected(store, settings):
    with _client(store, settings) as client:
        assert client.post("/query", json={"query": "   "}).status_code == 422

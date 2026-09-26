import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings
from app.errors import ModelError, StoreUnavailableError
from app.models import build_chat_model, build_embeddings
from app.rag import RagService
from app.schemas import Document, QueryRequest, QueryResponse, ReadyResponse
from app.store import DocumentStore, connect_redis

logger = logging.getLogger("app")


@dataclass
class Services:
    store: DocumentStore
    rag: RagService


def build_services(settings: Settings) -> Services:
    store = DocumentStore(connect_redis(settings), build_embeddings(settings), settings)
    return Services(store=store, rag=RagService(store, build_chat_model(settings), settings.top_k))


def get_services(request: Request) -> Services:
    current: Services | None = request.app.state.services
    if current is None:
        raise HTTPException(status_code=503, detail=request.app.state.startup_error)
    return current


ServicesDep = Annotated[Services, Depends(get_services)]


def create_app(
    settings: Settings | None = None,
    services_factory: Callable[[Settings], Services] = build_services,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.services = None
        app.state.startup_error = None
        if not settings.openai_api_key:
            app.state.startup_error = "OPENAI_API_KEY is not set. Add it to .env and restart."
        else:
            try:
                app.state.services = services_factory(settings)
            except Exception:
                logger.exception("Could not connect to Redis")
                app.state.startup_error = f"Could not connect to Redis at {settings.redis_url}."
        yield

    app = FastAPI(title="Optibus domain RAG", version="2.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=["X-Total-Count"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", response_model=ReadyResponse)
    def ready(request: Request, response: Response) -> ReadyResponse:
        current: Services | None = request.app.state.services
        if current is None:
            response.status_code = 503
            return ReadyResponse(ready=False, documents=0, detail=request.app.state.startup_error)
        try:
            current.store.ping()
            count = current.store.count_documents()
        except StoreUnavailableError as exc:
            response.status_code = 503
            return ReadyResponse(ready=False, documents=0, detail=str(exc))
        if count == 0:
            response.status_code = 503
            return ReadyResponse(
                ready=False, documents=0, detail="No documents are indexed. Run the ingest command."
            )
        return ReadyResponse(ready=True, documents=count)

    @app.get("/documents", response_model=list[Document])
    def list_documents(
        response: Response,
        current: ServicesDep,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=500)] = 100,
    ) -> list[Document]:
        try:
            response.headers["X-Total-Count"] = str(current.store.count_documents())
            return current.store.list_documents(offset, limit)
        except StoreUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/query", response_model=QueryResponse)
    def query(body: QueryRequest, current: ServicesDep) -> QueryResponse:
        try:
            if current.store.count_documents() == 0:
                raise HTTPException(
                    status_code=503, detail="No documents are indexed. Run the ingest command."
                )
            return current.rag.query(body.query, k=body.k)
        except StoreUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ModelError as exc:
            logger.exception("Model call failed")
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return app


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
app = create_app()

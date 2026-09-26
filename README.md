# Optibus domain RAG

A dashboard for querying Optibus-style planning, scheduling, and operations notes. Documents are embedded with OpenAI and stored in a Redis vector index. Each query retrieves the closest passages and asks OpenAI to answer from those passages only.

## Layout

- `frontend/` — React + TypeScript dashboard
- `backend/` — FastAPI service, ingest command, and tests
- `backend/dataset/documents.json` — the sample dataset, read only by the ingest command

## Run with Docker Compose

```bash
cp .env.example .env
# Put your OpenAI API key in .env
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000). The API is at [http://localhost:8000](http://localhost:8000). This is the supported way to run the dashboard locally.

Compose starts four services in order:

1. `redis` — Redis 8 with vector search, persisted to the `redis-data` volume.
2. `ingest` — embeds `backend/dataset/documents.json` into Redis, then exits.
3. `backend` — the API. It starts only after ingest succeeds.
4. `frontend` — the dashboard, served by nginx, which proxies `/api` to the backend.

Ingest needs `OPENAI_API_KEY`. Without it, ingest stops with an error and the API does not start.

## Updating the documents

Edit the dataset and run ingest again:

```bash
docker compose run --rm ingest
```

Ingest inserts or updates documents by `id` and only re-embeds documents whose text or module changed. `--prune`, which Compose passes by default, deletes indexed documents that are no longer in the source.

The source can be:

- a JSON array of `{ "id", "module", "text" }` objects;
- a folder of Markdown files, optionally with a header:

```markdown
---
id: ops_6
module: OPS
---
Bus 118 is out of service until Monday.
```

Without a header, the file name is the `id` and the folder name is the `module`.

To ingest a different source, mount it into the container and pass `--source`:

```bash
docker compose run --rm -v "$PWD/my-docs:/import:ro" ingest \
  python -m app.ingest --source /import --prune
```

## Frontend development

The React app can run on the host for UI work only. Redis, ingest, and the API stay in Docker Compose.

Start the stack first (`docker compose up --build`), then:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` to the Compose backend on port 8000.

## API

`GET /documents?offset=0&limit=100` returns a list of `{ id, module, text }`. The `X-Total-Count` header gives the total number of documents. `limit` can be at most 500.

`POST /query` accepts `{ "query": "...", "k": 5 }` and returns:

```json
{
  "retrieved_docs": [
    { "id": "scheduling_1", "module": "Scheduling", "text": "...", "score": 0.61 }
  ],
  "answer": "..."
}
```

`k` is optional. The default is `TOP_K` (5) and the maximum is 10. `score` is cosine similarity. Each retrieved item is one passage; long documents can contribute more than one.

`GET /health` confirms the process is up. `GET /ready` returns 200 only when Redis is reachable and documents are indexed. Otherwise it returns 503 with the reason.

## How it works

Ingest:

1. Load and validate the source. Duplicate ids and missing fields are rejected.
2. Hash each document together with the embedding and chunking settings. Documents whose hash matches the stored one are skipped.
3. Split each changed document with LangChain's `RecursiveCharacterTextSplitter`, measured in tokens (400 per passage, 50 overlap). Markdown files use LangChain's Markdown separators, so chunks break at headings, code fences, and horizontal rules before paragraphs. JSON records hold plain prose and use the default separators: paragraphs, lines, then words. The sample notes are short and stay whole.
4. Write the passages to LangChain's `RedisVectorStore`: an HNSW index with cosine distance, and `doc_id` and `module` as tag fields.
5. Record the document, its hash, and its passage count under `doc:{id}`, and add the id to a sorted set used for listing.

Query:

1. Embed the question and run a k-nearest-neighbour search in Redis.
2. Send the question and passages to the chat model through a LangChain prompt.
3. Return the passages and the answer.

Redis keys:

- `chunk:{id}:{n}` — one passage and its embedding.
- `doc:{id}` — the source document, hash, and passage count.
- `doc:ids` — sorted set of document ids for paginated listing.

## Tests and formatting

```bash
cd backend
pytest              # starts a throwaway Redis container, so Docker must be running
ruff format --check .
ruff check .
```

The tests use a real Redis and a keyword-based fake embedder. They do not call OpenAI.

## Retrieval check

`backend/evals/retrieval_cases.json` lists questions with the document ids that should be retrieved. The check runs them against the live index with real embeddings, and exits with 1 if any question misses an expected document within the top k.

```bash
cd backend
python -m evals.retrieval          # uses TOP_K
python -m evals.retrieval --k 6
```

It needs `OPENAI_API_KEY` and an ingested index. Redis from Compose is already on `localhost:6379`. Run it before and after changing embedding models, chunking, or retrieval settings, and add a case when you find a question that retrieves the wrong notes.

```bash
cd frontend
npm run format:check
npm run typecheck
```

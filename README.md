# ragkit

Document-centric RAG platform with a LangChain LCEL search pipeline, a FastAPI
REST server, a FastMCP adapter that exposes the same search to external AI
tools, and a React admin UI for day-to-day operations.

## Architecture

```
Admin UI (Vite + React)  ──REST+JWT──▶  FastAPI  ──▶  SQLite / Postgres
External AI tools  ──MCP──▶  ragkit-mcp (FastMCP, sibling repo)  ──REST──▶  FastAPI
FastAPI  ──▶  Qdrant (vectors) · upload dir · embedding provider
            (Ollama / TEI / vLLM / Azure OpenAI)
```

Top-level layout:

| Path      | Contents                                                |
| --------- | ------------------------------------------------------- |
| `server/` | FastAPI REST API, ingestion, embeddings, Qdrant, LCEL   |
| `admin/`  | Vite + React + TS admin SPA (login, documents, search)  |

The FastMCP adapter lives in a **separate repository**: clone `ragkit-mcp` next to this repo (sibling directory under the same parent) so MCP and the REST server can be versioned and deployed independently.

## Requirements

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm
- Docker (for Qdrant; optionally Postgres)
- [Ollama](https://ollama.com) running locally if you use the default embedding
  provider — pull the default model once with:
  ```bash
  ollama pull nomic-embed-text
  ```

## Quickstart

```bash
# 1. Start infra (Qdrant + Postgres)
docker compose up -d

# 2. Secrets
cp .env.example .env
# edit .env: set JWT_SECRET_KEY, pick INITIAL_ADMIN_PASSWORD, etc.

# 3. Server
cd server
uv sync
# Uses DATABASE_URL from env if set, otherwise sqlite at server/data/ragkit.db.
# Tables are created on first app startup from the ORM (no Alembic).
# `.env` is auto-loaded from `server/.env` and `../.env` when present.
uv run uvicorn app.main:app --reload --port 8000

# 4. MCP (separate shell — sibling repo `ragkit-mcp`)
cd ../ragkit-mcp
uv sync
export MCP_SERVICE_TOKEN=... RAGKIT_API_BASE=http://localhost:8000
uv run python server.py

# 5. Admin UI (separate shell)
cd admin
npm install
npm run dev
```

Open the admin UI at http://localhost:5173. The dev server proxies `/api/*` to
`http://localhost:8000` so no CORS setup is needed for development.

On first startup the server creates one user (email from
`server/config.yaml` → `admin_bootstrap.email`, default `admin@example.com`)
using `INITIAL_ADMIN_PASSWORD`. There is no multi-user admin UI; add more
accounts by inserting into the DB if you need them later.

## Configuration

`server/config.yaml` holds non-secret config:

- `server.upload_dir` — where uploaded files are stored (relative to `server/`)
- `db.url` — SQLite by default; overridden by `DATABASE_URL`
- `vectorstore` — Qdrant URL, collection, vector size, distance
- `embeddings.provider` — one of `ollama` (default), `tei`, `vllm`,
  `azure_openai`; each provider has its own sub-section
- `ingest.chunk_size` / `chunk_overlap` — splitter parameters
- `search.default_top_k` / `max_top_k`
- `jwt.algorithm` / `access_token_ttl_minutes`
- `admin_bootstrap.email` / `password_env`

Environment variables (from `.env`):

| Variable                  | Purpose                                                  |
| ------------------------- | -------------------------------------------------------- |
| `JWT_SECRET_KEY`          | Signs access tokens (required)                           |
| `DATABASE_URL`            | Overrides `db.url`                                       |
| `VECTORSTORE_API_KEY`     | Sent to Qdrant if the instance is secured                |
| `EMBEDDING_API_KEY`       | Sent to the embedding provider (TEI/vLLM/Azure OpenAI)   |
| `INITIAL_ADMIN_PASSWORD`  | Bootstraps the first (and only configured) user          |
| `MCP_SERVICE_TOKEN`       | Shared token so the MCP adapter can call the REST server |

## MCP tools

- `search_chunks(query, top_k?, document_id?)`
- `get_document(document_id)`
- `list_documents(limit?, offset?, q?)`

The adapter sends `X-Service-Token` when `MCP_SERVICE_TOKEN` is set; the REST
API also accepts a normal `Authorization: Bearer <JWT>` from `/auth/login`.

## Data and integrity

Each **document** has one stored file and a `status` (`pending` / `ready` /
`failed`). **Chunks** reference `document_id` and store the matching Qdrant
point id.

- **Upload**: file on disk → row updated → chunk + embed + Qdrant upsert →
  chunk rows + `status=ready`. On failure, inserted vectors are deleted and the
  row is marked `failed`.
- **Replace**: same as upload after clearing existing vectors + chunk rows.
- **Delete**: Qdrant vectors for that `document_id`, then the DB row (chunks
  cascade), then the upload folder.
- **Search**: LangChain LCEL — `query → embed → Qdrant → enrich` with optional
  `document_id` filter in the request body.

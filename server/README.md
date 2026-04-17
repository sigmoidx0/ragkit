# ragkit server

FastAPI REST server: JWT login, documents (one file each), search (LangChain
LCEL over Qdrant).

## Run

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Tables are created automatically from the SQLAlchemy models on startup (no
Alembic). If you change a model, drop the SQLite file or Postgres database and
restart.

**Docs:** http://localhost:8000/docs · **OpenAPI:** http://localhost:8000/openapi.json

Configuration lives in `config.yaml`; secrets are read from environment
variables. On startup, the server also auto-loads `.env` from `server/.env` and
`../.env` if present (shell-exported vars still take precedence).

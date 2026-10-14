"""LangGraph checkpointer — lifecycle managed via FastAPI lifespan.

Chat history lives in the same database as everything else, so the backend is
picked from `db.url`: SQLite for zero-setup local development, Postgres for a
deployed stack. Both savers share LangGraph's interface; nothing else in the
app knows which one is active.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.base import BaseCheckpointSaver

from app.core.config import get_settings
from app.core.paths import resolve_relative

_checkpointer: BaseCheckpointSaver | None = None

_SQLITE_PREFIX = "sqlite:///"


def get_checkpointer() -> BaseCheckpointSaver:
    if _checkpointer is None:
        raise RuntimeError("checkpointer not initialised — call checkpointer_lifespan in lifespan")
    return _checkpointer


def _sqlite_path(url: str) -> str:
    path = url[len(_SQLITE_PREFIX):]
    return path if path == ":memory:" else str(resolve_relative(path))


def _postgres_conninfo(url: str) -> str:
    """SQLAlchemy URL → libpq conninfo: drop the "+driver" part of the scheme."""
    scheme, rest = url.split("://", 1)
    return f"{scheme.split('+', 1)[0]}://{rest}"


@asynccontextmanager
async def checkpointer_lifespan() -> AsyncIterator[BaseCheckpointSaver]:
    global _checkpointer
    url = get_settings().db.url

    if url.startswith(_SQLITE_PREFIX):
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        saver_cm = AsyncSqliteSaver.from_conn_string(_sqlite_path(url))
    elif url.startswith("postgresql"):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        saver_cm = AsyncPostgresSaver.from_conn_string(_postgres_conninfo(url))
    else:
        raise ValueError(f"unsupported database for chat checkpoints: {url.split('://', 1)[0]}")

    async with saver_cm as saver:
        await saver.setup()
        _checkpointer = saver
        try:
            yield saver
        finally:
            _checkpointer = None

"""LangGraph SQLite checkpointer — lifecycle managed via FastAPI lifespan."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.core.config import get_settings
from app.core.paths import resolve_relative

_checkpointer: AsyncSqliteSaver | None = None


def get_checkpointer() -> AsyncSqliteSaver:
    if _checkpointer is None:
        raise RuntimeError("checkpointer not initialised — call checkpointer_lifespan in lifespan")
    return _checkpointer


def _db_path() -> str:
    url = get_settings().db.url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise ValueError(f"langgraph checkpoint requires SQLite DB, got: {url!r}")
    path = url[len(prefix):]
    if path == ":memory:":
        return path
    return str(resolve_relative(path))


@asynccontextmanager
async def checkpointer_lifespan() -> AsyncIterator[AsyncSqliteSaver]:
    global _checkpointer
    async with AsyncSqliteSaver.from_conn_string(_db_path()) as saver:
        await saver.setup()
        _checkpointer = saver
        try:
            yield saver
        finally:
            _checkpointer = None

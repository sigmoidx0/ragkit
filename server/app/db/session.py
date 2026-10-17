"""SQLAlchemy engine and session factory."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.paths import resolve_relative


def _make_engine():
    settings = get_settings()
    url = settings.db.url

    connect_args: dict = {}
    if url.startswith("sqlite"):
        # Ensure the parent directory exists for file-based sqlite
        prefix = "sqlite:///"
        if url.startswith(prefix):
            db_path = url[len(prefix):]
            if db_path and db_path != ":memory:":
                resolved = resolve_relative(db_path)
                Path(resolved).parent.mkdir(parents=True, exist_ok=True)
                url = f"{prefix}{resolved}"
        connect_args["check_same_thread"] = False

    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True, future=True)
    if url.startswith("sqlite"):
        # SQLite ignores foreign keys unless asked, per connection — so every
        # ON DELETE CASCADE in the schema was a no-op and deleting a chat left
        # its sources and ratings behind. Alembic uses its own engine, which
        # keeps them off: table rebuilds in migrations must not cascade.
        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(dbapi_conn, _record) -> None:
            dbapi_conn.execute("PRAGMA foreign_keys = ON")

    return engine


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def create_tables() -> None:
    """Create all tables from ORM metadata (greenfield; no migration history).

    Schema changes are not applied to existing tables — drop the DB file or
    database and restart when models change.
    """
    from app.db import models  # noqa: F401 — register tables on Base.metadata
    from app.db.base import Base

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

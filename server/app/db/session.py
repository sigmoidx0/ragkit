"""SQLAlchemy engine and session factory."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
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

    return create_engine(url, connect_args=connect_args, pool_pre_ping=True, future=True)


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

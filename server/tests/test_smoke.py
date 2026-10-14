"""Minimal import smoke test."""

from __future__ import annotations


def test_app_imports() -> None:
    from app.main import app

    assert app.title == "ragkit"
    routes = {r.path for r in app.routes}
    assert "/health" in routes
    assert "/auth/login" in routes
    assert "/services/{service_id}/search" in routes
    assert "/services/{service_id}/documents" in routes


def test_config_loads() -> None:
    from app.core.config import get_settings

    s = get_settings()
    assert s.embeddings.provider in {"ollama", "tei", "vllm", "azure_openai"}
    assert s.ingest.chunk_size > 0


def test_create_tables_runs() -> None:
    from app.db.session import create_tables

    create_tables()
    create_tables()


def test_timestamps_come_back_in_utc() -> None:
    """SQLite returns naive datetimes; they must still serialize with an offset."""
    from app.db.models import Service
    from app.db.session import SessionLocal, create_tables

    create_tables()
    with SessionLocal() as db:
        svc = Service(name="tz-check", slug="tz-check")
        db.add(svc)
        db.commit()
        db.expire_all()
        loaded = db.get(Service, svc.id)
        assert loaded.created_at.tzinfo is not None
        assert loaded.created_at.utcoffset().total_seconds() == 0

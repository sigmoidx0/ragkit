"""Minimal import smoke test."""

from __future__ import annotations


def test_app_imports() -> None:
    from app.main import app

    assert app.title == "ragkit"
    routes = {r.path for r in app.routes}
    assert "/health" in routes
    assert "/auth/login" in routes
    assert "/search" in routes
    assert "/documents" in routes


def test_config_loads() -> None:
    from app.core.config import get_settings

    s = get_settings()
    assert s.embeddings.provider in {"ollama", "tei", "vllm", "azure_openai"}
    assert s.ingest.chunk_size > 0


def test_create_tables_runs() -> None:
    from app.db.session import create_tables

    create_tables()
    create_tables()

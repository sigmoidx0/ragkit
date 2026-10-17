"""Minimal import smoke test."""

from __future__ import annotations


def test_app_imports() -> None:
    from app.main import app

    assert app.title == "ragkit"
    routes = {r.path for r in app.routes}
    assert "/health" in routes
    assert "/auth/login" in routes
    assert "/workspaces/{workspace_id}/search" in routes
    assert "/workspaces/{workspace_id}/documents" in routes
    assert "/agents/{agent_id}/chat" in routes
    assert "/workspaces/{workspace_id}/document-sets" in routes
    # Pre-rename paths the external MCP adapter still calls.
    assert "/services/{workspace_id}/search" in routes
    assert "/services/{workspace_id}/documents/{document_id}" in routes


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
    from app.db.models import Workspace
    from app.db.session import SessionLocal, create_tables

    create_tables()
    with SessionLocal() as db:
        svc = Workspace(name="tz-check", slug="tz-check")
        db.add(svc)
        db.commit()
        db.expire_all()
        loaded = db.get(Workspace, svc.id)
        assert loaded.created_at.tzinfo is not None
        assert loaded.created_at.utcoffset().total_seconds() == 0


def test_sqlite_enforces_foreign_key_cascades() -> None:
    """Deleting a chat must take its stored sources with it."""
    from app.db.models import Agent, ChatSession, ChatTurnSources, User, Workspace
    from app.db.session import SessionLocal, create_tables

    create_tables()
    with SessionLocal() as db:
        ws = Workspace(name="fk", slug="fk-check")
        user = User(email="fk@example.com", hashed_password="x")
        db.add_all([ws, user])
        db.flush()
        agent = Agent(workspace_id=ws.id, name="fk")
        db.add(agent)
        db.flush()
        chat = ChatSession(user_id=user.id, agent_id=agent.id)
        db.add(chat)
        db.flush()
        db.add(ChatTurnSources(session_id=chat.id, turn_index=0, sources_json=[]))
        db.commit()

        db.delete(db.get(Workspace, ws.id))  # cascades workspace → agent → chat → sources
        db.commit()
        assert db.query(ChatTurnSources).filter_by(session_id=chat.id).count() == 0

"""Document sets narrow what an agent can retrieve."""

from __future__ import annotations

from app.agent.config import documents_in_sets, resolve_document_scope
from app.db.models import Document, DocumentSet, DocumentSetDocument, Workspace
from app.db.session import SessionLocal, create_tables
from app.schemas.agent_config import AgentConfig
from app.vectorstore.qdrant import QdrantStore


def _doc(ws: int, title: str) -> Document:
    return Document(
        workspace_id=ws, title=title, source_filename=f"{title}.md", mime_type="text/markdown",
        file_path="/tmp/x", size_bytes=1, sha256="0" * 64,
    )


def test_scope_is_the_union_of_the_sets_and_stays_inside_the_workspace() -> None:
    create_tables()
    with SessionLocal() as db:
        ws, other = Workspace(name="a", slug="ds-a"), Workspace(name="b", slug="ds-b")
        db.add_all([ws, other])
        db.flush()
        d1, d2, d3, foreign = _doc(ws.id, "d1"), _doc(ws.id, "d2"), _doc(ws.id, "d3"), _doc(other.id, "x")
        db.add_all([d1, d2, d3, foreign])
        db.flush()
        hr, legal, empty, theirs = (
            DocumentSet(workspace_id=ws.id, name="hr"),
            DocumentSet(workspace_id=ws.id, name="legal"),
            DocumentSet(workspace_id=ws.id, name="empty"),
            DocumentSet(workspace_id=other.id, name="theirs"),
        )
        db.add_all([hr, legal, empty, theirs])
        db.flush()
        db.add_all([
            DocumentSetDocument(document_set_id=hr.id, document_id=d1.id),
            DocumentSetDocument(document_set_id=legal.id, document_id=d1.id),
            DocumentSetDocument(document_set_id=legal.id, document_id=d2.id),
            DocumentSetDocument(document_set_id=theirs.id, document_id=foreign.id),
        ])
        db.commit()

        assert documents_in_sets(db, ws.id, []) is None  # ad-hoc search with no sets: no filter
        # An agent with no sets searches nothing — never the whole workspace by default.
        assert resolve_document_scope(db, ws.id, AgentConfig()) == []
        assert sorted(resolve_document_scope(db, ws.id, AgentConfig(document_set_ids=[legal.id]))) == sorted([d1.id, d2.id])
        assert sorted(documents_in_sets(db, ws.id, [hr.id, legal.id])) == sorted([d1.id, d2.id])
        assert documents_in_sets(db, ws.id, [empty.id]) == []  # empty set: nothing, not everything
        assert documents_in_sets(db, ws.id, [theirs.id]) == []  # another workspace's set is ignored


def test_an_empty_scope_searches_nothing() -> None:
    store = QdrantStore.__new__(QdrantStore)  # no client needed: the guard returns first
    assert store.search(vector=[0.0], top_k=5, workspace_id=1, document_ids=[]) == []

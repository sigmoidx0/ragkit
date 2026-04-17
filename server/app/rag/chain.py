"""LangChain LCEL: query → embed → Qdrant search → attach document titles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Document
from app.embeddings import get_embedder
from app.vectorstore import SearchHit, get_vectorstore


@dataclass
class SearchQuery:
    query: str
    top_k: int
    document_id: int | None = None


@dataclass
class EnrichedHit:
    document_id: int
    document_title: str | None
    ordinal: int
    score: float
    text: str
    metadata: dict[str, Any]


def _enrich(db: Session, hits: list[SearchHit]) -> list[EnrichedHit]:
    if not hits:
        return []
    doc_ids = {
        int(h.payload["document_id"])
        for h in hits
        if h.payload.get("document_id") is not None
    }
    docs: dict[int, Document] = {}
    if doc_ids:
        for d in db.execute(select(Document).where(Document.id.in_(doc_ids))).scalars():
            docs[d.id] = d

    out: list[EnrichedHit] = []
    for h in hits:
        p = h.payload or {}
        doc_id = int(p["document_id"]) if p.get("document_id") is not None else 0
        out.append(
            EnrichedHit(
                document_id=doc_id,
                document_title=docs[doc_id].title if doc_id in docs else None,
                ordinal=int(p.get("ordinal", 0)),
                score=h.score,
                text=str(p.get("text") or ""),
                metadata=dict(p.get("source_metadata") or {}),
            )
        )
    return out


def build_search_chain(db: Session):
    """Return LCEL chain: SearchQuery → list[EnrichedHit]."""
    embedder = get_embedder()
    vs = get_vectorstore()

    embed = RunnableLambda(lambda q: embedder.embed_query(q.query))

    def _do_search(inputs: dict[str, Any]) -> list[SearchHit]:
        q: SearchQuery = inputs["query"]
        vec: list[float] = inputs["vector"]
        return vs.search(vector=vec, top_k=q.top_k, document_id=q.document_id)

    search = RunnableLambda(_do_search)
    enrich = RunnableLambda(lambda hits: _enrich(db, hits))

    return (
        RunnableParallel(query=RunnablePassthrough(), vector=embed)
        | search
        | enrich
    )


def run_search(db: Session, q: SearchQuery) -> list[EnrichedHit]:
    settings = get_settings()
    if q.top_k <= 0 or q.top_k > settings.search.max_top_k:
        q.top_k = min(max(1, q.top_k), settings.search.max_top_k)
    return build_search_chain(db).invoke(q)

"""Enrich raw SearchHits with document metadata from the DB."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document
from app.vectorstore import SearchHit


class EnrichedHit:
    def __init__(
        self,
        document_id: int,
        document_title: str | None,
        ordinal: int,
        score: float,
        text: str,
        metadata: dict[str, Any],
    ) -> None:
        self.document_id = document_id
        self.document_title = document_title
        self.ordinal = ordinal
        self.score = score
        self.text = text
        self.metadata = metadata


def enrich_hits(db: Session, hits: list[SearchHit]) -> list[EnrichedHit]:
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

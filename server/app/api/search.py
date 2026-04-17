"""Semantic search API."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbDep, ServiceOrUser
from app.core.config import get_settings
from app.rag.chain import SearchQuery, run_search
from app.schemas.search import SearchHitOut, SearchRequest, SearchResponse

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search(payload: SearchRequest, db: DbDep, _auth: ServiceOrUser) -> SearchResponse:
    settings = get_settings()
    top_k = payload.top_k or settings.search.default_top_k
    query = SearchQuery(query=payload.query, top_k=top_k, document_id=payload.document_id)
    hits = run_search(db, query)
    return SearchResponse(
        query=payload.query,
        hits=[
            SearchHitOut(
                document_id=h.document_id,
                document_title=h.document_title,
                ordinal=h.ordinal,
                score=h.score,
                text=h.text,
                metadata=h.metadata,
            )
            for h in hits
        ],
    )

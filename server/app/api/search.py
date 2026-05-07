"""Semantic search API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbDep, ServiceMemberDep
from app.core.config import get_settings
from app.db.models import Pipeline, PipelineStatus
from app.pipeline.executor import run_pipeline
from app.pipeline.types import ExecutionContext
from app.rag.chain import SearchQuery, run_search
from app.schemas.search import SearchHitOut, SearchRequest, SearchResponse

router = APIRouter(tags=["search"])


@router.post("/services/{service_id}/search", response_model=SearchResponse)
def search(
    service_id: int,
    payload: SearchRequest,
    db: DbDep,
    _membership: ServiceMemberDep,
) -> SearchResponse:
    settings = get_settings()
    top_k = payload.top_k or settings.search.default_top_k

    if payload.pipeline_id is not None:
        pipeline = db.get(Pipeline, payload.pipeline_id)
        if not pipeline or pipeline.service_id != service_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "pipeline not found")
        if pipeline.status != PipelineStatus.active:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "pipeline is not active")
        ctx = ExecutionContext(
            db=db,
            service_id=service_id,
            run_inputs={"query": payload.query, "top_k": top_k},
        )
        results, _ = run_pipeline(pipeline.graph_json, ctx)
        return SearchResponse(
            query=payload.query,
            hits=[
                SearchHitOut(
                    document_id=r.document_id,
                    document_title=r.document_title,
                    ordinal=r.ordinal,
                    score=r.score,
                    text=r.text,
                    metadata=r.metadata,
                )
                for r in results
            ],
        )

    query = SearchQuery(
        query=payload.query,
        top_k=top_k,
        service_id=service_id,
        document_id=payload.document_id,
    )
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

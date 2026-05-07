"""LangChain LCEL: query → embed → vector search → rerank → enrich."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.embeddings import get_embedder
from app.rag.enrich import EnrichedHit, enrich_hits
from app.rag.reranker import get_reranker
from app.vectorstore import SearchHit, get_vectorstore


@dataclass
class SearchQuery:
    query: str
    top_k: int
    service_id: int | None = None
    document_id: int | None = None


def _enrich(db: Session, hits: list[SearchHit]) -> list[EnrichedHit]:
    return enrich_hits(db, hits)


def build_search_chain(db: Session):
    """Return LCEL chain: SearchQuery → list[EnrichedHit]."""
    embedder = get_embedder()
    vs = get_vectorstore()
    reranker = get_reranker()
    reranker_cfg = get_settings().search.reranker

    embed = RunnableLambda(lambda q: embedder.embed_query(q.query))

    def _do_search(inputs: dict[str, Any]) -> dict[str, Any]:
        q: SearchQuery = inputs["query"]
        vec: list[float] = inputs["vector"]
        fetch_k = q.top_k * reranker_cfg.fetch_k_multiplier if reranker_cfg is not None else q.top_k
        hits = vs.search(
            vector=vec,
            top_k=fetch_k,
            service_id=q.service_id,
            document_id=q.document_id,
            query_text=q.query,
        )
        return {"query": q, "hits": hits}

    def _rerank(data: dict[str, Any]) -> list[SearchHit]:
        q: SearchQuery = data["query"]
        return reranker.rerank(q.query, data["hits"], q.top_k)

    search = RunnableLambda(_do_search)
    rerank = RunnableLambda(_rerank)
    enrich = RunnableLambda(lambda hits: _enrich(db, hits))

    return (
        RunnableParallel(query=RunnablePassthrough(), vector=embed)
        | search
        | rerank
        | enrich
    )


def run_search(db: Session, q: SearchQuery) -> list[EnrichedHit]:
    settings = get_settings()
    if q.top_k <= 0 or q.top_k > settings.search.max_top_k:
        q.top_k = min(max(1, q.top_k), settings.search.max_top_k)
    return build_search_chain(db).invoke(q)

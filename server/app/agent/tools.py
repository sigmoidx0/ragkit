"""Shared LangChain tools used by sub-agents."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.pipeline.executor import run_pipeline
from app.pipeline.types import ExecutionContext
from app.rag.chain import SearchQuery, run_search
from app.rag.citation import build_context_block, hits_to_sources
from app.schemas.chat import SourceItem

logger = logging.getLogger(__name__)


def make_retrieval_tool(
    db: Session,
    service_id: int,
    top_k: int,
    pipeline_graph: dict[str, Any] | None = None,
):
    """Return (tool, sources_store).

    sources_store is populated on each invocation keyed by query string.
    The executor reads it on on_tool_end to build observation SSE events.

    With `pipeline_graph`, retrieval runs the agent's Pipeline Builder pipeline
    instead of the built-in search chain. Its results carry the same fields as
    the built-in hits, so citation formatting is shared.
    """
    sources_store: dict[str, list[SourceItem]] = {}

    def _search(query: str) -> list:
        if pipeline_graph is not None:
            ctx = ExecutionContext(
                db=db,
                service_id=service_id,
                run_inputs={"query": query, "top_k": top_k},
            )
            results, _timings = run_pipeline(pipeline_graph, ctx)
            return results
        return run_search(db, SearchQuery(query=query, top_k=top_k, service_id=service_id))

    @tool
    async def retrieval(query: str) -> str:
        """Search the knowledge base for relevant information.
        Use a concise, focused query. Call multiple times with different queries
        if the first result is insufficient.
        """
        logger.debug(
            "[retrieval] query=%r top_k=%d service_id=%d pipeline=%s",
            query, top_k, service_id, pipeline_graph is not None,
        )
        hits = await asyncio.to_thread(_search, query)
        sources_store[query] = hits_to_sources(hits)
        logger.debug("[retrieval] → %d hits for query=%r", len(hits), query)
        return build_context_block(hits)

    return retrieval, sources_store

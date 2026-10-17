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
from app.rag.citation import CitationNumbering, build_context_block, hits_to_sources
from app.schemas.chat import SourceItem

logger = logging.getLogger(__name__)


def make_retrieval_tool(
    db: Session,
    workspace_id: int,
    top_k: int,
    pipeline_graph: dict[str, Any] | None = None,
    document_ids: list[int] | None = None,
    *,
    sources_store: dict[str, list[SourceItem]],
    numbering: CitationNumbering,
):
    """Return the retrieval tool for one turn.

    sources_store is populated on each invocation keyed by query string.
    The executor reads it on on_tool_end to build observation SSE events.
    Both it and `numbering` belong to the turn and are shared with the delegate
    tools, so every source of one answer lands in one store, in one sequence.

    With `pipeline_graph`, retrieval runs the agent's Pipeline Builder pipeline
    instead of the built-in search chain. Its results carry the same fields as
    the built-in hits, so citation formatting is shared.

    `document_ids` limits retrieval to the agent's document sets (None = no
    filter; an agent always passes a list), for both the built-in chain and a pipeline.
    """
    def _search(query: str) -> list:
        if pipeline_graph is not None:
            ctx = ExecutionContext(
                db=db,
                workspace_id=workspace_id,
                run_inputs={"query": query, "top_k": top_k},
                document_ids=document_ids,
            )
            results, _timings = run_pipeline(pipeline_graph, ctx)
            return results
        return run_search(
            db, SearchQuery(query=query, top_k=top_k, workspace_id=workspace_id, document_ids=document_ids)
        )

    @tool
    async def retrieval(query: str) -> str:
        """Search the knowledge base for relevant information.
        Use a concise, focused query. Call multiple times with different queries
        if the first result is insufficient.
        """
        logger.debug(
            "[retrieval] query=%r top_k=%d workspace=%d pipeline=%s scoped=%s",
            query, top_k, workspace_id, pipeline_graph is not None, document_ids is not None,
        )
        hits = await asyncio.to_thread(_search, query)
        # Numbered with no await in between, so parallel calls can't interleave.
        numbers = numbering.assign(hits)
        sources_store[query] = hits_to_sources(hits, numbers)
        logger.debug("[retrieval] → %d hits for query=%r", len(hits), query)
        return build_context_block(hits, numbers)

    return retrieval

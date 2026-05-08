"""LangChain tools available to the RAG agent."""

from __future__ import annotations

import asyncio

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.rag.chain import SearchQuery, run_search
from app.rag.citation import build_context_block, hits_to_sources
from app.schemas.chat import SourceItem


def make_retrieval_tool(db: Session, service_id: int, top_k: int):
    """Return (tool, sources_store).

    sources_store is a dict populated on each tool invocation, keyed by the
    query string. The executor reads it on `on_tool_end` to build SSE events.
    """
    sources_store: dict[str, list[SourceItem]] = {}

    @tool
    async def retrieval(query: str) -> str:
        """Search the knowledge base for relevant information.
        Use a concise, focused query. Call multiple times with different queries
        if the first result is insufficient.
        """
        hits = await asyncio.to_thread(
            run_search, db, SearchQuery(query=query, top_k=top_k, service_id=service_id)
        )
        sources_store[query] = hits_to_sources(hits)
        return build_context_block(hits)

    return retrieval, sources_store

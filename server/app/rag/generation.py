"""Async SSE generator: retrieval → prompt → LLM stream."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import SystemPrompt
from app.llm import get_chat_model
from app.rag.chain import SearchQuery, run_search
from app.rag.citation import build_context_block, hits_to_sources
from app.rag.prompts import build_messages
from app.schemas.chat import (
    ChatRequest,
    DoneEvent,
    ErrorEvent,
    RetrievalCompleteEvent,
    RetrievalStartEvent,
    TokenEvent,
    UsageInfo,
)


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _load_system_prompt(db: Session, service_id: int) -> str:
    row = db.execute(
        select(SystemPrompt).where(
            SystemPrompt.service_id == service_id,
            SystemPrompt.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if row:
        return row.content
    return get_settings().chat.fallback_system_prompt


async def generate_stream(
    db: Session,
    service_id: int,
    request: ChatRequest,
) -> AsyncIterator[str]:
    cfg = get_settings()
    top_k = request.top_k or cfg.chat.default_top_k

    # extract query from last user message
    user_messages = [m for m in request.messages if m.role == "user"]
    if not user_messages:
        yield _sse("error", ErrorEvent(error="no user message provided").model_dump())
        return
    query = user_messages[-1].content

    yield _sse("retrieval_start", RetrievalStartEvent(query=query, top_k=top_k).model_dump())

    try:
        search_q = SearchQuery(query=query, top_k=top_k, service_id=service_id)
        hits = await asyncio.to_thread(run_search, db, search_q)
    except Exception as exc:
        yield _sse("error", ErrorEvent(error=str(exc)).model_dump())
        return

    sources = hits_to_sources(hits)
    yield _sse("retrieval_complete", RetrievalCompleteEvent(sources=sources).model_dump())

    system_prompt = await asyncio.to_thread(_load_system_prompt, db, service_id)
    context_block = build_context_block(hits)
    messages = build_messages(system_prompt, request.messages, context_block)

    llm = get_chat_model()
    finish_reason = "stop"
    usage: UsageInfo | None = None

    try:
        async for chunk in llm.astream(messages):
            delta = chunk.content
            if delta:
                yield _sse("token", TokenEvent(delta=str(delta)).model_dump())
            # capture usage from final chunk if present
            if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                meta = chunk.usage_metadata
                usage = UsageInfo(
                    input_tokens=getattr(meta, "input_tokens", None),
                    output_tokens=getattr(meta, "output_tokens", None),
                )
            if hasattr(chunk, "response_metadata"):
                fr = chunk.response_metadata.get("finish_reason")
                if fr:
                    finish_reason = fr
    except Exception as exc:
        yield _sse("error", ErrorEvent(error=str(exc)).model_dump())
        return

    yield _sse("done", DoneEvent(finish_reason=finish_reason, usage=usage).model_dump())

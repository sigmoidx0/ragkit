"""Stream SSE events from the multi-agent RAG graph."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

logger = logging.getLogger(__name__)

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.graph import build_multi_agent_graph
from app.core.config import get_settings
from app.db.models import SystemPrompt
from app.schemas.chat import (
    AgentStepEvent,
    ChatMessage,
    DoneEvent,
    ErrorEvent,
    TokenEvent,
)

_SUB_AGENT_NODES = {"retrieval_agent", "summary_agent", "comparison_agent"}


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def _load_system_prompt(db: Session, service_id: int) -> str:
    row = db.execute(
        select(SystemPrompt).where(
            SystemPrompt.service_id == service_id,
            SystemPrompt.is_active.is_(True),
        )
    ).scalar_one_or_none()
    return row.content if row else get_settings().chat.fallback_system_prompt


def _to_lc_messages(messages: list[ChatMessage]) -> list:
    result = []
    for msg in messages:
        if msg.role == "user":
            result.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            result.append(AIMessage(content=msg.content))
    return result


def _token_sse_from_chunk(event: dict) -> list[str]:
    chunk = event["data"].get("chunk")
    if not chunk or getattr(chunk, "tool_call_chunks", None):
        return []
    delta = chunk.content
    if isinstance(delta, str) and delta:
        return [_sse("token", TokenEvent(delta=delta).model_dump())]
    if isinstance(delta, list):
        out = []
        for block in delta:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if text:
                    out.append(_sse("token", TokenEvent(delta=text).model_dump()))
        return out
    return []


async def _stream_graph(graph, sources_store: dict, input_state: dict, run_config: dict):
    # on_chat_model_stream events inside sub-agents carry langgraph_node="agent"
    # (the inner ReAct node), not the outer node name. Track entry/exit instead.
    _current_query = ""
    _in_sub_agent = False
    try:
        async for event in graph.astream_events(input_state, config=run_config, version="v2"):
            kind = event["event"]
            name = event.get("name", "")

            if kind == "on_chain_start" and name in _SUB_AGENT_NODES:
                logger.debug("[stream] entering sub-agent node=%r", name)
                _in_sub_agent = True

            elif kind == "on_chain_end" and name in _SUB_AGENT_NODES:
                logger.debug("[stream] sub-agent node=%r finished", name)
                _in_sub_agent = False

            elif kind == "on_tool_start" and name == "retrieval":
                _current_query = (event["data"].get("input") or {}).get("query", "")
                if _current_query:
                    logger.debug("[stream] tool_call retrieval query=%r", _current_query)
                    yield _sse(
                        "agent_step",
                        AgentStepEvent(
                            type="tool_call", tool="retrieval", input=_current_query
                        ).model_dump(),
                    )

            elif kind == "on_tool_end" and name == "retrieval":
                sources = sources_store.get(_current_query, [])
                logger.debug("[stream] observation retrieval sources=%d", len(sources))
                yield _sse(
                    "agent_step",
                    AgentStepEvent(
                        type="observation", tool="retrieval", output=sources
                    ).model_dump(),
                )

            elif kind == "on_chat_model_stream" and _in_sub_agent:
                for token_sse in _token_sse_from_chunk(event):
                    yield token_sse

    except Exception as exc:
        logger.debug("[stream] error: %s", exc)
        yield _sse("error", ErrorEvent(error=str(exc)).model_dump())
        return

    logger.debug("[stream] pipeline done")
    yield _sse("done", DoneEvent(finish_reason="stop").model_dump())


async def agent_stream(
    db: Session,
    service_id: int,
    messages: list[ChatMessage],
    top_k: int | None = None,
    filters: dict | None = None,
) -> AsyncIterator[str]:
    cfg = get_settings()
    _top_k = top_k or cfg.chat.default_top_k

    if not any(m.role == "user" for m in messages):
        yield _sse("error", ErrorEvent(error="no user message provided").model_dump())
        return

    system_prompt = await asyncio.to_thread(_load_system_prompt, db, service_id)
    graph, sources_store = build_multi_agent_graph(
        db, service_id, _top_k, system_prompt, checkpointer=None
    )

    input_state = {"messages": _to_lc_messages(messages), "agent_type": ""}
    async for chunk in _stream_graph(graph, sources_store, input_state, run_config={}):
        yield chunk


async def session_agent_stream(
    db: Session,
    service_id: int,
    thread_id: str,
    new_message: str,
    top_k: int | None = None,
    filters: dict | None = None,
) -> AsyncIterator[str]:
    from app.agent.checkpoint import get_checkpointer

    cfg = get_settings()
    _top_k = top_k or cfg.chat.default_top_k
    system_prompt = await asyncio.to_thread(_load_system_prompt, db, service_id)

    graph, sources_store = build_multi_agent_graph(
        db, service_id, _top_k, system_prompt, checkpointer=get_checkpointer()
    )

    input_state = {"messages": [HumanMessage(content=new_message)], "agent_type": ""}
    run_config = {"configurable": {"thread_id": thread_id}}

    async for chunk in _stream_graph(graph, sources_store, input_state, run_config):
        yield chunk

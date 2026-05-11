"""LangGraph ReAct agent: streams SSE events from astream_events."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.tools import make_retrieval_tool
from app.core.config import get_settings
from app.db.models import SystemPrompt
from app.llm import get_chat_model
from app.schemas.chat import (
    AgentStepEvent,
    ChatMessage,
    DoneEvent,
    ErrorEvent,
    TokenEvent,
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
    return row.content if row else get_settings().chat.fallback_system_prompt


def _to_lc_messages(messages: list[ChatMessage]) -> list:
    result = []
    for msg in messages:
        if msg.role == "user":
            result.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            result.append(AIMessage(content=msg.content))
    return result


async def agent_stream(
    db: Session,
    service_id: int,
    messages: list[ChatMessage],
    top_k: int | None = None,
    filters: dict | None = None,
) -> AsyncIterator[str]:
    cfg = get_settings()
    _top_k = top_k or cfg.chat.default_top_k

    user_messages = [m for m in messages if m.role == "user"]
    if not user_messages:
        yield _sse("error", ErrorEvent(error="no user message provided").model_dump())
        return

    retrieval_tool, sources_store = make_retrieval_tool(db, service_id, _top_k)

    system_prompt = await asyncio.to_thread(_load_system_prompt, db, service_id)

    llm = get_chat_model()
    agent = create_react_agent(
        llm,
        [retrieval_tool],
        state_modifier=SystemMessage(content=system_prompt),
    )

    lc_messages = _to_lc_messages(messages)
    recursion_limit = cfg.agent.max_iterations * 2 + 1

    try:
        async for event in agent.astream_events(
            {"messages": lc_messages},
            config={"recursion_limit": recursion_limit},
            version="v2",
        ):
            kind = event["event"]
            name = event.get("name", "")

            if kind == "on_tool_start" and name == "retrieval":
                query = event["data"].get("input", {}).get("query", "")
                yield _sse(
                    "agent_step",
                    AgentStepEvent(type="tool_call", tool="retrieval", input=query).model_dump(),
                )

            elif kind == "on_tool_end" and name == "retrieval":
                query = event["data"].get("input", {}).get("query", "")
                sources = sources_store.get(query, [])
                yield _sse(
                    "agent_step",
                    AgentStepEvent(
                        type="observation", tool="retrieval", output=sources
                    ).model_dump(),
                )

            elif kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if not chunk:
                    continue
                if getattr(chunk, "tool_call_chunks", None):
                    continue
                delta = chunk.content
                if isinstance(delta, str) and delta:
                    yield _sse("token", TokenEvent(delta=delta).model_dump())
                elif isinstance(delta, list):
                    for block in delta:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                yield _sse("token", TokenEvent(delta=text).model_dump())

    except Exception as exc:
        yield _sse("error", ErrorEvent(error=str(exc)).model_dump())
        return

    yield _sse("done", DoneEvent(finish_reason="stop").model_dump())


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

    retrieval_tool, sources_store = make_retrieval_tool(db, service_id, _top_k)
    system_prompt = await asyncio.to_thread(_load_system_prompt, db, service_id)

    llm = get_chat_model()
    agent = create_react_agent(
        llm,
        [retrieval_tool],
        checkpointer=get_checkpointer(),
        state_modifier=SystemMessage(content=system_prompt),
    )

    recursion_limit = cfg.agent.max_iterations * 2 + 1
    run_config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": recursion_limit,
    }

    try:
        async for event in agent.astream_events(
            {"messages": [HumanMessage(content=new_message)]},
            config=run_config,
            version="v2",
        ):
            kind = event["event"]
            name = event.get("name", "")

            if kind == "on_tool_start" and name == "retrieval":
                query = event["data"].get("input", {}).get("query", "")
                yield _sse(
                    "agent_step",
                    AgentStepEvent(type="tool_call", tool="retrieval", input=query).model_dump(),
                )

            elif kind == "on_tool_end" and name == "retrieval":
                query = event["data"].get("input", {}).get("query", "")
                sources = sources_store.get(query, [])
                yield _sse(
                    "agent_step",
                    AgentStepEvent(type="observation", tool="retrieval", output=sources).model_dump(),
                )

            elif kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if not chunk:
                    continue
                if getattr(chunk, "tool_call_chunks", None):
                    continue
                delta = chunk.content
                if isinstance(delta, str) and delta:
                    yield _sse("token", TokenEvent(delta=delta).model_dump())
                elif isinstance(delta, list):
                    for block in delta:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "")
                            if text:
                                yield _sse("token", TokenEvent(delta=text).model_dump())

    except Exception as exc:
        yield _sse("error", ErrorEvent(error=str(exc)).model_dump())
        return

    yield _sse("done", DoneEvent(finish_reason="stop").model_dump())

"""Stream SSE events from the multi-agent RAG graph.

Event types the UI consumes:
    graph           shape of this run's graph, once up front
    node_state      which top-level node is running / done
    delegate_state  progress inside a delegate agent (agent-as-tool)
    span            trace spans (nodes, LLM calls, tool calls) for the waterfall
    supervisor_route, agent_step, token, done, error
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.agents import INTERNAL_LLM_TAG
from app.agent.config import load_agent_config, load_system_prompt
from app.agent.delegation import DELEGATE_NODE_EVENT, DELEGATE_SOURCES_EVENT, DELEGATE_TOOL_PREFIX
from app.agent.graph import BuiltGraph, build_multi_agent_graph, graph_node_ids
from app.agent.history import count_answers
from app.agent.trace import TraceRecorder
from app.db.models import ChatTurnSources, Service
from app.schemas.agent_config import RetrievalMode
from app.schemas.chat import (
    AgentStepEvent,
    ChatMessage,
    DelegateStateEvent,
    DoneEvent,
    ErrorEvent,
    NodeStateEvent,
    SourceItem,
    SupervisorRouteEvent,
    TokenEvent,
)

logger = logging.getLogger(__name__)

_SUB_AGENT_NODES = {"retrieval_agent", "summary_agent", "comparison_agent", "direct_agent"}


def _tool_query(raw_input: dict | None, key: str = "query") -> str:
    """Normalize a tool's string argument.

    Providers disagree on the shape. Most send `{"query": "휴학 절차"}`, but some
    local models (qwen2.5 via Ollama, for one) wrap each argument in its schema:
    `{"query": {"type": "string", "value": "휴학 절차"}}`.
    """
    value = (raw_input or {}).get(key, "")
    if isinstance(value, dict):
        value = value.get("value") or value.get(key) or ""
    return value if isinstance(value, str) else str(value)


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


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


async def _stream_graph(built: BuiltGraph, input_state: dict, run_config: dict):
    # on_chat_model_stream events inside sub-agents carry langgraph_node="agent"
    # (the inner ReAct node), not the outer node name. Track entry/exit instead.
    pending_queries: dict[str, str] = {}  # run_id → query, supports parallel tool calls
    in_sub_agent = False
    delegate_nodes = {d.tool_name: d.node_id for d in built.delegates}  # tool name → graph node id

    yield _sse("graph", built.topology().model_dump())
    # Only nodes the graph actually has are reported, so stray on_chain_start
    # events from inner ReAct machinery don't light up the diagram.
    graph_nodes = graph_node_ids(built.graph)
    trace = TraceRecorder(graph_nodes)

    try:
        async for event in built.graph.astream_events(input_state, config=run_config, version="v2"):
            kind = event["event"]
            name = event.get("name", "")

            # ── tracing ──
            span_meta: dict = {}
            if kind == "on_tool_start":
                span_meta["input"] = _tool_query(
                    event["data"].get("input"), "question" if name.startswith(DELEGATE_TOOL_PREFIX) else "query"
                )
            elif kind in ("on_tool_end", "on_tool_error") and name == "retrieval":
                span_meta["hits"] = len(built.sources_store.get(pending_queries.get(event.get("run_id", ""), ""), []))
            if (span := trace.observe(event, span_meta)) is not None:
                yield _sse("span", span.model_dump())

            # ── graph highlighting ──
            if kind == "on_chain_start" and name in graph_nodes:
                yield _sse("node_state", NodeStateEvent(node=name, status="running").model_dump())
            elif kind == "on_chain_end" and name in graph_nodes:
                yield _sse("node_state", NodeStateEvent(node=name, status="done").model_dump())

            if kind == "on_chain_end" and name == "supervisor":
                output = event["data"].get("output") or {}
                agent_type = output.get("agent_type", "")
                if agent_type and agent_type != "direct":
                    yield _sse("supervisor_route", SupervisorRouteEvent(agent_type=agent_type).model_dump())

            elif kind == "on_chain_start" and name in _SUB_AGENT_NODES:
                in_sub_agent = True

            elif kind == "on_chain_end" and name in _SUB_AGENT_NODES:
                in_sub_agent = False

            # ── own document searches ──
            elif kind == "on_tool_start" and name == "retrieval":
                run_id = event.get("run_id", "")
                query = _tool_query(event["data"].get("input"))
                if query:
                    pending_queries[run_id] = query
                    yield _sse(
                        "agent_step",
                        AgentStepEvent(type="tool_call", tool="retrieval", input=query).model_dump(),
                    )

            # on_tool_error is handled alongside on_tool_end so a failed lookup
            # still closes out its tool_call instead of leaving the UI waiting.
            elif kind in ("on_tool_end", "on_tool_error") and name == "retrieval":
                query = pending_queries.pop(event.get("run_id", ""), "")
                sources = built.sources_store.get(query, [])
                yield _sse(
                    "agent_step",
                    AgentStepEvent(type="observation", tool="retrieval", output=sources).model_dump(),
                )

            # ── delegate agents (agent-as-tool) ──
            elif kind == "on_tool_start" and name in delegate_nodes:
                question = _tool_query(event["data"].get("input"), "question")
                yield _sse("agent_step", AgentStepEvent(type="tool_call", tool=name, input=question).model_dump())
                yield _sse("node_state", NodeStateEvent(node=delegate_nodes[name], status="running").model_dump())

            elif kind in ("on_tool_end", "on_tool_error") and name in delegate_nodes:
                yield _sse("node_state", NodeStateEvent(node=delegate_nodes[name], status="done").model_dump())

            elif kind == "on_custom_event" and name == DELEGATE_NODE_EVENT:
                yield _sse("delegate_state", DelegateStateEvent(**event["data"]).model_dump())

            elif kind == "on_custom_event" and name == DELEGATE_SOURCES_EVENT:
                data = event["data"]
                yield _sse(
                    "agent_step",
                    AgentStepEvent(
                        type="observation",
                        tool=data["tool"],
                        output=[SourceItem(**s) for s in data["sources"]],
                    ).model_dump(),
                )

            elif kind == "on_chat_model_stream" and in_sub_agent and INTERNAL_LLM_TAG not in (event.get("tags") or []):
                for token_sse in _token_sse_from_chunk(event):
                    yield token_sse

    except Exception as exc:
        logger.debug("[stream] error: %s", exc)
        yield _sse("error", ErrorEvent(error=str(exc)).model_dump())
        return

    yield _sse("done", DoneEvent(finish_reason="stop").model_dump())


def _build_graph(
    db: Session,
    service_id: int,
    top_k: int | None,
    retrieval_mode: RetrievalMode | None,
    user_id: int | None,
    checkpointer=None,
) -> BuiltGraph:
    """Load the agent's config and prompt, then assemble its graph for one run."""
    agent_cfg = load_agent_config(db.get(Service, service_id))
    return build_multi_agent_graph(
        db,
        service_id,
        agent_cfg,
        load_system_prompt(db, service_id),
        retrieval_mode or agent_cfg.default_retrieval_mode,
        top_k=top_k,
        checkpointer=checkpointer,
        user_id=user_id,
    )


async def agent_stream(
    db: Session,
    service_id: int,
    messages: list[ChatMessage],
    top_k: int | None = None,
    retrieval_mode: RetrievalMode | None = None,
    user_id: int | None = None,
) -> AsyncIterator[str]:
    if not any(m.role == "user" for m in messages):
        yield _sse("error", ErrorEvent(error="no user message provided").model_dump())
        return

    try:
        built = await asyncio.to_thread(_build_graph, db, service_id, top_k, retrieval_mode, user_id)
    except ValueError as exc:
        # A misconfigured agent (e.g. a provider with no model) fails here, before
        # streaming starts, so report it as a normal error event.
        yield _sse("error", ErrorEvent(error=str(exc)).model_dump())
        return

    input_state = {"messages": _to_lc_messages(messages), "agent_type": ""}
    async for chunk in _stream_graph(built, input_state, run_config={}):
        yield chunk


def _save_turn_sources(db: Session, session_id: int, turn_index: int, sources: list[dict]) -> None:
    existing = db.execute(
        select(ChatTurnSources).where(
            ChatTurnSources.session_id == session_id,
            ChatTurnSources.turn_index == turn_index,
        )
    ).scalar_one_or_none()
    if existing:
        existing.sources_json = sources
    else:
        db.add(ChatTurnSources(session_id=session_id, turn_index=turn_index, sources_json=sources))
    db.commit()


async def session_agent_stream(
    db: Session,
    service_id: int,
    thread_id: str,
    new_message: str,
    top_k: int | None = None,
    retrieval_mode: RetrievalMode | None = None,
    user_id: int | None = None,
) -> AsyncIterator[str]:
    from app.agent.checkpoint import get_checkpointer

    checkpointer = get_checkpointer()
    try:
        built = await asyncio.to_thread(
            _build_graph, db, service_id, top_k, retrieval_mode, user_id, checkpointer
        )
    except ValueError as exc:
        yield _sse("error", ErrorEvent(error=str(exc)).model_dump())
        return

    # Count existing AI turns to get the index for this new turn
    cp_tuple = await checkpointer.aget_tuple({"configurable": {"thread_id": thread_id}})
    lc_msgs = cp_tuple.checkpoint.get("channel_values", {}).get("messages", []) if cp_tuple else []
    ai_turn_index = count_answers(lc_msgs)

    input_state = {"messages": [HumanMessage(content=new_message)], "agent_type": ""}
    run_config = {"configurable": {"thread_id": thread_id}}

    async for chunk in _stream_graph(built, input_state, run_config):
        yield chunk

    all_sources = [s.model_dump() for sources in built.sources_store.values() for s in sources]
    if all_sources:
        await asyncio.to_thread(_save_turn_sources, db, int(thread_id), ai_turn_index, all_sources)

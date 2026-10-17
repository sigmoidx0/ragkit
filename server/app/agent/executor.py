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
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.errors import GraphInterrupt
from langgraph.types import Command
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.agent.agents import INTERNAL_LLM_TAG
from app.agent.config import load_agent_config, load_system_prompt
from app.agent.delegation import DELEGATE_NODE_EVENT, DELEGATE_SOURCES_EVENT, DELEGATE_TOOL_PREFIX
from app.agent.graph import BuiltGraph, build_multi_agent_graph, graph_node_ids
from app.agent.history import count_answers
from app.agent.mcp import APPROVAL_KIND
from app.agent.trace import TraceRecorder
from app.core.config import get_settings
from app.db.models import (
    Agent,
    ChatTurnLog,
    ChatTurnSources,
    McpToolCall,
    MessageFeedback,
    ToolCallStatus,
)
from app.schemas.agent_config import RetrievalMode
from app.schemas.chat import (
    AgentStepEvent,
    ApprovalRequiredEvent,
    ChatMessage,
    DelegateStateEvent,
    DoneEvent,
    ErrorEvent,
    McpCallEvent,
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


async def _stream_graph(built: BuiltGraph, input_state, run_config: dict, outcome: dict | None = None):
    """Stream one run as SSE. With `outcome` given, the caller finishes the
    stream itself: no "done" is sent, and `outcome["failed"]` says whether an
    "error" was."""
    # on_chat_model_stream events inside sub-agents carry langgraph_node="agent"
    # (the inner ReAct node), not the outer node name. Track entry/exit instead.
    pending_queries: dict[str, str] = {}  # run_id → query, supports parallel tool calls
    in_sub_agent = False
    delegate_nodes = {d.tool_name: d.node_id for d in built.delegates}  # tool name → graph node id
    mcp_tools = {t.tool_name: t for t in built.mcp_tools}

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

            # ── MCP tools ──
            elif kind == "on_tool_start" and name in mcp_tools:
                info = mcp_tools[name]
                yield _sse("mcp_call", McpCallEvent(
                    id=event.get("run_id", ""), server=info.server_name, tool=info.tool,
                    args=event["data"].get("input") or {}, status="running",
                ).model_dump())
                yield _sse("node_state", NodeStateEvent(node=info.node_id, status="running").model_dump())

            elif kind in ("on_tool_end", "on_tool_error") and name in mcp_tools:
                info = mcp_tools[name]
                error = event["data"].get("error")
                output = event["data"].get("output")
                if isinstance(error, GraphInterrupt):
                    # Not a failure: the call is waiting for the user's approval.
                    status, text = "waiting", None
                elif error is not None:
                    status, text = "error", str(error)
                else:
                    status = "error" if getattr(output, "status", None) == "error" else "done"
                    text = str(getattr(output, "content", output))
                yield _sse("mcp_call", McpCallEvent(
                    id=event.get("run_id", ""), server=info.server_name, tool=info.tool,
                    status=status, output=text[:600] if text else None,
                ).model_dump())
                yield _sse("node_state", NodeStateEvent(node=info.node_id, status="done").model_dump())

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
        if outcome is not None:
            outcome["failed"] = True
        yield _sse("error", ErrorEvent(error=str(exc)).model_dump())
        return

    if outcome is None:
        yield _sse("done", DoneEvent(finish_reason="stop").model_dump())


def _build_graph(
    db: Session,
    agent_id: int,
    top_k: int | None,
    retrieval_mode: RetrievalMode | None,
    user_id: int | None,
    checkpointer=None,
    regenerate: bool = False,
) -> BuiltGraph:
    # A run with a checkpointer is a session turn — it can pause for approval.
    """Load the agent's config and prompt, then assemble its graph for one run."""
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise ValueError(f"agent {agent_id} not found")
    agent_cfg = load_agent_config(agent)
    return build_multi_agent_graph(
        db,
        agent,
        agent_cfg,
        load_system_prompt(db, agent.id),
        retrieval_mode or agent_cfg.default_retrieval_mode,
        top_k=top_k,
        checkpointer=checkpointer,
        user_id=user_id,
        answer_temperature=get_settings().agent.regenerate_temperature if regenerate else None,
        interactive=checkpointer is not None,
    )


async def agent_stream(
    db: Session,
    agent_id: int,
    messages: list[ChatMessage],
    top_k: int | None = None,
    retrieval_mode: RetrievalMode | None = None,
    user_id: int | None = None,
) -> AsyncIterator[str]:
    if not any(m.role == "user" for m in messages):
        yield _sse("error", ErrorEvent(error="no user message provided").model_dump())
        return

    try:
        built = await asyncio.to_thread(_build_graph, db, agent_id, top_k, retrieval_mode, user_id)
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


_CITED = re.compile(r"\[(\d+)\]")


def cited_count(answer: str, sources: list[SourceItem]) -> int:
    """Distinct [N] markers in `answer` that name a source the turn found."""
    known = {s.index for s in sources}
    return len({int(n) for n in _CITED.findall(answer)} & known)


async def _fork_point(graph, thread_config: dict, replace_turn: int):
    """The checkpoint to rerun from so that user message `replace_turn` is replaced.

    Walks back along the session's current branch (parent by parent, so turns
    abandoned by an earlier edit are never picked) to the end of the run just
    before that message. Returns its snapshot, or None when there is none.
    """
    snapshot = await graph.aget_state(thread_config)
    fallback = None
    while snapshot is not None and snapshot.config:
        messages = snapshot.values.get("messages", [])
        if sum(isinstance(m, HumanMessage) for m in messages) == replace_turn:
            if not snapshot.next:  # a finished run — the clean place to branch
                return snapshot
            fallback = fallback or snapshot  # that run failed midway; still usable
        if snapshot.parent_config is None:
            break
        snapshot = await graph.aget_state(snapshot.parent_config)
    return fallback


def _clear_turns_from(db: Session, session_id: int, turn_index: int) -> None:
    """Drop what was stored about answers `turn_index` onwards — they're being replaced."""
    for model in (ChatTurnSources, MessageFeedback, ChatTurnLog):
        db.execute(delete(model).where(model.session_id == session_id, model.turn_index >= turn_index))
    db.commit()


def _save_turn_log(db: Session, agent_id: int, session_id: int, turn_index: int, **fields) -> None:
    log = db.execute(
        select(ChatTurnLog).where(ChatTurnLog.session_id == session_id, ChatTurnLog.turn_index == turn_index)
    ).scalar_one_or_none()
    if log is None:
        log = ChatTurnLog(agent_id=agent_id, session_id=session_id, turn_index=turn_index)
        db.add(log)
    for key, value in fields.items():
        setattr(log, key, value)
    db.commit()


async def session_agent_stream(
    db: Session,
    agent_id: int,
    thread_id: str,
    new_message: str,
    top_k: int | None = None,
    retrieval_mode: RetrievalMode | None = None,
    user_id: int | None = None,
    replace_turn: int | None = None,
    regenerate: bool = False,
) -> AsyncIterator[str]:
    """Run one turn of a session.

    `replace_turn` (0-based, counting user messages) reruns the session from
    just before that message with `new_message` in its place: editing a
    question, or — with the same words — regenerating its answer. Everything
    after it is dropped from the session's branch; the checkpoint keeps the old
    branch, but nothing reads it. `regenerate` answers at a modestly higher
    temperature (agent.regenerate_temperature), so the new answer can differ.
    """
    from app.agent.checkpoint import get_checkpointer

    checkpointer = get_checkpointer()
    try:
        built = await asyncio.to_thread(
            _build_graph, db, agent_id, top_k, retrieval_mode, user_id, checkpointer, regenerate
        )
    except ValueError as exc:
        yield _sse("error", ErrorEvent(error=str(exc)).model_dump())
        return

    thread_config = {"configurable": {"thread_id": thread_id}}
    run_config = thread_config
    if replace_turn is None:
        state = await built.graph.aget_state(thread_config)
        prior = state.values.get("messages", []) if state else []
    elif replace_turn == 0:
        # Nothing comes before the first question: start the session over.
        await checkpointer.adelete_thread(thread_id)
        prior = []
    else:
        fork = await _fork_point(built.graph, thread_config, replace_turn)
        if fork is None:
            yield _sse("error", ErrorEvent(error=f"no message {replace_turn} to replace").model_dump())
            return
        # Running from a past checkpoint branches the thread there; the new
        # branch is newest, so it's what the session reads from now on.
        run_config, prior = fork.config, fork.values.get("messages", [])

    ai_turn_index = count_answers(prior)
    if replace_turn is not None:
        await asyncio.to_thread(_clear_turns_from, db, int(thread_id), ai_turn_index)
        await asyncio.to_thread(expire_pending_calls, db, int(thread_id))

    input_state = {"messages": [HumanMessage(content=new_message)], "agent_type": ""}
    run_options = {"top_k": top_k, "retrieval_mode": retrieval_mode, "regenerate": regenerate}
    async for chunk in _finish_turn(
        db, built, agent_id, thread_id, input_state, run_config, ai_turn_index, new_message, run_options, user_id
    ):
        yield chunk


async def _finish_turn(
    db: Session,
    built: BuiltGraph,
    agent_id: int,
    thread_id: str,
    graph_input,
    run_config: dict,
    ai_turn_index: int,
    question: str,
    run_options: dict,
    user_id: int | None,
) -> AsyncIterator[str]:
    """Run (or resume) a session turn, then record what it produced.

    A run that paused on an MCP approval ends with an `approval_required` event
    per pending call and finish_reason "approval_required"; the answer — and its
    turn log — comes with the resume.
    """
    outcome: dict = {"failed": False}
    async for chunk in _stream_graph(built, graph_input, run_config, outcome):
        yield chunk
    if outcome["failed"]:
        return

    all_sources = [s for sources in built.sources_store.values() for s in sources]
    if all_sources:
        await asyncio.to_thread(
            _save_turn_sources, db, int(thread_id), ai_turn_index, [s.model_dump() for s in all_sources]
        )

    thread_config = {"configurable": {"thread_id": thread_id}}
    snapshot = await built.graph.aget_state(thread_config)
    pending = [i for i in snapshot.interrupts if isinstance(i.value, dict) and i.value.get("kind") == APPROVAL_KIND]
    if pending:
        calls = await asyncio.to_thread(
            _record_pending_calls, db, agent_id, int(thread_id), pending, run_options, user_id
        )
        for call in calls:
            yield _sse("approval_required", ApprovalRequiredEvent(
                call_id=call.id, server=call.server_name, tool=call.tool,
                title=next((i.value.get("title") for i in pending if i.id == call.interrupt_id), None),
                args=call.args,
            ).model_dump())
        yield _sse("done", DoneEvent(finish_reason="approval_required").model_dump())
        return

    yield _sse("done", DoneEvent(finish_reason="stop").model_dump())
    final = snapshot.values
    messages = final.get("messages", [])
    if not messages or not isinstance(messages[-1], AIMessage) or count_answers(messages) != ai_turn_index + 1:
        return  # the run failed before answering — nothing to log
    answer = str(messages[-1].content)
    await asyncio.to_thread(
        _save_turn_log,
        db,
        agent_id,
        int(thread_id),
        ai_turn_index,
        question=question,
        query=final.get("query") or question,
        # Empty when a single-route agent skipped the supervisor.
        route=final.get("agent_type") or (built.routes[0] if len(built.routes) == 1 else None),
        # Distinct passages: a passage found by two searches shares one number.
        source_count=len({s.index for s in all_sources}),
        cited_count=cited_count(answer, all_sources),
    )


def _record_pending_calls(
    db: Session, agent_id: int, session_id: int, interrupts, run_options: dict, user_id: int | None
) -> list[McpToolCall]:
    """One pending McpToolCall per interrupt — once: a resume that leaves some
    undecided re-raises them under the same ids."""
    calls = []
    for intr in interrupts:
        call = db.execute(select(McpToolCall).where(McpToolCall.interrupt_id == intr.id)).scalar_one_or_none()
        if call is None:
            value = intr.value
            call = McpToolCall(
                agent_id=agent_id, session_id=session_id, server_id=value.get("server_id"),
                server_name=value.get("server_name", ""), tool=value.get("tool", ""), args=value.get("args") or {},
                status=ToolCallStatus.pending, interrupt_id=intr.id, run_options=run_options, requested_by=user_id,
            )
            db.add(call)
            db.commit()
            db.refresh(call)
        if call.status == ToolCallStatus.pending:
            calls.append(call)
    return calls


def pending_calls(db: Session, session_id: int) -> list[McpToolCall]:
    return list(
        db.execute(
            select(McpToolCall)
            .where(McpToolCall.session_id == session_id, McpToolCall.status == ToolCallStatus.pending)
            .order_by(McpToolCall.id)
        ).scalars()
    )


def expire_pending_calls(db: Session, session_id: int) -> None:
    """The conversation was edited past a paused run: its approvals can no longer apply."""
    for call in pending_calls(db, session_id):
        call.status = ToolCallStatus.expired
    db.commit()


async def session_resume_stream(
    db: Session,
    agent_id: int,
    thread_id: str,
    decisions: list[tuple[McpToolCall, bool, dict | None]],
    user_id: int | None,
) -> AsyncIterator[str]:
    """Resume a paused session turn with the user's decisions on its pending calls.

    `decisions` pairs each call with approve/reject and, optionally, edited
    arguments. The graph is rebuilt the way the paused run was started, so the
    node that paused exists again; LangGraph re-enters it and the tool's
    `interrupt()` returns the decision.
    """
    from app.agent.checkpoint import get_checkpointer

    options = decisions[0][0].run_options or {}
    try:
        built = await asyncio.to_thread(
            _build_graph, db, agent_id, options.get("top_k"), options.get("retrieval_mode"), user_id,
            get_checkpointer(), bool(options.get("regenerate")),
        )
    except ValueError as exc:
        yield _sse("error", ErrorEvent(error=str(exc)).model_dump())
        return

    thread_config = {"configurable": {"thread_id": thread_id}}
    state = await built.graph.aget_state(thread_config)
    messages = state.values.get("messages", [])
    question = next((str(m.content) for m in reversed(messages) if isinstance(m, HumanMessage)), "")

    resume = {}
    for call, approve, args in decisions:
        resume[call.interrupt_id] = {"decision": "approve" if approve else "reject", "args": args, "call_id": call.id}
    await asyncio.to_thread(_save_decisions, db, decisions, user_id)

    async for chunk in _finish_turn(
        db, built, agent_id, thread_id, Command(resume=resume), thread_config,
        count_answers(messages), question, options, user_id,
    ):
        yield chunk


def _save_decisions(db: Session, decisions: list[tuple[McpToolCall, bool, dict | None]], user_id: int | None) -> None:
    now = datetime.now(UTC)
    for call, approve, args in decisions:
        row = db.get(McpToolCall, call.id)
        row.status = ToolCallStatus.approved if approve else ToolCallStatus.rejected
        row.decided_by, row.decided_at = user_id, now
        if approve and args is not None and args != row.args:
            row.approved_args = args
    db.commit()

"""Multi-agent RAG graph: a supervisor routes each question to one sub-agent.

The graph is assembled per request from the agent's AgentConfig: which routes
exist, what the supervisor is told about each, and which model every node runs
on. With a single reachable route the supervisor is skipped entirely.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from pydantic import create_model
from sqlalchemy.orm import Session

from app.agent.agents import (
    make_comparison_agent,
    make_direct_agent,
    make_retrieval_agent,
    make_summary_agent,
)
from app.agent.config import resolve_document_scope, resolve_llm, resolve_pipeline_graph
from app.agent.context import conversation_window, make_prepare_node
from app.agent.delegation import DelegateInfo, make_delegate_tool, resolve_delegates
from app.agent.mcp import McpToolInfo, make_mcp_tools
from app.agent.state import MultiAgentState
from app.agent.tools import make_retrieval_tool
from app.core.config import get_settings
from app.db.models import Agent
from app.llm import get_chat_model
from app.rag.citation import CitationNumbering
from app.schemas.agent_config import AgentConfig, RetrievalMode
from app.schemas.chat import GraphEdge, GraphEvent, GraphNode

logger = logging.getLogger(__name__)

# LangGraph's own sentinel nodes. Drawn as the graph's endpoints, never reported
# as a step the run is "in".
GRAPH_START, GRAPH_END = "__start__", "__end__"
# First node of every run: compresses long history, rewrites follow-ups.
PREPARE_NODE = "prepare"


def _node_id(route: str) -> str:
    return f"{route}_agent"


# ── Supervisor ────────────────────────────────────────────────────────────────

def _make_supervisor_node(llm: BaseChatModel, routes: list[str], agent_cfg: AgentConfig):
    """Build a classifier constrained to exactly the routes this agent allows.

    The decision schema is generated per agent so the model cannot return a
    route that has no node — structured output enforces the Literal.
    """
    decision_model = create_model(
        "SupervisorDecision",
        agent_type=(Literal[tuple(routes)], ...),
    )
    prompt = (
        f"Classify the user's intent into one of {len(routes)} categories:\n"
        + "\n".join(f"- {name}: {agent_cfg.routes[name].description}" for name in routes)
    )

    async def supervisor_node(state: MultiAgentState) -> dict:
        classifier = llm.with_structured_output(decision_model)
        # The standalone rewrite, so a follow-up is classified by what it asks.
        query = state["query"]

        logger.debug("[supervisor] classifying query: %r", query[:120])
        result = await classifier.ainvoke([SystemMessage(prompt), HumanMessage(content=query)])
        logger.debug("[supervisor] → routed to agent_type=%r", result.agent_type)
        return {"agent_type": result.agent_type}

    return supervisor_node


# ── Sub-agent node wrapper ─────────────────────────────────────────────────────

def _react_recursion_limit(max_iterations: int) -> int:
    """Translate a tool-call budget into LangGraph's recursion limit.

    A ReAct round costs two super-steps (the model call, then the tool call), and
    one more step is needed for the final answer that follows the last tool
    result. Without this the agent loops until LangGraph's default of 25.
    """
    return max_iterations * 2 + 1


async def _seed_with_retrieval(messages: list, query: str, seed_tool, config: RunnableConfig) -> list:
    """Search with the user's question up front and attach the results to it.

    Waiting for the model to decide to search is what made small models stall:
    they would announce a search and stop, or print the call as text. Running the
    first search ourselves guarantees every answer starts from the documents.
    The context is folded into the question rather than sent as a synthetic tool
    call, so it works for every provider (Gemini rejects tool calls it didn't sign).
    Only this invocation sees the augmented question — the stored history keeps
    the user's original words. The search itself uses `query`, the standalone
    rewrite, so a follow-up like "그럼 마감은?" searches for what it means.
    """
    last_human = next((i for i in range(len(messages) - 1, -1, -1) if isinstance(messages[i], HumanMessage)), None)
    if last_human is None:
        return messages
    question = str(messages[last_human].content)
    # Invoked with the node's config so the tool's start/end events reach the
    # UI stream like any model-initiated search.
    context = await seed_tool.ainvoke({"query": query or question}, config=config)
    augmented = HumanMessage(
        content=(
            f"{question}\n\n<retrieved_context>\n{context or '(no matching documents)'}\n</retrieved_context>"
        )
    )
    return [*messages[:last_human], augmented, *messages[last_human + 1:]]


# Last resort when even the budget answer fails: no model left to word it in
# the user's language, so it says only what happened.
_BUDGET_FAILURE_MESSAGE = "검색 한도에 도달해 답변을 마무리하지 못했습니다. 다시 시도해 주세요."


async def _answer_within_budget(llm: BaseChatModel, system_prompt: str, messages: list, found: list[str]) -> AIMessage:
    """Write the final answer from what the searches found, without tools.

    Hitting the tool-call limit used to discard every search and tell the user to
    rephrase. The results are still good evidence; answer from them and name
    what is missing. Tool results go in as text inside the question, not as tool
    messages: with no tools bound, some providers reject a tool-call history.
    """
    extra = "\n\n".join(found) or "(no further results)"
    last = messages[-1]
    closing = HumanMessage(
        content=(
            f"{last.content}\n\n<additional_context>\n{extra}\n</additional_context>\n\n"
            "The search budget for this question is used up. Answer now from the context above, "
            "citing passage numbers like [1] as usual, and say plainly which parts of the question the documents did not cover."
        )
    )
    try:
        return await llm.ainvoke([SystemMessage(content=system_prompt), *messages[:-1], closing])
    except Exception as exc:
        logger.warning("budget answer failed: %s", exc)
        return AIMessage(content=_BUDGET_FAILURE_MESSAGE)


def _wrap_agent(agent, max_iterations: int, seed_tool=None, llm: BaseChatModel | None = None, system_prompt: str = ""):
    """Invoke a compiled ReAct agent and return only the final AI message."""
    async def node(state: MultiAgentState, config: RunnableConfig) -> dict:
        messages = conversation_window(state)
        logger.debug("[%s] starting (window_len=%d)", node.__qualname__, len(messages))
        if seed_tool is not None:
            messages = await _seed_with_retrieval(messages, state["query"], seed_tool, config)
        result: dict = {"messages": messages}
        try:
            # Streamed for its states so the searches made so far survive a
            # GraphRecursionError — ainvoke would lose them with the exception.
            async for values in agent.astream(
                {"messages": messages},
                config={"recursion_limit": _react_recursion_limit(max_iterations)},
                stream_mode="values",
            ):
                result = values
        except GraphRecursionError:
            logger.warning("[%s] hit the tool-call limit (max_iterations=%d)", node.__qualname__, max_iterations)
            found = [str(m.content) for m in result["messages"][len(messages):] if isinstance(m, ToolMessage)]
            return {"messages": [await _answer_within_budget(llm, system_prompt, messages, found)]}
        ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
        logger.debug("[%s] finished (output_msgs=%d)", node.__qualname__, len(ai_messages))
        return {"messages": ai_messages[-1:] if ai_messages else []}
    return node


def _wrap_comparison(comparison_graph):
    async def comparison_node(state: MultiAgentState) -> dict:
        result = await comparison_graph.ainvoke({
            "messages": conversation_window(state),
            "query": state["query"],
            "queries": [],
            "contexts": [],
        })
        ai_msgs = [m for m in result["messages"] if isinstance(m, AIMessage)]
        return {"messages": ai_msgs[-1:] if ai_msgs else []}
    return comparison_node


# ── Graph builder ─────────────────────────────────────────────────────────────

# Specialists that get the agent's tools (retrieval, plus any delegates).
# Comparison runs a fixed plan→retrieve→synthesize pipeline; direct uses none.
_TOOL_USING_ROUTES = ("retrieval", "summary")

_MCP_TOOLS_NOTE = """\
You can also act on external systems through the tools whose descriptions start
with a [server name]. When the user asks you to look something up there or to
change something (create, assign, close…), call the matching tool with the
details from the conversation. Never guess identifiers (equipment, order or
person IDs): look them up first with the read-only tools. Some actions are
approved by the user before
they run — call the tool anyway; the system asks them. Report what the tool
returned, including when the user rejected the action."""


@dataclass
class BuiltGraph:
    graph: Any  # the compiled LangGraph
    # query → sources found, filled as the retrieval tool runs; the stream reads
    # it to attach citations to each search.
    sources_store: dict
    delegates: list[DelegateInfo] = field(default_factory=list)
    # The routes this run could take; with one, the supervisor is skipped.
    routes: list[str] = field(default_factory=list)
    mcp_tools: list[McpToolInfo] = field(default_factory=list)

    def topology(self) -> GraphEvent:
        return graph_topology(self.graph, self.delegates, self.mcp_tools)


def build_multi_agent_graph(
    db: Session,
    agent: Agent,
    agent_cfg: AgentConfig,
    system_prompt: str,
    retrieval_mode: RetrievalMode,
    top_k: int | None = None,
    checkpointer=None,
    llm: BaseChatModel | None = None,
    user_id: int | None = None,
    allow_delegates: bool = True,
    answer_temperature: float | None = None,
    interactive: bool = False,
) -> BuiltGraph:
    """Assemble the graph one run of `agent` executes, configured by `agent_cfg`.

    The config is passed separately from the agent so a draft can be previewed
    or evaluated without saving it. `llm` overrides the agent's model — the settings preview passes the default
    one, since the shape doesn't depend on the model and a draft config may name
    a provider with no key yet. `allow_delegates=False` is how a delegate is
    built, keeping delegation one level deep.

    `answer_temperature` raises the temperature of the model that writes the
    answer (a regenerate). The query rewrite and the supervisor keep the agent's
    own, so the same question still finds the same documents.

    `interactive` marks a run that can pause and be resumed (a chat session
    with a checkpointer); only such a run gets MCP tools that need approval.
    """
    settings = get_settings()
    answer_llm = llm
    if llm is None:
        llm_cfg = resolve_llm(agent_cfg)
        llm = get_chat_model(llm_cfg)
        answer_llm = llm
        if answer_temperature is not None and answer_temperature > llm_cfg.temperature:
            answer_llm = get_chat_model(llm_cfg.model_copy(update={"temperature": answer_temperature}))
    max_iterations = agent_cfg.max_iterations or settings.agent.max_iterations
    routes = agent_cfg.active_routes(retrieval_mode)

    # One store and one numbering per turn, shared by the retrieval tool and the
    # delegate tools, so every source of the answer is cited in one sequence.
    sources_store: dict = {}
    numbering = CitationNumbering()
    retrieval_tool = None
    if any(route != "direct" for route in routes):
        retrieval_tool = make_retrieval_tool(
            db,
            agent.workspace_id,
            top_k or agent_cfg.top_k or settings.chat.default_top_k,
            resolve_pipeline_graph(db, agent.workspace_id, agent_cfg),
            resolve_document_scope(db, agent.workspace_id, agent_cfg),
            sources_store=sources_store,
            numbering=numbering,
        )

    delegate_tools: list = []
    delegates: list[DelegateInfo] = []
    if allow_delegates and agent_cfg.delegates and any(r in _TOOL_USING_ROUTES for r in routes):
        for delegate in resolve_delegates(db, agent.id, agent_cfg.delegates, user_id):
            tool, info = make_delegate_tool(db, delegate, sources_store, numbering)
            delegate_tools.append(tool)
            delegates.append(info)

    mcp_tools, mcp_infos = make_mcp_tools(db, agent, agent_cfg, user_id, interactive)
    if mcp_tools:
        system_prompt = f"{system_prompt}\n\n{_MCP_TOOLS_NOTE}"

    agent_tools = ([retrieval_tool] if retrieval_tool is not None else []) + delegate_tools + mcp_tools

    graph = StateGraph(MultiAgentState)
    for route in routes:
        if route in ("retrieval", "summary"):
            make = make_retrieval_agent if route == "retrieval" else make_summary_agent
            specialist = make(answer_llm, agent_tools, system_prompt)
            node = _wrap_agent(
                specialist.agent,
                max_iterations,
                seed_tool=retrieval_tool,
                llm=answer_llm,
                system_prompt=specialist.system_prompt,
            )
        elif route == "comparison":
            node = _wrap_comparison(make_comparison_agent(answer_llm, retrieval_tool, system_prompt))
        else:
            node = _wrap_agent(make_direct_agent(answer_llm, system_prompt, mcp_tools), max_iterations)
        graph.add_node(_node_id(route), node)
        graph.add_edge(_node_id(route), END)

    graph.add_node(
        PREPARE_NODE,
        make_prepare_node(llm, settings.agent.history_max_tokens, settings.agent.history_keep_messages),
    )
    graph.add_edge(START, PREPARE_NODE)
    if len(routes) == 1:
        # Nothing to decide — skip the supervisor and its extra LLM call.
        graph.add_edge(PREPARE_NODE, _node_id(routes[0]))
    else:
        graph.add_node("supervisor", _make_supervisor_node(llm, routes, agent_cfg))
        graph.add_edge(PREPARE_NODE, "supervisor")
        graph.add_conditional_edges(
            "supervisor",
            lambda s: s["agent_type"],
            {route: _node_id(route) for route in routes},
        )

    return BuiltGraph(graph.compile(checkpointer=checkpointer), sources_store, delegates, routes, mcp_infos)


# ── Topology for the UI ───────────────────────────────────────────────────────

def _node_kind(node_id: str) -> str:
    if node_id == GRAPH_START:
        return "entry"
    if node_id == GRAPH_END:
        return "exit"
    if node_id == "supervisor":
        return "supervisor"
    if node_id == PREPARE_NODE:
        return "step"
    return "agent"


def _node_label(node_id: str) -> str:
    if node_id in (GRAPH_START, GRAPH_END):
        return node_id.strip("_")
    # "retrieval_agent" → "retrieval": the node's kind already marks it as an
    # agent, and short labels keep the graph legible in a narrow side panel.
    return node_id.removesuffix("_agent").replace("_", " ")


def graph_node_ids(graph) -> set[str]:
    """The graph's real nodes — the ones a run can be "in"."""
    return set(graph.get_graph().nodes) - {GRAPH_START, GRAPH_END}


def graph_topology(
    graph, delegates: list[DelegateInfo] | None = None, mcp_tools: list[McpToolInfo] | None = None
) -> GraphEvent:
    """Read the compiled graph's shape so the UI can draw it.

    Derived from the graph itself rather than hardcoded, so it stays correct as
    routes are toggled or the retrieval mode changes the wiring. Delegates aren't
    graph nodes — they're tools — so they're added as their own kind, joined to
    the specialists that can call them by tool edges.
    """
    drawable = graph.get_graph()
    nodes = [
        GraphNode(id=node_id, label=_node_label(node_id), kind=_node_kind(node_id))
        for node_id in drawable.nodes
    ]
    edges = [
        GraphEdge(
            source=edge.source,
            target=edge.target,
            label=edge.data if isinstance(edge.data, str) else None,
            conditional=bool(edge.conditional),
        )
        for edge in drawable.edges
    ]
    callers = [_node_id(route) for route in _TOOL_USING_ROUTES if _node_id(route) in drawable.nodes]
    for info in delegates or []:
        nodes.append(GraphNode(id=info.node_id, label=info.name, kind="delegate"))
        edges.extend(GraphEdge(source=caller, target=info.node_id, tool=True) for caller in callers)
    # One node per MCP server, joined to every specialist that holds its tools.
    mcp_callers = callers + ([_node_id("direct")] if _node_id("direct") in drawable.nodes else [])
    for server_id, server_name in dict.fromkeys((t.server_id, t.server_name) for t in mcp_tools or []):
        node_id = f"mcp:{server_id}"
        nodes.append(GraphNode(id=node_id, label=server_name, kind="mcp"))
        edges.extend(GraphEdge(source=caller, target=node_id, tool=True) for caller in mcp_callers)
    return GraphEvent(nodes=nodes, edges=edges)

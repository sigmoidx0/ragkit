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
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
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
from app.agent.config import resolve_llm, resolve_pipeline_graph
from app.agent.delegation import DelegateInfo, make_delegate_tool, resolve_delegates
from app.agent.state import MultiAgentState
from app.agent.tools import make_retrieval_tool
from app.core.config import get_settings
from app.llm import get_chat_model
from app.schemas.agent_config import AgentConfig, RetrievalMode
from app.schemas.chat import GraphEdge, GraphEvent, GraphNode

logger = logging.getLogger(__name__)

# LangGraph's own sentinel nodes. Drawn as the graph's endpoints, never reported
# as a step the run is "in".
GRAPH_START, GRAPH_END = "__start__", "__end__"


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
        user_msgs = [m for m in state["messages"] if isinstance(m, HumanMessage)]
        last = str(user_msgs[-1].content) if user_msgs else ""

        logger.debug("[supervisor] classifying query: %r", last[:120])
        result = await classifier.ainvoke([SystemMessage(prompt), HumanMessage(content=last)])
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


async def _seed_with_retrieval(messages: list, seed_tool, config: RunnableConfig) -> list:
    """Search with the user's question up front and attach the results to it.

    Waiting for the model to decide to search is what made small models stall:
    they would announce a search and stop, or print the call as text. Running the
    first search ourselves guarantees every answer starts from the documents.
    The context is folded into the question rather than sent as a synthetic tool
    call, so it works for every provider (Gemini rejects tool calls it didn't sign).
    Only this invocation sees the augmented question — the stored history keeps
    the user's original words.
    """
    last_human = next((i for i in range(len(messages) - 1, -1, -1) if isinstance(messages[i], HumanMessage)), None)
    if last_human is None:
        return messages
    question = str(messages[last_human].content)
    # Invoked with the node's config so the tool's start/end events reach the
    # UI stream like any model-initiated search.
    context = await seed_tool.ainvoke({"query": question}, config=config)
    augmented = HumanMessage(
        content=(
            f"{question}\n\n<retrieved_context>\n{context or '(no matching documents)'}\n</retrieved_context>"
        )
    )
    return [*messages[:last_human], augmented, *messages[last_human + 1:]]


def _wrap_agent(agent, max_iterations: int, seed_tool=None):
    """Invoke a compiled ReAct agent and return only the final AI message."""
    async def node(state: MultiAgentState, config: RunnableConfig) -> dict:
        logger.debug("[%s] starting (history_len=%d)", node.__qualname__, len(state["messages"]))
        messages = state["messages"]
        if seed_tool is not None:
            messages = await _seed_with_retrieval(messages, seed_tool, config)
        try:
            result = await agent.ainvoke(
                {"messages": messages},
                config={"recursion_limit": _react_recursion_limit(max_iterations)},
            )
        except GraphRecursionError:
            # The agent kept calling tools past its budget. Say so plainly rather
            # than surfacing a LangGraph traceback to the user.
            logger.warning("[%s] hit the tool-call limit (max_iterations=%d)", node.__qualname__, max_iterations)
            return {
                "messages": [
                    AIMessage(
                        content=(
                            "검색을 반복했지만 충분한 근거를 찾지 못했습니다. "
                            "질문을 더 구체적으로 작성해 주세요."
                        )
                    )
                ]
            }
        ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
        logger.debug("[%s] finished (output_msgs=%d)", node.__qualname__, len(ai_messages))
        return {"messages": ai_messages[-1:] if ai_messages else []}
    return node


def _wrap_comparison(comparison_graph):
    async def comparison_node(state: MultiAgentState) -> dict:
        result = await comparison_graph.ainvoke({
            "messages": state["messages"],
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


@dataclass
class BuiltGraph:
    graph: Any  # the compiled LangGraph
    # query → sources found, filled as the retrieval tool runs; the stream reads
    # it to attach citations to each search.
    sources_store: dict
    delegates: list[DelegateInfo] = field(default_factory=list)

    def topology(self) -> GraphEvent:
        return graph_topology(self.graph, self.delegates)


def build_multi_agent_graph(
    db: Session,
    service_id: int,
    agent_cfg: AgentConfig,
    system_prompt: str,
    retrieval_mode: RetrievalMode,
    top_k: int | None = None,
    checkpointer=None,
    llm: BaseChatModel | None = None,
    user_id: int | None = None,
    allow_delegates: bool = True,
) -> BuiltGraph:
    """Assemble the graph one run of this agent executes.

    `llm` overrides the agent's model — the settings preview passes the default
    one, since the shape doesn't depend on the model and a draft config may name
    a provider with no key yet. `allow_delegates=False` is how a delegate is
    built, keeping delegation one level deep.
    """
    settings = get_settings()
    llm = llm or get_chat_model(resolve_llm(agent_cfg))
    max_iterations = agent_cfg.max_iterations or settings.agent.max_iterations
    routes = agent_cfg.active_routes(retrieval_mode)

    sources_store: dict = {}
    retrieval_tool = None
    if any(route != "direct" for route in routes):
        retrieval_tool, sources_store = make_retrieval_tool(
            db,
            service_id,
            top_k or agent_cfg.top_k or settings.chat.default_top_k,
            resolve_pipeline_graph(db, service_id, agent_cfg),
        )

    delegate_tools: list = []
    delegates: list[DelegateInfo] = []
    if allow_delegates and agent_cfg.delegates and any(r in _TOOL_USING_ROUTES for r in routes):
        for service in resolve_delegates(db, service_id, agent_cfg.delegates, user_id):
            tool, info = make_delegate_tool(db, service)
            delegate_tools.append(tool)
            delegates.append(info)

    agent_tools = ([retrieval_tool] if retrieval_tool is not None else []) + delegate_tools

    graph = StateGraph(MultiAgentState)
    for route in routes:
        if route == "retrieval":
            node = _wrap_agent(
                make_retrieval_agent(llm, agent_tools, system_prompt), max_iterations, seed_tool=retrieval_tool
            )
        elif route == "summary":
            node = _wrap_agent(
                make_summary_agent(llm, agent_tools, system_prompt), max_iterations, seed_tool=retrieval_tool
            )
        elif route == "comparison":
            node = _wrap_comparison(make_comparison_agent(llm, retrieval_tool, system_prompt))
        else:
            node = _wrap_agent(make_direct_agent(llm, system_prompt), max_iterations)
        graph.add_node(_node_id(route), node)
        graph.add_edge(_node_id(route), END)

    if len(routes) == 1:
        # Nothing to decide — skip the supervisor and its extra LLM call.
        graph.add_edge(START, _node_id(routes[0]))
    else:
        graph.add_node("supervisor", _make_supervisor_node(llm, routes, agent_cfg))
        graph.add_edge(START, "supervisor")
        graph.add_conditional_edges(
            "supervisor",
            lambda s: s["agent_type"],
            {route: _node_id(route) for route in routes},
        )

    return BuiltGraph(graph.compile(checkpointer=checkpointer), sources_store, delegates)


# ── Topology for the UI ───────────────────────────────────────────────────────

def _node_kind(node_id: str) -> str:
    if node_id == GRAPH_START:
        return "entry"
    if node_id == GRAPH_END:
        return "exit"
    if node_id == "supervisor":
        return "supervisor"
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


def graph_topology(graph, delegates: list[DelegateInfo] | None = None) -> GraphEvent:
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
    return GraphEvent(nodes=nodes, edges=edges)

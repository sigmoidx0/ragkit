"""Multi-agent RAG graph: Supervisor routes to Retrieval / Summary / Comparison agent."""

from __future__ import annotations

import logging
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agent.agents import make_comparison_agent, make_direct_agent, make_retrieval_agent, make_summary_agent
from app.agent.state import MultiAgentState
from app.agent.tools import make_retrieval_tool
from app.llm import get_chat_model
from app.schemas.chat import SourceItem

logger = logging.getLogger(__name__)


# ── Supervisor ────────────────────────────────────────────────────────────────

class _SupervisorDecisionOn(BaseModel):
    agent_type: Literal["retrieval", "summary", "comparison"]


class _SupervisorDecisionAuto(BaseModel):
    agent_type: Literal["retrieval", "summary", "comparison", "direct"]


_SUPERVISOR_PROMPT_ON = (
    "Classify the user's intent into one of three categories:\n"
    "- retrieval: factual questions, definitions, explanations\n"
    "- summary: requests to summarize a topic or document\n"
    "- comparison: requests to compare, contrast, or differentiate items"
)

_SUPERVISOR_PROMPT_AUTO = (
    "Classify the user's intent into one of four categories:\n"
    "- retrieval: factual questions, definitions, explanations\n"
    "- summary: requests to summarize a topic or document\n"
    "- comparison: requests to compare, contrast, or differentiate items\n"
    "- direct: conversational messages, greetings, or questions that clearly don't require document lookup"
)


def _make_supervisor_node(retrieval_mode: str = "on"):
    is_auto = retrieval_mode == "auto"
    DecisionModel = _SupervisorDecisionAuto if is_auto else _SupervisorDecisionOn
    prompt = _SUPERVISOR_PROMPT_AUTO if is_auto else _SUPERVISOR_PROMPT_ON

    async def supervisor_node(state: MultiAgentState) -> dict:
        llm = get_chat_model().with_structured_output(DecisionModel)
        user_msgs = [m for m in state["messages"] if isinstance(m, HumanMessage)]
        last = str(user_msgs[-1].content) if user_msgs else ""

        logger.debug("[supervisor] classifying query: %r", last[:120])
        result = await llm.ainvoke([
            SystemMessage(prompt),
            HumanMessage(content=last),
        ])
        logger.debug("[supervisor] → routed to agent_type=%r", result.agent_type)
        return {"agent_type": result.agent_type}

    return supervisor_node


# ── Sub-agent node wrapper ─────────────────────────────────────────────────────

def _wrap_agent(agent):
    """Invoke a compiled ReAct agent and return only the final AI message."""
    async def node(state: MultiAgentState) -> dict:
        logger.debug("[%s] starting (history_len=%d)", node.__qualname__, len(state["messages"]))
        result = await agent.ainvoke({"messages": state["messages"]})
        ai_messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
        logger.debug("[%s] finished (output_msgs=%d)", node.__qualname__, len(ai_messages))
        return {"messages": ai_messages[-1:] if ai_messages else []}
    return node


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_multi_agent_graph(
    db: Session,
    service_id: int,
    top_k: int,
    system_prompt: str,
    retrieval_mode: str = "on",
    checkpointer=None,
) -> tuple:
    """Return (compiled_graph, sources_store)."""
    graph = StateGraph(MultiAgentState)

    if retrieval_mode == "off":
        graph.add_node("direct_agent", _wrap_agent(make_direct_agent(system_prompt)))
        graph.add_edge(START, "direct_agent")
        graph.add_edge("direct_agent", END)
        return graph.compile(checkpointer=checkpointer), {}

    retrieval_tool, sources_store = make_retrieval_tool(db, service_id, top_k)

    graph.add_node("supervisor", _make_supervisor_node(retrieval_mode))
    graph.add_node("retrieval_agent",  _wrap_agent(make_retrieval_agent(retrieval_tool, system_prompt)))
    graph.add_node("summary_agent",    _wrap_agent(make_summary_agent(retrieval_tool, system_prompt)))
    graph.add_node("comparison_agent", _wrap_agent(make_comparison_agent(retrieval_tool, system_prompt)))

    routing = {
        "retrieval":  "retrieval_agent",
        "summary":    "summary_agent",
        "comparison": "comparison_agent",
    }

    if retrieval_mode == "auto":
        graph.add_node("direct_agent", _wrap_agent(make_direct_agent(system_prompt)))
        routing["direct"] = "direct_agent"
        graph.add_edge("direct_agent", END)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges("supervisor", lambda s: s["agent_type"], routing)
    for node in ("retrieval_agent", "summary_agent", "comparison_agent"):
        graph.add_edge(node, END)

    return graph.compile(checkpointer=checkpointer), sources_store

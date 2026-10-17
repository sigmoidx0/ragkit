"""Three specialized sub-agents: Retrieval, Summary, Comparison."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Annotated, Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel
from typing_extensions import TypedDict

from app.agent.delegation import DELEGATE_TOOL_PREFIX
from app.agent.recovery import make_tool_call_recovery_hook

# Tags an LLM call whose output is machinery, not answer text — a structured
# plan, a classification. The stream skips tokens from calls carrying it, so a
# planner's JSON never flashes up in the chat bubble.
INTERNAL_LLM_TAG = "ragkit:internal"

_LANGUAGE_RULE = "Always respond in the same language as the user's question. If the user asks in Korean, respond in Korean."

# Retrieval and summary agents receive the results of an initial search along
# with the question (see graph._seeded_agent_node), so they never depend on the
# model choosing to call a tool before it can answer anything.
_RETRIEVAL_ROLE = """\
You are a retrieval specialist. The user's question arrives with context from an
initial document search, inside <retrieved_context> tags.
Never answer from your own knowledge or memory.
1. Answer based solely on the retrieved context, citing each fact with its passage number, like [1] or [2][3].
2. Only if that context is insufficient, call the retrieval tool with a different, more specific query.
If the documents do not contain enough information, say so clearly.
""" + _LANGUAGE_RULE

_SUMMARY_ROLE = """\
You are a summarization specialist. The user's question arrives with context from an
initial document search, inside <retrieved_context> tags.
Never answer from your own knowledge or memory.
1. If the context misses parts of the topic, call the retrieval tool with other angles of it.
2. Write a comprehensive, well-structured summary with clear sections and bullet points,
   citing each fact with its passage number, like [1] or [2][3].
If the documents do not contain enough information, say so clearly.
""" + _LANGUAGE_RULE

_COMPARISON_ROLE = """\
You are a comparison specialist. You MUST call the retrieval tool BEFORE writing any response.
Never answer from your own knowledge or memory.
Steps you must follow:
1. Call the retrieval tool once per item being compared.
2. Read all retrieved context.
3. Present the comparison in a structured format (sections or a table) \
highlighting similarities and differences.
If the retrieved context does not contain enough information, say so clearly.
""" + _LANGUAGE_RULE


def _delegation_prompt(tools: list[BaseTool]) -> str:
    """Spell out the delegate tools, and that they must actually be called.

    Without this, small models reply "I should ask the manufacturing agent" and
    stop — announcing the hand-off instead of making it.
    """
    delegates = [t for t in tools if t.name.startswith(DELEGATE_TOOL_PREFIX)]
    if not delegates:
        return ""
    listing = "\n".join(f"- {t.name}: {t.description}" for t in delegates)
    return (
        "\n\nYou can consult other agents through these tools:\n"
        f"{listing}\n"
        "When the question belongs to one of their domains, or the user asks you to consult one, "
        "call that tool yourself and answer from its reply. Never tell the user to ask another agent, "
        "and never say you will ask one without calling the tool in the same turn. "
        "Never mention tool names to the user — refer to the other agent by its name. "
        "Its reply cites passages with numbers like [4], counted alongside your own search results; "
        "keep those exact numbers on the facts you take from it."
    )


@dataclass(frozen=True)
class Specialist:
    agent: Any  # the compiled ReAct agent
    # Its full system prompt, kept so a final answer can be written without the
    # agent when it runs out of tool calls (see graph._answer_within_budget).
    system_prompt: str


def _make_agent(llm: BaseChatModel, tools: list[BaseTool], role_prompt: str, base_system_prompt: str) -> Specialist:
    system_prompt = f"{base_system_prompt}\n\n{role_prompt}{_delegation_prompt(tools)}"
    agent = create_react_agent(
        llm,
        tools,
        prompt=SystemMessage(content=system_prompt),
        post_model_hook=make_tool_call_recovery_hook({t.name for t in tools}),
    )
    return Specialist(agent, system_prompt)


def make_retrieval_agent(llm: BaseChatModel, tools: list[BaseTool], base_system_prompt: str) -> Specialist:
    return _make_agent(llm, tools, _RETRIEVAL_ROLE, base_system_prompt)


def make_summary_agent(llm: BaseChatModel, tools: list[BaseTool], base_system_prompt: str) -> Specialist:
    return _make_agent(llm, tools, _SUMMARY_ROLE, base_system_prompt)


class _ComparisonPlan(BaseModel):
    queries: list[str]


class _ComparisonState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    query: str  # the question rewritten to stand alone (see app/agent/context.py)
    queries: list[str]
    contexts: list[str]


def make_comparison_agent(llm: BaseChatModel, retrieval_tool: BaseTool, base_system_prompt: str):
    system_prompt = f"{base_system_prompt}\n\n{_COMPARISON_ROLE}"

    async def plan(state: _ComparisonState) -> dict:
        planner = llm.with_structured_output(_ComparisonPlan).with_config(tags=[INTERNAL_LLM_TAG])
        result = await planner.ainvoke([
            SystemMessage(content="Generate one focused search query per item being compared."),
            HumanMessage(content=state["query"]),
        ])
        return {"queries": result.queries}

    async def retrieve(state: _ComparisonState, config: RunnableConfig) -> dict:
        tasks = [retrieval_tool.ainvoke({"query": q}, config=config) for q in state["queries"]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {"contexts": [r if isinstance(r, str) else "" for r in results]}

    async def synthesize(state: _ComparisonState) -> dict:
        context_block = "\n\n---\n\n".join(
            f"[Query: {q}]\n{ctx}"
            for q, ctx in zip(state["queries"], state["contexts"], strict=True)
        )
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            *state["messages"],
            HumanMessage(content=f"Retrieved context:\n\n{context_block}"),
        ])
        return {"messages": [response]}

    g = StateGraph(_ComparisonState)
    g.add_node("plan", plan)
    g.add_node("retrieve", retrieve)
    g.add_node("synthesize", synthesize)
    g.add_edge(START, "plan")
    g.add_edge("plan", "retrieve")
    g.add_edge("retrieve", "synthesize")
    g.add_edge("synthesize", END)
    return g.compile()


_DIRECT_ROLE = """\
You are a helpful assistant. Answer the user's question directly using your own knowledge.
""" + _LANGUAGE_RULE


def make_direct_agent(llm: BaseChatModel, base_system_prompt: str, tools: list[BaseTool] | None = None):
    """No document lookup — but an agent's MCP tools still reach external systems from here."""
    system_prompt = f"{base_system_prompt}\n\n{_DIRECT_ROLE}"
    tools = tools or []
    return create_react_agent(
        llm,
        tools,
        prompt=SystemMessage(content=system_prompt),
        post_model_hook=make_tool_call_recovery_hook({t.name for t in tools}) if tools else None,
    )

"""Three specialized sub-agents: Retrieval, Summary, Comparison."""

from __future__ import annotations

import asyncio
from typing import Annotated

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel
from typing_extensions import TypedDict

from app.llm import get_chat_model

_LANGUAGE_RULE = "Always respond in the same language as the user's question. If the user asks in Korean, respond in Korean."

_RETRIEVAL_ROLE = """\
You are a retrieval specialist. You MUST call the retrieval tool BEFORE writing any response.
Never answer from your own knowledge or memory.
Steps you must follow:
1. Call the retrieval tool with a concise query derived from the user's question.
2. Read the retrieved context.
3. Answer based solely on that context, citing sources inline using [N] notation.
If the retrieved context does not contain enough information, say so clearly.
""" + _LANGUAGE_RULE

_SUMMARY_ROLE = """\
You are a summarization specialist. You MUST call the retrieval tool BEFORE writing any response.
Never answer from your own knowledge or memory.
Steps you must follow:
1. Call the retrieval tool multiple times with varied queries to gather complete information.
2. Read all retrieved context.
3. Write a comprehensive, well-structured summary with clear sections and bullet points.
If the retrieved context does not contain enough information, say so clearly.
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


def _make_agent(retrieval_tool: BaseTool, role_prompt: str, base_system_prompt: str):
    system_prompt = f"{base_system_prompt}\n\n{role_prompt}"
    return create_react_agent(
        get_chat_model(),
        [retrieval_tool],
        prompt=SystemMessage(content=system_prompt),
    )


def make_retrieval_agent(retrieval_tool: BaseTool, base_system_prompt: str):
    return _make_agent(retrieval_tool, _RETRIEVAL_ROLE, base_system_prompt)


def make_summary_agent(retrieval_tool: BaseTool, base_system_prompt: str):
    return _make_agent(retrieval_tool, _SUMMARY_ROLE, base_system_prompt)


class _ComparisonPlan(BaseModel):
    queries: list[str]


class _ComparisonState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    queries: list[str]
    contexts: list[str]


def make_comparison_agent(retrieval_tool: BaseTool, base_system_prompt: str):
    system_prompt = f"{base_system_prompt}\n\n{_COMPARISON_ROLE}"

    async def plan(state: _ComparisonState) -> dict:
        llm = get_chat_model().with_structured_output(_ComparisonPlan)
        user_msgs = [m for m in state["messages"] if isinstance(m, HumanMessage)]
        result = await llm.ainvoke([
            SystemMessage(content="Generate one focused search query per item being compared."),
            user_msgs[-1],
        ])
        return {"queries": result.queries}

    async def retrieve(state: _ComparisonState, config: RunnableConfig) -> dict:
        tasks = [retrieval_tool.ainvoke({"query": q}, config=config) for q in state["queries"]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {"contexts": [r if isinstance(r, str) else "" for r in results]}

    async def synthesize(state: _ComparisonState) -> dict:
        context_block = "\n\n---\n\n".join(
            f"[Query: {q}]\n{ctx}"
            for q, ctx in zip(state["queries"], state["contexts"])
        )
        response = await get_chat_model().ainvoke([
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


def make_direct_agent(base_system_prompt: str):
    system_prompt = f"{base_system_prompt}\n\n{_DIRECT_ROLE}"
    return create_react_agent(
        get_chat_model(),
        [],
        prompt=SystemMessage(content=system_prompt),
    )

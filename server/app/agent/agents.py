"""Three specialized sub-agents: Retrieval, Summary, Comparison."""

from __future__ import annotations

from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from app.llm import get_chat_model

_RETRIEVAL_ROLE = """\
You are a retrieval specialist. You MUST call the retrieval tool BEFORE writing any response.
Never answer from your own knowledge or memory.
Steps you must follow:
1. Call the retrieval tool with a concise query derived from the user's question.
2. Read the retrieved context.
3. Answer based solely on that context, citing sources inline using [N] notation.
If the retrieved context does not contain enough information, say so clearly."""

_SUMMARY_ROLE = """\
You are a summarization specialist. You MUST call the retrieval tool BEFORE writing any response.
Never answer from your own knowledge or memory.
Steps you must follow:
1. Call the retrieval tool multiple times with varied queries to gather complete information.
2. Read all retrieved context.
3. Write a comprehensive, well-structured summary with clear sections and bullet points.
If the retrieved context does not contain enough information, say so clearly."""

_COMPARISON_ROLE = """\
You are a comparison specialist. You MUST call the retrieval tool BEFORE writing any response.
Never answer from your own knowledge or memory.
Steps you must follow:
1. Call the retrieval tool once per item being compared.
2. Read all retrieved context.
3. Present the comparison in a structured format (sections or a table) \
highlighting similarities and differences.
If the retrieved context does not contain enough information, say so clearly."""


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


def make_comparison_agent(retrieval_tool: BaseTool, base_system_prompt: str):
    return _make_agent(retrieval_tool, _COMPARISON_ROLE, base_system_prompt)

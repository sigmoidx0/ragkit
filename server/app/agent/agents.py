"""Three specialized sub-agents: Retrieval, Summary, Comparison."""

from __future__ import annotations

from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent

from app.llm import get_chat_model

_RETRIEVAL_ROLE = """\
You are a retrieval specialist. Answer the user's question accurately \
based on documents retrieved from the knowledge base.
Use the retrieval tool to find relevant information. \
Cite sources inline using [N] notation (e.g. "According to the policy [1], ...").
If the knowledge base does not contain enough information, say so clearly."""

_SUMMARY_ROLE = """\
You are a summarization specialist. Produce a comprehensive, well-structured summary.
Use the retrieval tool multiple times with varied queries to gather complete information \
before writing the summary.
Organize the output with clear sections and bullet points where appropriate."""

_COMPARISON_ROLE = """\
You are a comparison specialist. Compare and contrast topics or entities systematically.
Use the retrieval tool multiple times — once per item being compared — to gather information.
Present the comparison in a structured format (sections or a table) \
highlighting similarities and differences."""


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

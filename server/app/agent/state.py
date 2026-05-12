from __future__ import annotations

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class MultiAgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    agent_type: str  # set by supervisor: "retrieval" | "summary" | "comparison"

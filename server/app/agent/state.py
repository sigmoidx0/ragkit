from __future__ import annotations

from langgraph.graph import MessagesState


class MultiAgentState(MessagesState):
    agent_type: str  # set by supervisor: "retrieval" | "summary" | "comparison"

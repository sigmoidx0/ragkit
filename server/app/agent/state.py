from __future__ import annotations

from langgraph.graph import MessagesState


class MultiAgentState(MessagesState):
    agent_type: str  # set by supervisor: "retrieval" | "summary" | "comparison"
    # This turn's question rewritten to stand alone; what routing and search act on.
    query: str
    # Running summary of the older messages, and how many leading messages of
    # `messages` it covers. Persisted by the checkpointer like `messages`.
    summary: str
    summarized: int

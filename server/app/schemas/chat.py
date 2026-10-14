from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    top_k: int | None = None
    # None uses the agent's configured default_retrieval_mode.
    retrieval_mode: Literal["on", "off", "auto"] | None = None


# ── SSE event payloads ───────────────────────────────────────────────────────

class SourceItem(BaseModel):
    index: int
    document_id: int
    title: str | None
    snippet: str
    score: float


class AgentStepEvent(BaseModel):
    type: Literal["tool_call", "observation"]
    tool: str
    input: str | None = None          # populated on tool_call
    output: list[SourceItem] | None = None  # populated on observation


class TokenEvent(BaseModel):
    delta: str


class UsageInfo(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None


class DoneEvent(BaseModel):
    finish_reason: str
    usage: UsageInfo | None = None


class SupervisorRouteEvent(BaseModel):
    agent_type: Literal["retrieval", "summary", "comparison"]


class GraphNode(BaseModel):
    id: str
    label: str
    # "entry"/"exit" are LangGraph's __start__/__end__ sentinels; "supervisor"
    # routes, "agent" does the work. The UI styles each kind differently.
    kind: Literal["entry", "exit", "supervisor", "agent", "delegate"]


class GraphEdge(BaseModel):
    source: str
    target: str
    label: str | None = None  # route name, on conditional edges only
    conditional: bool = False
    # A tool edge: the source agent may call the target (a delegate agent) as a
    # tool, rather than handing control to it.
    tool: bool = False


class GraphEvent(BaseModel):
    """The shape of the graph for this run, sent once before execution starts."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


class NodeStateEvent(BaseModel):
    """Which node the run is in right now, so the UI can highlight it."""

    node: str
    status: Literal["running", "done"]


class DelegateStateEvent(BaseModel):
    """Progress inside a delegate agent, drawn nested within its node."""

    delegate: str  # the delegate's node id, "delegate:<agent id>"
    node: str  # a node of the delegate's own graph
    status: Literal["running", "done"]


class ErrorEvent(BaseModel):
    error: str


# ── Session schemas ──────────────────────────────────────────────────────────

class ChatSessionCreate(BaseModel):
    title: str | None = None


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_id: int
    title: str | None
    created_at: datetime
    updated_at: datetime


class FeedbackIn(BaseModel):
    rating: Literal[1, -1]
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackOut(BaseModel):
    rating: Literal[1, -1]
    comment: str | None = None


class SessionMessageResponse(BaseModel):
    role: str
    content: str
    sources: list[SourceItem] = Field(default_factory=list)
    # Assistant messages only: which answer this is, and how the user rated it.
    turn_index: int | None = None
    feedback: FeedbackOut | None = None


class SessionChatRequest(BaseModel):
    message: str = Field(min_length=1)
    top_k: int | None = None
    # None uses the agent's configured default_retrieval_mode.
    retrieval_mode: Literal["on", "off", "auto"] | None = None

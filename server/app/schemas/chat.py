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
    filters: dict | None = None
    retrieval_mode: Literal["on", "off", "auto"] = "on"


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


class SessionMessageResponse(BaseModel):
    role: str
    content: str
    sources: list[SourceItem] = Field(default_factory=list)


class SessionChatRequest(BaseModel):
    message: str = Field(min_length=1)
    top_k: int | None = None
    filters: dict | None = None
    retrieval_mode: Literal["on", "off", "auto"] = "on"

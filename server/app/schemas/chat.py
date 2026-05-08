from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    top_k: int | None = None
    filters: dict | None = None


# ── SSE event payloads ───────────────────────────────────────────────────────

class SourceItem(BaseModel):
    index: int
    document_id: int
    title: str | None
    snippet: str
    score: float


class RetrievalStartEvent(BaseModel):
    query: str
    top_k: int


class RetrievalCompleteEvent(BaseModel):
    sources: list[SourceItem]


class TokenEvent(BaseModel):
    delta: str


class UsageInfo(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None


class DoneEvent(BaseModel):
    finish_reason: str
    usage: UsageInfo | None = None


class ErrorEvent(BaseModel):
    error: str

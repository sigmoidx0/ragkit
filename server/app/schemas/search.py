from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int | None = Field(default=None, ge=1, le=200)
    document_id: int | None = None


class SearchHitOut(BaseModel):
    document_id: int
    document_title: str | None = None
    ordinal: int
    score: float
    text: str
    metadata: dict[str, Any] = {}


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHitOut]

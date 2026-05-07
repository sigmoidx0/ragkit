from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import PipelineStatus


class PipelineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    graph_json: dict[str, Any]


class PipelineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    graph_json: dict[str, Any] | None = None


class PipelineStatusUpdate(BaseModel):
    status: PipelineStatus


class PipelineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_id: int
    name: str
    status: PipelineStatus
    graph_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PipelineRunRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=200)


class PipelineRunResponse(BaseModel):
    pipeline_id: int
    query: str
    results: list[dict[str, Any]]
    node_timings: dict[str, float] = {}

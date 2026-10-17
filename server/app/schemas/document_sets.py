from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentSetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    document_ids: list[int] = Field(default_factory=list)


class DocumentSetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    # Replaces the set's documents when given.
    document_ids: list[int] | None = None


class AgentRef(BaseModel):
    id: int
    name: str


class DocumentSetOut(BaseModel):
    id: int
    workspace_id: int
    name: str
    description: str | None
    document_ids: list[int]
    # Agents in the workspace that search this set.
    used_by: list[AgentRef]
    created_at: datetime
    updated_at: datetime

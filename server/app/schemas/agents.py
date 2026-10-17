from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import WorkspaceRole
from app.schemas.agent_config import AgentConfig


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    # Start from another agent's settings (same workspace or any you can reach).
    copy_from_agent_id: int | None = None


class AgentUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    created_at: datetime
    updated_at: datetime


class AgentCardOut(AgentOut):
    """One agent as the landing page and the rest of the UI see it."""

    workspace_name: str
    # The caller's role in the agent's workspace — what they may change.
    role: WorkspaceRole
    agent_config: AgentConfig
    # Documents this agent can search: the union of its document sets.
    document_count: int
    # Resolved "provider · model" the agent will actually run on, after
    # config.yaml defaults are applied — what a user needs to see on the card.
    model_label: str


class RouteRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class RouteOut(BaseModel):
    agent_id: int
    # One sentence on why, in the user's language; empty when there was no choice.
    reason: str

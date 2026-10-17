from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import WorkspaceRole


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime


class WorkspaceWithRoleOut(WorkspaceOut):
    role: WorkspaceRole


class WorkspaceMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    workspace_id: int
    role: WorkspaceRole
    created_at: datetime
    updated_at: datetime


class WorkspaceMemberCreate(BaseModel):
    user_id: int
    role: WorkspaceRole


class WorkspaceMemberUpdate(BaseModel):
    role: WorkspaceRole

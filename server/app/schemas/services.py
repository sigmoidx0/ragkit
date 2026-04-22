from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import ServiceRole


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime


class ServiceMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    service_id: int
    role: ServiceRole
    created_at: datetime
    updated_at: datetime


class ServiceMemberCreate(BaseModel):
    user_id: int
    role: ServiceRole


class ServiceMemberUpdate(BaseModel):
    role: ServiceRole


class ServiceWithRoleOut(ServiceOut):
    role: ServiceRole

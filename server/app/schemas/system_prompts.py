from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SystemPromptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)


class SystemPromptUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1)


class SystemPromptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service_id: int
    name: str
    content: str
    is_active: bool
    created_by: int | None
    created_at: datetime
    updated_at: datetime

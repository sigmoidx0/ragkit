from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime
    updated_at: datetime


class MeOut(UserOut):
    is_superadmin: bool


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

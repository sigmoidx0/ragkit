from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FeedbackItem(BaseModel):
    id: int
    session_id: int
    session_title: str | None
    user_email: str
    turn_index: int
    rating: int
    comment: str | None
    question: str
    answer: str
    created_at: datetime


class FeedbackOverview(BaseModel):
    up: int
    down: int
    items: list[FeedbackItem]

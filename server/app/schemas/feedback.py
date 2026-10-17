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
    # The standalone rewrite of `question`, when the turn was logged. A
    # follow-up ("그럼 마감은?") only makes sense as an eval case in this form.
    query: str | None = None
    answer: str
    created_at: datetime


class FeedbackOverview(BaseModel):
    up: int
    down: int
    items: list[FeedbackItem]


class UnansweredItem(BaseModel):
    session_id: int
    session_title: str | None
    user_email: str
    turn_index: int
    question: str
    query: str
    route: str | None
    source_count: int
    created_at: datetime


class UnansweredOverview(BaseModel):
    # Logged turns that searched, and how many of those cited nothing.
    searched: int
    unanswered: int
    items: list[UnansweredItem]

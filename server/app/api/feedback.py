"""User feedback on answers, for the people tuning an agent."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import DbDep, ServiceAdminDep
from app.db.models import ChatSession, MessageFeedback, User
from app.schemas.feedback import FeedbackItem, FeedbackOverview

router = APIRouter(tags=["feedback"])


@router.get("/services/{service_id}/feedback", response_model=FeedbackOverview)
def list_feedback(
    service_id: int,
    _admin: ServiceAdminDep,
    db: DbDep,
    rating: Literal[1, -1] | None = None,
    limit: int = 100,
) -> FeedbackOverview:
    counts = dict(
        db.execute(
            select(MessageFeedback.rating, func.count())
            .where(MessageFeedback.service_id == service_id)
            .group_by(MessageFeedback.rating)
        ).all()
    )
    stmt = (
        select(MessageFeedback, ChatSession.title, User.email)
        .join(ChatSession, ChatSession.id == MessageFeedback.session_id)
        .join(User, User.id == MessageFeedback.user_id)
        .where(MessageFeedback.service_id == service_id)
        .order_by(MessageFeedback.updated_at.desc())
        .limit(min(max(limit, 1), 500))
    )
    if rating is not None:
        stmt = stmt.where(MessageFeedback.rating == rating)
    items = [
        FeedbackItem(
            id=f.id,
            session_id=f.session_id,
            session_title=title,
            user_email=email,
            turn_index=f.turn_index,
            rating=f.rating,
            comment=f.comment,
            question=f.question,
            answer=f.answer,
            created_at=f.updated_at,
        )
        for f, title, email in db.execute(stmt).all()
    ]
    return FeedbackOverview(up=counts.get(1, 0), down=counts.get(-1, 0), items=items)

"""User feedback on answers, for the people tuning an agent."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import AgentAdminDep, DbDep
from app.db.models import ChatSession, ChatTurnLog, MessageFeedback, User
from app.schemas.feedback import FeedbackItem, FeedbackOverview, UnansweredItem, UnansweredOverview

router = APIRouter(tags=["feedback"])


@router.get("/agents/{agent_id}/feedback", response_model=FeedbackOverview)
def list_feedback(
    agent_id: int,
    _admin: AgentAdminDep,
    db: DbDep,
    rating: Literal[1, -1] | None = None,
    limit: int = 100,
) -> FeedbackOverview:
    counts = dict(
        db.execute(
            select(MessageFeedback.rating, func.count())
            .where(MessageFeedback.agent_id == agent_id)
            .group_by(MessageFeedback.rating)
        ).all()
    )
    stmt = (
        select(MessageFeedback, ChatSession.title, User.email, ChatTurnLog.query)
        .join(ChatSession, ChatSession.id == MessageFeedback.session_id)
        .join(User, User.id == MessageFeedback.user_id)
        .outerjoin(
            ChatTurnLog,
            (ChatTurnLog.session_id == MessageFeedback.session_id)
            & (ChatTurnLog.turn_index == MessageFeedback.turn_index),
        )
        .where(MessageFeedback.agent_id == agent_id)
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
            query=query,
            answer=f.answer,
            created_at=f.updated_at,
        )
        for f, title, email, query in db.execute(stmt).all()
    ]
    return FeedbackOverview(up=counts.get(1, 0), down=counts.get(-1, 0), items=items)


@router.get("/agents/{agent_id}/unanswered", response_model=UnansweredOverview)
def list_unanswered(agent_id: int, _admin: AgentAdminDep, db: DbDep, limit: int = 100) -> UnansweredOverview:
    """Questions the agent searched for but answered without citing anything.

    Usually "the documents don't cover this" — a list of what to add to the
    agent's document sets, or of questions it should have found and didn't.
    """
    searched = ChatTurnLog.agent_id == agent_id, ChatTurnLog.route.is_distinct_from("direct")
    unanswered = (*searched, ChatTurnLog.cited_count == 0)
    stmt = (
        select(ChatTurnLog, ChatSession.title, User.email)
        .join(ChatSession, ChatSession.id == ChatTurnLog.session_id)
        .join(User, User.id == ChatSession.user_id)
        .where(*unanswered)
        .order_by(ChatTurnLog.created_at.desc())
        .limit(min(max(limit, 1), 500))
    )
    items = [
        UnansweredItem(
            session_id=log.session_id,
            session_title=title,
            user_email=email,
            turn_index=log.turn_index,
            question=log.question,
            query=log.query,
            route=log.route,
            source_count=log.source_count,
            created_at=log.created_at,
        )
        for log, title, email in db.execute(stmt).all()
    ]
    return UnansweredOverview(
        searched=_count_logs(db, *searched), unanswered=_count_logs(db, *unanswered), items=items
    )


def _count_logs(db: DbDep, *where) -> int:
    return db.execute(select(func.count()).select_from(ChatTurnLog).where(*where)).scalar_one()

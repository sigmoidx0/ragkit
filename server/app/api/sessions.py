"""Chat session CRUD + stateful chat endpoint."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.agent.checkpoint import get_checkpointer
from app.agent.executor import session_agent_stream
from app.agent.history import question_and_answer, session_turns
from app.api.deps import CurrentUser, DbDep, ServiceMemberDep
from app.core.config import get_settings
from app.db.models import ChatSession, ChatTurnSources, MessageFeedback
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionResponse,
    FeedbackIn,
    FeedbackOut,
    SessionChatRequest,
    SessionMessageResponse,
    SourceItem,
)

router = APIRouter(tags=["sessions"])


def _get_session_or_404(db: DbDep, session_id: int, user_id: int, service_id: int) -> ChatSession:
    session = db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.service_id == service_id,
        )
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "session not found")
    return session


# ── Session CRUD ─────────────────────────────────────────────────────────────

@router.post("/services/{service_id}/sessions", response_model=ChatSessionResponse, status_code=201)
def create_session(
    service_id: int,
    body: ChatSessionCreate,
    _membership: ServiceMemberDep,
    user: CurrentUser,
    db: DbDep,
) -> ChatSession:
    session = ChatSession(user_id=user.id, service_id=service_id, title=body.title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/services/{service_id}/sessions", response_model=list[ChatSessionResponse])
def list_sessions(
    service_id: int,
    _membership: ServiceMemberDep,
    user: CurrentUser,
    db: DbDep,
) -> list[ChatSession]:
    rows = db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user.id, ChatSession.service_id == service_id)
        .order_by(ChatSession.updated_at.desc())
    ).scalars().all()
    return list(rows)


@router.get(
    "/services/{service_id}/sessions/{session_id}/messages",
    response_model=list[SessionMessageResponse],
)
async def list_messages(
    service_id: int,
    session_id: int,
    _membership: ServiceMemberDep,
    user: CurrentUser,
    db: DbDep,
) -> list[SessionMessageResponse]:
    _get_session_or_404(db, session_id, user.id, service_id)
    cp_tuple = await get_checkpointer().aget_tuple(
        {"configurable": {"thread_id": str(session_id)}}
    )
    if not cp_tuple:
        return []
    lc_msgs = cp_tuple.checkpoint.get("channel_values", {}).get("messages", [])

    # Load stored sources indexed by assistant turn index
    rows = db.execute(
        select(ChatTurnSources).where(ChatTurnSources.session_id == session_id)
    ).scalars().all()
    sources_by_turn: dict[int, list[SourceItem]] = {
        row.turn_index: [SourceItem(**s) for s in row.sources_json]
        for row in rows
    }
    feedback_by_turn = {
        f.turn_index: FeedbackOut(rating=f.rating, comment=f.comment)
        for f in db.execute(select(MessageFeedback).where(MessageFeedback.session_id == session_id)).scalars()
    }

    return [
        SessionMessageResponse(
            role=turn.role,
            content=turn.content,
            sources=sources_by_turn.get(turn.turn_index, []) if turn.turn_index is not None else [],
            turn_index=turn.turn_index,
            feedback=feedback_by_turn.get(turn.turn_index) if turn.turn_index is not None else None,
        )
        for turn in session_turns(lc_msgs)
    ]


# ── Feedback ──────────────────────────────────────────────────────────────────

@router.put(
    "/services/{service_id}/sessions/{session_id}/turns/{turn_index}/feedback",
    response_model=FeedbackOut,
)
async def rate_answer(
    service_id: int,
    session_id: int,
    turn_index: int,
    body: FeedbackIn,
    _membership: ServiceMemberDep,
    user: CurrentUser,
    db: DbDep,
) -> FeedbackOut:
    """Rate one answer. Rating again replaces the earlier rating."""
    _get_session_or_404(db, session_id, user.id, service_id)
    cp_tuple = await get_checkpointer().aget_tuple({"configurable": {"thread_id": str(session_id)}})
    lc_msgs = cp_tuple.checkpoint.get("channel_values", {}).get("messages", []) if cp_tuple else []
    # The question/answer text comes from the stored history, not the client,
    # so feedback always describes what the agent actually said.
    found = question_and_answer(lc_msgs, turn_index)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "answer not found")
    question, answer = found

    feedback = db.execute(
        select(MessageFeedback).where(
            MessageFeedback.session_id == session_id, MessageFeedback.turn_index == turn_index
        )
    ).scalar_one_or_none()
    if feedback is None:
        feedback = MessageFeedback(
            service_id=service_id, session_id=session_id, user_id=user.id, turn_index=turn_index
        )
        db.add(feedback)
    feedback.rating = body.rating
    feedback.comment = (body.comment or "").strip() or None
    feedback.question, feedback.answer = question, answer
    db.commit()
    return FeedbackOut(rating=feedback.rating, comment=feedback.comment)


@router.delete(
    "/services/{service_id}/sessions/{session_id}/turns/{turn_index}/feedback",
    status_code=204,
)
def clear_rating(
    service_id: int,
    session_id: int,
    turn_index: int,
    _membership: ServiceMemberDep,
    user: CurrentUser,
    db: DbDep,
) -> None:
    _get_session_or_404(db, session_id, user.id, service_id)
    feedback = db.execute(
        select(MessageFeedback).where(
            MessageFeedback.session_id == session_id, MessageFeedback.turn_index == turn_index
        )
    ).scalar_one_or_none()
    if feedback is not None:
        db.delete(feedback)
        db.commit()


@router.delete("/services/{service_id}/sessions/{session_id}", status_code=204)
async def delete_session(
    service_id: int,
    session_id: int,
    _membership: ServiceMemberDep,
    user: CurrentUser,
    db: DbDep,
) -> None:
    session = _get_session_or_404(db, session_id, user.id, service_id)
    # Through the saver's own API: its tables differ by backend (SQLite has
    # `writes`, Postgres has `checkpoint_writes` + `checkpoint_blobs`), and
    # naming them here broke deletion on Postgres.
    await get_checkpointer().adelete_thread(str(session_id))
    db.delete(session)
    db.commit()


# ── Stateful chat ─────────────────────────────────────────────────────────────

@router.post("/services/{service_id}/sessions/{session_id}/chat")
async def session_chat(
    service_id: int,
    session_id: int,
    body: SessionChatRequest,
    _membership: ServiceMemberDep,
    user: CurrentUser,
    db: DbDep,
) -> StreamingResponse:
    if not get_settings().chat.enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "chat is disabled")

    session = _get_session_or_404(db, session_id, user.id, service_id)
    session.updated_at = datetime.now(UTC)
    db.commit()

    return StreamingResponse(
        session_agent_stream(
            db, service_id, str(session_id), body.message, body.top_k, body.retrieval_mode, user_id=user.id
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

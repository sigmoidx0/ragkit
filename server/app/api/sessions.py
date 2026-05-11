"""Chat session CRUD + stateful chat endpoint."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update

from app.agent.executor import agent_stream
from app.api.deps import CurrentUser, DbDep, ServiceMemberDep
from app.core.config import get_settings
from app.db.models import ChatSession, SessionMessage
from app.schemas.chat import (
    ChatMessage,
    ChatSessionCreate,
    ChatSessionResponse,
    SessionChatRequest,
    SessionMessageResponse,
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


def _parse_token_delta(sse_chunk: str) -> str | None:
    """Extract delta text from a `event: token` SSE chunk."""
    lines = sse_chunk.strip().split("\n")
    if not lines or lines[0] != "event: token":
        return None
    for line in lines[1:]:
        if line.startswith("data:"):
            try:
                return json.loads(line[5:].strip()).get("delta")
            except Exception:
                pass
    return None


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
def list_messages(
    service_id: int,
    session_id: int,
    _membership: ServiceMemberDep,
    user: CurrentUser,
    db: DbDep,
) -> list[SessionMessage]:
    session = _get_session_or_404(db, session_id, user.id, service_id)
    rows = db.execute(
        select(SessionMessage)
        .where(SessionMessage.session_id == session.id)
        .order_by(SessionMessage.id)
    ).scalars().all()
    return list(rows)


@router.delete("/services/{service_id}/sessions/{session_id}", status_code=204)
def delete_session(
    service_id: int,
    session_id: int,
    _membership: ServiceMemberDep,
    user: CurrentUser,
    db: DbDep,
) -> None:
    session = _get_session_or_404(db, session_id, user.id, service_id)
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

    # Load conversation history
    history_rows = db.execute(
        select(SessionMessage)
        .where(SessionMessage.session_id == session.id)
        .order_by(SessionMessage.id)
    ).scalars().all()

    history = [ChatMessage(role=r.role, content=r.content) for r in history_rows]
    all_messages = history + [ChatMessage(role="user", content=body.message)]

    # Persist user message before streaming
    db.add(SessionMessage(session_id=session.id, role="user", content=body.message))
    db.commit()

    async def _stream_and_save():
        tokens: list[str] = []
        try:
            async for chunk in agent_stream(db, service_id, all_messages, body.top_k, body.filters):
                yield chunk
                delta = _parse_token_delta(chunk)
                if delta:
                    tokens.append(delta)
        finally:
            if tokens:
                db.add(SessionMessage(
                    session_id=session.id,
                    role="assistant",
                    content="".join(tokens),
                ))
                db.execute(
                    update(ChatSession)
                    .where(ChatSession.id == session.id)
                    .values(updated_at=func.now())
                )
                db.commit()

    return StreamingResponse(
        _stream_and_save(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

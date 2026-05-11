"""Chat session CRUD + stateful chat endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select

from app.agent.checkpoint import get_checkpointer
from app.agent.executor import session_agent_stream
from app.api.deps import CurrentUser, DbDep, ServiceMemberDep
from app.core.config import get_settings
from app.db.models import ChatSession
from app.schemas.chat import (
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
    result: list[SessionMessageResponse] = []
    for msg in lc_msgs:
        if isinstance(msg, HumanMessage):
            result.append(SessionMessageResponse(role="user", content=str(msg.content)))
        elif isinstance(msg, AIMessage) and msg.content:
            result.append(SessionMessageResponse(role="assistant", content=str(msg.content)))
    return result


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

    _get_session_or_404(db, session_id, user.id, service_id)

    return StreamingResponse(
        session_agent_stream(db, service_id, str(session_id), body.message, body.top_k, body.filters),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

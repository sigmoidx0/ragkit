"""Chat endpoint: POST /agents/{agent_id}/chat → SSE stream."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.agent.executor import agent_stream
from app.api.deps import AgentMemberDep, CurrentUser, DbDep
from app.core.config import get_settings
from app.schemas.chat import ChatRequest

router = APIRouter(tags=["chat"])


@router.post("/agents/{agent_id}/chat")
async def chat(
    agent_id: int,
    body: ChatRequest,
    _membership: AgentMemberDep,
    _user: CurrentUser,
    db: DbDep,
) -> StreamingResponse:
    if not get_settings().chat.enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "chat is disabled")

    return StreamingResponse(
        agent_stream(db, agent_id, body.messages, body.top_k, body.retrieval_mode, user_id=_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

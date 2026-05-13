"""Chat endpoint: POST /services/{service_id}/chat → SSE stream."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.agent.executor import agent_stream
from app.api.deps import CurrentUser, DbDep, ServiceMemberDep
from app.core.config import get_settings
from app.schemas.chat import ChatRequest

router = APIRouter(tags=["chat"])


@router.post("/services/{service_id}/chat")
async def chat(
    service_id: int,
    body: ChatRequest,
    _membership: ServiceMemberDep,
    _user: CurrentUser,
    db: DbDep,
) -> StreamingResponse:
    if not get_settings().chat.enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "chat is disabled")

    return StreamingResponse(
        agent_stream(db, service_id, body.messages, body.top_k, body.filters, body.retrieval_mode),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

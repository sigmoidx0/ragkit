"""Agent configuration: read/update an agent's settings and preview its graph."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.agent.config import load_agent_config, provider_catalog, resolve_llm
from app.agent.delegation import resolve_delegates
from app.agent.graph import build_multi_agent_graph
from app.api.deps import CurrentUser, DbDep, ServiceAdminDep, ServiceMemberDep
from app.db.models import Pipeline, PipelineStatus, Service
from app.llm import get_chat_model
from app.schemas.agent_config import AgentConfig, RetrievalMode
from app.schemas.chat import GraphEvent

router = APIRouter(tags=["agent-config"])


def _get_service(db, service_id: int) -> Service:
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "agent not found")
    return service


@router.get("/llm/providers")
def list_llm_providers(_user: CurrentUser) -> list[dict]:
    """Providers the settings UI can offer, with availability and model hints."""
    return provider_catalog()


@router.get("/services/{service_id}/agent-config", response_model=AgentConfig)
def get_agent_config(service_id: int, _membership: ServiceMemberDep, db: DbDep) -> AgentConfig:
    return load_agent_config(_get_service(db, service_id))


@router.put("/services/{service_id}/agent-config", response_model=AgentConfig)
def update_agent_config(
    service_id: int,
    body: AgentConfig,
    _admin: ServiceAdminDep,
    db: DbDep,
) -> AgentConfig:
    service = _get_service(db, service_id)

    if body.pipeline_id is not None:
        pipeline = db.get(Pipeline, body.pipeline_id)
        if not pipeline or pipeline.service_id != service_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "pipeline does not belong to this agent")
        if pipeline.status != PipelineStatus.active:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "only an active pipeline can serve chat")

    if body.delegates:
        # Only agents the saving admin can reach may be delegated to — otherwise
        # an admin could route questions into document sets they can't see.
        reachable = {s.id for s in resolve_delegates(db, service_id, body.delegates, _admin.user_id)}
        unreachable = [d for d in body.delegates if d not in reachable]
        if unreachable:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"cannot delegate to agent(s) {unreachable}: missing, this agent itself, or not accessible",
            )

    try:
        # Fails fast on a config that could never run, e.g. a provider with no model.
        resolve_llm(body)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    service.agent_config = body.model_dump(mode="json")
    db.commit()
    return body


class GraphPreviewRequest(BaseModel):
    config: AgentConfig
    retrieval_mode: RetrievalMode | None = None


@router.post("/services/{service_id}/agent-graph/preview", response_model=GraphEvent)
def preview_agent_graph(
    service_id: int,
    body: GraphPreviewRequest,
    _membership: ServiceMemberDep,
    db: DbDep,
) -> GraphEvent:
    """Shape of the graph a (possibly unsaved) config would run.

    Built from the same code path as chat, so the preview can't drift from what
    actually executes. The default model stands in for the agent's, since the
    shape doesn't depend on it.
    """
    _get_service(db, service_id)
    built = build_multi_agent_graph(
        db,
        service_id,
        body.config,
        system_prompt="",
        retrieval_mode=body.retrieval_mode or body.config.default_retrieval_mode,
        llm=get_chat_model(),
        user_id=_membership.user_id,
    )
    return built.topology()

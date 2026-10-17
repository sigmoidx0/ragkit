"""Agents: create and manage them, read and save their settings, preview their graph."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.config import (
    load_agent_config,
    provider_catalog,
    resolve_document_scope,
    resolve_llm,
)
from app.agent.delegation import resolve_delegates
from app.agent.graph import build_multi_agent_graph
from app.agent.routing import pick_agent
from app.api.deps import (
    AgentAdminDep,
    AgentMemberDep,
    CurrentUser,
    DbDep,
    WorkspaceAdminDep,
    WorkspaceMemberDep,
    is_superadmin,
    membership_for,
)
from app.db.models import (
    Agent,
    DocumentSet,
    McpServer,
    Pipeline,
    PipelineStatus,
    Workspace,
    WorkspaceMembership,
)
from app.llm import get_chat_model
from app.schemas.agent_config import AgentConfig, RetrievalMode
from app.schemas.agents import (
    AgentCardOut,
    AgentCreate,
    AgentOut,
    AgentUpdate,
    RouteOut,
    RouteRequest,
)
from app.schemas.chat import GraphEvent

router = APIRouter(tags=["agents"])


def _card(db: Session, agent: Agent, workspace: Workspace, role) -> AgentCardOut:
    cfg = load_agent_config(agent)
    scope = resolve_document_scope(db, agent.workspace_id, cfg)
    try:
        llm = resolve_llm(cfg)
        model_label = f"{llm.provider} · {llm.model}"
    except ValueError:
        model_label = "misconfigured"
    return AgentCardOut(
        **AgentOut.model_validate(agent).model_dump(),
        workspace_name=workspace.name,
        role=role,
        agent_config=cfg,
        document_count=len(scope),
        model_label=model_label,
    )


# ── Listing ─────────────────────────────────────────────────────────────────

@router.get("/me/agents", response_model=list[AgentCardOut])
def list_my_agents(user: CurrentUser, db: DbDep, workspace_id: int | None = None) -> list[AgentCardOut]:
    """Agents the user can chat with — optionally just one workspace's."""
    stmt = select(Agent, Workspace).join(Workspace, Workspace.id == Agent.workspace_id)
    if not is_superadmin(db, user.id):
        stmt = stmt.join(
            WorkspaceMembership,
            (WorkspaceMembership.workspace_id == Workspace.id) & (WorkspaceMembership.user_id == user.id),
        )
    if workspace_id is not None:
        stmt = stmt.where(Agent.workspace_id == workspace_id)
    rows = db.execute(stmt.order_by(Workspace.name, Agent.name)).all()

    cards = []
    for agent, workspace in rows:
        role = membership_for(db, user.id, workspace.id).role
        cards.append(_card(db, agent, workspace, role))
    return cards


@router.get("/workspaces/{workspace_id}/agents", response_model=list[AgentOut])
def list_workspace_agents(workspace_id: int, _membership: WorkspaceMemberDep, db: DbDep) -> list[Agent]:
    return list(db.execute(select(Agent).where(Agent.workspace_id == workspace_id).order_by(Agent.name)).scalars())


@router.post("/workspaces/{workspace_id}/route", response_model=RouteOut)
async def route_question(workspace_id: int, body: RouteRequest, _membership: WorkspaceMemberDep, db: DbDep) -> RouteOut:
    """Which of the workspace's agents should take this question (see app/agent/routing.py)."""
    agents = list(db.execute(select(Agent).where(Agent.workspace_id == workspace_id).order_by(Agent.id)).scalars())
    if not agents:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "this workspace has no agents")
    try:
        agent, reason = await pick_agent(db, agents, body.question)
    except Exception as exc:  # the model is down or returned junk — let the user pick
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"couldn't choose an agent: {exc}") from exc
    return RouteOut(agent_id=agent.id, reason=reason)


# ── Create / rename / delete ────────────────────────────────────────────────

@router.post("/workspaces/{workspace_id}/agents", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
def create_agent(workspace_id: int, body: AgentCreate, admin: WorkspaceAdminDep, db: DbDep) -> Agent:
    if not db.get(Workspace, workspace_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workspace not found")
    config = None
    if body.copy_from_agent_id is not None:
        source = db.get(Agent, body.copy_from_agent_id)
        if not source or not membership_for(db, admin.user_id, source.workspace_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "agent to copy not found")
        config = dict(source.agent_config or {})
        if source.workspace_id != workspace_id:
            # Document sets, pipelines and MCP servers are per workspace; they don't carry over.
            config.update(document_set_ids=[], pipeline_id=None, mcp_tools=[])
    agent = Agent(workspace_id=workspace_id, name=body.name, agent_config=config)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/agents/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: int, access: AgentMemberDep) -> Agent:
    return access.agent


@router.patch("/agents/{agent_id}", response_model=AgentOut)
def rename_agent(agent_id: int, body: AgentUpdate, access: AgentAdminDep, db: DbDep) -> Agent:
    access.agent.name = body.name
    db.commit()
    db.refresh(access.agent)
    return access.agent


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: int, access: AgentAdminDep, db: DbDep) -> None:
    """Deletes the agent with its prompts, chats, evaluations and feedback.
    The workspace's documents and document sets are untouched."""
    db.delete(access.agent)
    db.commit()


# ── Settings ────────────────────────────────────────────────────────────────

@router.get("/llm/providers")
def list_llm_providers(_user: CurrentUser) -> list[dict]:
    """Providers the settings UI can offer, with availability and model hints."""
    return provider_catalog()


@router.get("/agents/{agent_id}/config", response_model=AgentConfig)
def get_agent_config(agent_id: int, access: AgentMemberDep) -> AgentConfig:
    return load_agent_config(access.agent)


@router.put("/agents/{agent_id}/config", response_model=AgentConfig)
def update_agent_config(agent_id: int, body: AgentConfig, access: AgentAdminDep, db: DbDep) -> AgentConfig:
    agent = access.agent

    if body.pipeline_id is not None:
        pipeline = db.get(Pipeline, body.pipeline_id)
        if not pipeline or pipeline.workspace_id != agent.workspace_id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "pipeline is not in this agent's workspace")
        if pipeline.status != PipelineStatus.active:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "only an active pipeline can serve chat")

    if body.document_set_ids:
        known = set(
            db.execute(
                select(DocumentSet.id).where(
                    DocumentSet.workspace_id == agent.workspace_id, DocumentSet.id.in_(body.document_set_ids)
                )
            ).scalars()
        )
        if unknown := [i for i in body.document_set_ids if i not in known]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"document sets not in this agent's workspace: {unknown}"
            )

    if body.delegates:
        # Only agents the saving admin can reach may be delegated to — otherwise
        # an admin could route questions into documents they can't see.
        reachable = {a.id for a in resolve_delegates(db, agent.id, body.delegates, access.user_id)}
        if unreachable := [d for d in body.delegates if d not in reachable]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"cannot delegate to agent(s) {unreachable}: missing, this agent itself, or not accessible",
            )

    if body.mcp_tools:
        servers = {
            s.id: s
            for s in db.execute(
                select(McpServer).where(
                    McpServer.workspace_id == agent.workspace_id,
                    McpServer.id.in_({ref.server_id for ref in body.mcp_tools}),
                )
            ).scalars()
        }
        for ref in body.mcp_tools:
            server = servers.get(ref.server_id)
            if server is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, f"MCP server {ref.server_id} is not in this agent's workspace"
                )
            if not any(t["name"] == ref.tool for t in server.tools or []):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, f"MCP server '{server.name}' has no tool '{ref.tool}'"
                )

    try:
        # Fails fast on a config that could never run, e.g. a provider with no model.
        resolve_llm(body)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    agent.agent_config = body.model_dump(mode="json")
    db.commit()
    return body


class GraphPreviewRequest(BaseModel):
    config: AgentConfig
    retrieval_mode: RetrievalMode | None = None


class GraphPreviewResponse(GraphEvent):
    # Documents the draft's document sets put in scope; none selected = nothing.
    document_count: int | None = None


@router.post("/agents/{agent_id}/graph-preview", response_model=GraphPreviewResponse)
def preview_agent_graph(
    agent_id: int, body: GraphPreviewRequest, access: AgentMemberDep, db: DbDep
) -> GraphPreviewResponse:
    """Shape of the graph a (possibly unsaved) config would run.

    Built from the same code path as chat, so the preview can't drift from what
    actually executes. The default model stands in for the agent's, since the
    shape doesn't depend on it.
    """
    built = build_multi_agent_graph(
        db,
        access.agent,
        body.config,
        system_prompt="",
        retrieval_mode=body.retrieval_mode or body.config.default_retrieval_mode,
        llm=get_chat_model(),
        user_id=access.user_id,
    )
    scope = resolve_document_scope(db, access.agent.workspace_id, body.config)
    return GraphPreviewResponse(**built.topology().model_dump(), document_count=len(scope))

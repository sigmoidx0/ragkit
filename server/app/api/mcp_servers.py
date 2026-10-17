"""MCP servers of a workspace, and the audit trail of the calls agents made to them."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.agent.config import load_agent_config
from app.agent.mcp import McpError, list_server_tools
from app.api.deps import DbDep, WorkspaceAdminDep, WorkspaceMemberDep
from app.db.models import Agent, McpServer, McpToolCall, User
from app.schemas.mcp import McpServerCreate, McpServerOut, McpServerUpdate, McpToolCallOut

router = APIRouter(tags=["mcp"])


def _users_of(db: Session, server: McpServer) -> list[Agent]:
    agents = db.execute(select(Agent).where(Agent.workspace_id == server.workspace_id)).scalars()
    return [a for a in agents if any(ref.server_id == server.id for ref in load_agent_config(a).mcp_tools)]


def _out(db: Session, server: McpServer) -> McpServerOut:
    return McpServerOut(
        id=server.id,
        workspace_id=server.workspace_id,
        name=server.name,
        description=server.description,
        url=server.url,
        auth_env_var=server.auth_env_var,
        auth_configured=bool(server.auth_env_var and os.getenv(server.auth_env_var)),
        enabled=server.enabled,
        tools=server.tools or [],
        tools_refreshed_at=server.tools_refreshed_at,
        last_error=server.last_error,
        used_by=[{"id": a.id, "name": a.name} for a in _users_of(db, server)],
    )


def _get(db: Session, workspace_id: int, server_id: int) -> McpServer:
    server = db.get(McpServer, server_id)
    if not server or server.workspace_id != workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "MCP server not found")
    return server


async def _refresh(db: Session, server: McpServer) -> None:
    """Fetch the tool list. A failure is stored on the server, not raised: the
    admin sees it on the page and can fix the URL or token."""
    try:
        server.tools = await list_server_tools(server)
        server.tools_refreshed_at = datetime.now(UTC)
        server.last_error = None
    except McpError as exc:
        server.last_error = str(exc)
    db.commit()


def _commit_unique(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "an MCP server with this name already exists") from exc


@router.get("/workspaces/{workspace_id}/mcp-servers", response_model=list[McpServerOut])
def list_servers(workspace_id: int, _membership: WorkspaceMemberDep, db: DbDep) -> list[McpServerOut]:
    servers = db.execute(
        select(McpServer).where(McpServer.workspace_id == workspace_id).order_by(McpServer.name)
    ).scalars()
    return [_out(db, s) for s in servers]


@router.post("/workspaces/{workspace_id}/mcp-servers", response_model=McpServerOut, status_code=status.HTTP_201_CREATED)
async def create_server(workspace_id: int, body: McpServerCreate, _admin: WorkspaceAdminDep, db: DbDep) -> McpServerOut:
    server = McpServer(workspace_id=workspace_id, **body.model_dump())
    db.add(server)
    _commit_unique(db)
    await _refresh(db, server)
    return _out(db, server)


@router.patch("/workspaces/{workspace_id}/mcp-servers/{server_id}", response_model=McpServerOut)
async def update_server(
    workspace_id: int, server_id: int, body: McpServerUpdate, _admin: WorkspaceAdminDep, db: DbDep
) -> McpServerOut:
    server = _get(db, workspace_id, server_id)
    changes = body.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(server, key, value)
    _commit_unique(db)
    if {"url", "auth_env_var"} & changes.keys():
        await _refresh(db, server)
    return _out(db, server)


@router.post("/workspaces/{workspace_id}/mcp-servers/{server_id}/refresh", response_model=McpServerOut)
async def refresh_server(workspace_id: int, server_id: int, _admin: WorkspaceAdminDep, db: DbDep) -> McpServerOut:
    server = _get(db, workspace_id, server_id)
    await _refresh(db, server)
    return _out(db, server)


@router.delete("/workspaces/{workspace_id}/mcp-servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_server(workspace_id: int, server_id: int, _admin: WorkspaceAdminDep, db: DbDep) -> None:
    server = _get(db, workspace_id, server_id)
    # Same rule as document sets: don't silently take tools away from agents.
    if users := _users_of(db, server):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"still used by agent(s): {', '.join(a.name for a in users)} — remove its tools from them first",
        )
    db.delete(server)
    db.commit()


@router.get("/workspaces/{workspace_id}/mcp-calls", response_model=list[McpToolCallOut])
def list_calls(
    workspace_id: int, _admin: WorkspaceAdminDep, db: DbDep, limit: int = Query(50, ge=1, le=200)
) -> list[McpToolCallOut]:
    """Recent MCP calls by the workspace's agents, newest first."""
    requester, decider = aliased(User), aliased(User)
    rows = db.execute(
        select(McpToolCall, Agent.name, requester.email, decider.email)
        .join(Agent, Agent.id == McpToolCall.agent_id)
        .outerjoin(requester, requester.id == McpToolCall.requested_by)
        .outerjoin(decider, decider.id == McpToolCall.decided_by)
        .where(Agent.workspace_id == workspace_id)
        .order_by(McpToolCall.id.desc())
        .limit(limit)
    ).all()
    return [
        McpToolCallOut(
            id=c.id, agent_id=c.agent_id, agent_name=agent_name, session_id=c.session_id,
            server_name=c.server_name, tool=c.tool, args=c.args, approved_args=c.approved_args,
            status=c.status.value, requested_by=req, decided_by=dec, decided_at=c.decided_at,
            result=c.result, is_error=c.is_error, created_at=c.created_at,
        )
        for c, agent_name, req, dec in rows
    ]

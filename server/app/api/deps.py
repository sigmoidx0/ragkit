"""Auth: Bearer JWT in Authorization header (no OAuth2 password flow).

Public interface (import these):
    is_superadmin       — utility: check superadmin status directly
    DbDep               — SQLAlchemy session
    CurrentUser         — authenticated user (JWT)
    UserOrMcpToken      — authenticated user, or None for the MCP adapter's shared token
    WorkspaceMemberDep  — current user's membership in the path's `workspace_id`
    WorkspaceWriterDep  — member or admin (viewers blocked)
    WorkspaceAdminDep   — workspace admin only
    AgentMemberDep      — the path's `agent_id`, plus the user's membership in its workspace
    AgentAdminDep       — the same, admin only
    SuperAdminDep       — superadmin only
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Agent, SuperAdmin, User, WorkspaceMembership, WorkspaceRole
from app.db.session import get_db
from app.security.tokens import decode_token

# ── Public utility ───────────────────────────────────────────────────────────

def is_superadmin(db: Session, user_id: int) -> bool:
    return db.get(SuperAdmin, user_id) is not None


# ── Internal DI callables ────────────────────────────────────────────────────

def _parse_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return None


def _get_bearer_token(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> str:
    token = _parse_bearer(authorization)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing Bearer token")
    return token


DbDep = Annotated[Session, Depends(get_db)]
_BearerDep = Annotated[str, Depends(_get_bearer_token)]


def _get_current_user(db: DbDep, token: _BearerDep) -> User:
    try:
        payload = decode_token(token)
    except ValueError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    try:
        user_id = int(sub)
    except (TypeError, ValueError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from e
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user


CurrentUser = Annotated[User, Depends(_get_current_user)]


def _get_user_or_mcp_token(
    db: DbDep,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_service_token: Annotated[str | None, Header(alias="X-Service-Token")] = None,
) -> User | None:
    expected = os.getenv("MCP_SERVICE_TOKEN")
    if expected and x_service_token and x_service_token == expected:
        return None
    token = _parse_bearer(authorization)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing credentials")
    try:
        payload = decode_token(token)
    except ValueError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e)) from e
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token")
    user = db.get(User, int(sub))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user


UserOrMcpToken = Annotated[User | None, Depends(_get_user_or_mcp_token)]


def membership_for(db: Session, user_id: int, workspace_id: int) -> WorkspaceMembership | None:
    """The user's membership in a workspace; superadmins are admins everywhere."""
    if is_superadmin(db, user_id):
        return WorkspaceMembership(user_id=user_id, workspace_id=workspace_id, role=WorkspaceRole.admin)
    return db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
    ).scalar_one_or_none()


def _get_workspace_membership(workspace_id: int, user: CurrentUser, db: DbDep) -> WorkspaceMembership:
    membership = membership_for(db, user.id, workspace_id)
    if not membership:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a member of this workspace")
    return membership


WorkspaceMemberDep = Annotated[WorkspaceMembership, Depends(_get_workspace_membership)]


def _require_workspace_writer(membership: WorkspaceMemberDep) -> WorkspaceMembership:
    if membership.role == WorkspaceRole.viewer:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "viewers cannot write")
    return membership


def _require_workspace_admin(membership: WorkspaceMemberDep) -> WorkspaceMembership:
    if membership.role != WorkspaceRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "workspace admin only")
    return membership


@dataclass
class AgentAccess:
    """An agent, and the caller's standing in the workspace that owns it."""

    agent: Agent
    membership: WorkspaceMembership

    @property
    def user_id(self) -> int:
        return self.membership.user_id


def _get_agent_access(agent_id: int, user: CurrentUser, db: DbDep) -> AgentAccess:
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "agent not found")
    membership = membership_for(db, user.id, agent.workspace_id)
    if not membership:
        # Same answer as a missing agent: don't reveal agents in other workspaces.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "agent not found")
    return AgentAccess(agent, membership)


AgentMemberDep = Annotated[AgentAccess, Depends(_get_agent_access)]


def _require_agent_admin(access: AgentMemberDep) -> AgentAccess:
    if access.membership.role != WorkspaceRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "workspace admin only")
    return access


def _require_superadmin(user: CurrentUser, db: DbDep) -> User:
    if not is_superadmin(db, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "superadmin only")
    return user


# ── Public type aliases ──────────────────────────────────────────────────────

WorkspaceWriterDep = Annotated[WorkspaceMembership, Depends(_require_workspace_writer)]
WorkspaceAdminDep = Annotated[WorkspaceMembership, Depends(_require_workspace_admin)]
AgentAdminDep = Annotated[AgentAccess, Depends(_require_agent_admin)]
SuperAdminDep = Annotated[User, Depends(_require_superadmin)]

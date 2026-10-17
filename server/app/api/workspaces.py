"""Workspaces — the tenant boundary — and their members."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import (
    CurrentUser,
    DbDep,
    SuperAdminDep,
    WorkspaceAdminDep,
    WorkspaceMemberDep,
    is_superadmin,
)
from app.db.models import Agent, User, Workspace, WorkspaceMembership, WorkspaceRole
from app.schemas.workspaces import (
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberOut,
    WorkspaceMemberUpdate,
    WorkspaceOut,
    WorkspaceWithRoleOut,
)

router = APIRouter(tags=["workspaces"])


# ── Workspace CRUD (superadmin only) ────────────────────────────────────────

@router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(_user: SuperAdminDep, db: DbDep) -> list[Workspace]:
    return list(db.execute(select(Workspace).order_by(Workspace.name)).scalars())


@router.post("/workspaces", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
def create_workspace(body: WorkspaceCreate, _user: SuperAdminDep, db: DbDep) -> Workspace:
    if db.execute(select(Workspace).where(Workspace.slug == body.slug)).scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "slug already exists")
    workspace = Workspace(name=body.name, slug=body.slug)
    db.add(workspace)
    db.flush()
    # A workspace with no agent has nothing to chat with; start it with one.
    db.add(Agent(workspace_id=workspace.id, name=body.name))
    db.commit()
    db.refresh(workspace)
    return workspace


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(workspace_id: int, _membership: WorkspaceMemberDep, db: DbDep) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workspace not found")
    return workspace


@router.delete("/workspaces/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(workspace_id: int, _user: SuperAdminDep, db: DbDep) -> None:
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workspace not found")
    db.delete(workspace)
    db.commit()


@router.get("/me/workspaces", response_model=list[WorkspaceWithRoleOut])
def list_my_workspaces(user: CurrentUser, db: DbDep) -> list[WorkspaceWithRoleOut]:
    if is_superadmin(db, user.id):
        workspaces = list(db.execute(select(Workspace).order_by(Workspace.name)).scalars())
        return [
            WorkspaceWithRoleOut(**WorkspaceOut.model_validate(w).model_dump(), role=WorkspaceRole.admin)
            for w in workspaces
        ]
    rows = db.execute(
        select(Workspace, WorkspaceMembership.role)
        .join(WorkspaceMembership, Workspace.id == WorkspaceMembership.workspace_id)
        .where(WorkspaceMembership.user_id == user.id)
        .order_by(Workspace.name)
    ).all()
    return [WorkspaceWithRoleOut(**WorkspaceOut.model_validate(w).model_dump(), role=role) for w, role in rows]


# ── Members (workspace admin) ─────────────────────────────────────────────────

@router.get("/workspaces/{workspace_id}/members", response_model=list[WorkspaceMemberOut])
def list_members(workspace_id: int, _membership: WorkspaceMemberDep, db: DbDep) -> list[WorkspaceMembership]:
    return list(
        db.execute(select(WorkspaceMembership).where(WorkspaceMembership.workspace_id == workspace_id)).scalars()
    )


@router.post("/workspaces/{workspace_id}/members", response_model=WorkspaceMemberOut, status_code=status.HTTP_201_CREATED)
def add_member(workspace_id: int, body: WorkspaceMemberCreate, _admin: WorkspaceAdminDep, db: DbDep) -> WorkspaceMembership:
    if not db.get(User, body.user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    existing = db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == body.user_id,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "user already a member")
    membership = WorkspaceMembership(user_id=body.user_id, workspace_id=workspace_id, role=body.role)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


@router.patch("/workspaces/{workspace_id}/members/{user_id}", response_model=WorkspaceMemberOut)
def update_member_role(
    workspace_id: int, user_id: int, body: WorkspaceMemberUpdate, _admin: WorkspaceAdminDep, db: DbDep
) -> WorkspaceMembership:
    membership = db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "member not found")
    membership.role = body.role
    db.commit()
    db.refresh(membership)
    return membership


@router.delete("/workspaces/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(workspace_id: int, user_id: int, _admin: WorkspaceAdminDep, db: DbDep) -> None:
    membership = db.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "member not found")
    db.delete(membership)
    db.commit()

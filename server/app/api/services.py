"""Services and membership management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep, ServiceAdminDep, ServiceMemberDep, SuperAdminDep, is_superadmin
from app.db.models import Service, ServiceMembership, ServiceRole, User
from app.schemas.services import (
    ServiceCreate,
    ServiceMemberCreate,
    ServiceMemberOut,
    ServiceMemberUpdate,
    ServiceOut,
    ServiceWithRoleOut,
)

router = APIRouter(tags=["services"])


# ── Service CRUD (superadmin only) ──────────────────────────────────────────

@router.get("/services", response_model=list[ServiceOut])
def list_services(_user: SuperAdminDep, db: DbDep) -> list[Service]:
    return list(db.execute(select(Service).order_by(Service.name)).scalars())


@router.post("/services", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def create_service(body: ServiceCreate, _user: SuperAdminDep, db: DbDep) -> Service:
    if db.execute(select(Service).where(Service.slug == body.slug)).scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "slug already exists")
    service = Service(name=body.name, slug=body.slug)
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.get("/services/{service_id}", response_model=ServiceOut)
def get_service(service_id: int, _membership: ServiceMemberDep, db: DbDep) -> Service:
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "service not found")
    return service


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(service_id: int, _user: SuperAdminDep, db: DbDep) -> None:
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "service not found")
    db.delete(service)
    db.commit()


# ── My services ─────────────────────────────────────────────────────────────

@router.get("/me/services", response_model=list[ServiceWithRoleOut])
def list_my_services(user: CurrentUser, db: DbDep) -> list[ServiceWithRoleOut]:
    if is_superadmin(db, user.id):
        services = list(db.execute(select(Service).order_by(Service.name)).scalars())
        return [ServiceWithRoleOut(**ServiceOut.model_validate(s).model_dump(), role=ServiceRole.admin) for s in services]
    rows = db.execute(
        select(Service, ServiceMembership.role)
        .join(ServiceMembership, Service.id == ServiceMembership.service_id)
        .where(ServiceMembership.user_id == user.id)
        .order_by(Service.name)
    ).all()
    return [ServiceWithRoleOut(**ServiceOut.model_validate(s).model_dump(), role=role) for s, role in rows]


# ── Membership management (service admin) ───────────────────────────────────

@router.get("/services/{service_id}/members", response_model=list[ServiceMemberOut])
def list_members(service_id: int, _membership: ServiceMemberDep, db: DbDep) -> list[ServiceMembership]:
    return list(
        db.execute(select(ServiceMembership).where(ServiceMembership.service_id == service_id)).scalars()
    )


@router.post("/services/{service_id}/members", response_model=ServiceMemberOut, status_code=status.HTTP_201_CREATED)
def add_member(service_id: int, body: ServiceMemberCreate, _admin: ServiceAdminDep, db: DbDep) -> ServiceMembership:
    if not db.get(User, body.user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    existing = db.execute(
        select(ServiceMembership).where(
            ServiceMembership.service_id == service_id,
            ServiceMembership.user_id == body.user_id,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "user already a member")
    membership = ServiceMembership(user_id=body.user_id, service_id=service_id, role=body.role)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


@router.patch("/services/{service_id}/members/{user_id}", response_model=ServiceMemberOut)
def update_member_role(
    service_id: int, user_id: int, body: ServiceMemberUpdate, _admin: ServiceAdminDep, db: DbDep
) -> ServiceMembership:
    membership = db.execute(
        select(ServiceMembership).where(
            ServiceMembership.service_id == service_id,
            ServiceMembership.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "member not found")
    membership.role = body.role
    db.commit()
    db.refresh(membership)
    return membership


@router.delete("/services/{service_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(service_id: int, user_id: int, _admin: ServiceAdminDep, db: DbDep) -> None:
    membership = db.execute(
        select(ServiceMembership).where(
            ServiceMembership.service_id == service_id,
            ServiceMembership.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "member not found")
    db.delete(membership)
    db.commit()

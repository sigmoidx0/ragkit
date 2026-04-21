"""Auth: Bearer JWT in Authorization header (no OAuth2 password flow)."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ServiceMembership, ServiceRole, SuperAdmin, User
from app.db.session import get_db
from app.security.tokens import decode_token


def is_superadmin(db: Session, user_id: int) -> bool:
    return db.get(SuperAdmin, user_id) is not None


def _parse_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip() or None
    return None


def get_bearer_token(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> str:
    token = _parse_bearer(authorization)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing Bearer token")
    return token


DbDep = Annotated[Session, Depends(get_db)]
BearerDep = Annotated[str, Depends(get_bearer_token)]


def get_current_user(db: DbDep, token: BearerDep) -> User:
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


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_service_or_user(
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


ServiceOrUser = Annotated[User | None, Depends(get_service_or_user)]


def get_service_membership(
    service_id: int,
    user: CurrentUser,
    db: DbDep,
) -> ServiceMembership:
    """Return the calling user's membership in the given service.

    Superadmins bypass the membership table and get a virtual admin membership.
    """
    if is_superadmin(db, user.id):
        return ServiceMembership(user_id=user.id, service_id=service_id, role=ServiceRole.admin)
    membership = db.execute(
        select(ServiceMembership).where(
            ServiceMembership.user_id == user.id,
            ServiceMembership.service_id == service_id,
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a member of this service")
    return membership


ServiceMemberDep = Annotated[ServiceMembership, Depends(get_service_membership)]


def require_service_writer(membership: ServiceMemberDep) -> ServiceMembership:
    if membership.role == ServiceRole.viewer:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "viewers cannot write")
    return membership


def require_service_admin(membership: ServiceMemberDep) -> ServiceMembership:
    if membership.role != ServiceRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "service admin only")
    return membership


def require_superadmin(user: CurrentUser, db: DbDep) -> User:
    if not is_superadmin(db, user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "superadmin only")
    return user


ServiceWriterDep = Annotated[ServiceMembership, Depends(require_service_writer)]
ServiceAdminDep = Annotated[ServiceMembership, Depends(require_service_admin)]
SuperAdminDep = Annotated[User, Depends(require_superadmin)]

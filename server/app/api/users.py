"""Users API: superadmin-only user management."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.db.models import User
from app.schemas.users import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(_user: CurrentUser, db: DbDep) -> list[User]:
    return list(db.execute(select(User).order_by(User.email)).scalars())

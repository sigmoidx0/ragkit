"""Users API: user listing (authenticated) and creation (superadmin only)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep, SuperAdminDep
from app.db.models import User
from app.schemas.users import UserCreate, UserOut
from app.security.passwords import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(_user: CurrentUser, db: DbDep) -> list[User]:
    return list(db.execute(select(User).order_by(User.email)).scalars())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, _admin: SuperAdminDep, db: DbDep) -> User:
    if db.execute(select(User).where(User.email == body.email)).scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered")
    user = User(email=body.email, hashed_password=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

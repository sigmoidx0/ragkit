"""Login returns a JWT; use `Authorization: Bearer <token>` on other routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbDep
from app.core.config import get_settings
from app.db.models import SuperAdmin, User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.users import UserOut
from app.security.passwords import verify_password
from app.security.tokens import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbDep) -> TokenResponse:
    user = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid email or password")
    settings = get_settings()
    token = create_access_token(subject=str(user.id), extra_claims={"email": user.email})
    return TokenResponse(
        access_token=token, expires_in=settings.jwt.access_token_ttl_minutes * 60
    )


@router.get("/me", response_model=UserOut)
def me(current: CurrentUser, db: DbDep) -> UserOut:
    return UserOut.model_validate(current).model_copy(
        update={"is_superadmin": db.get(SuperAdmin, current.id) is not None}
    )

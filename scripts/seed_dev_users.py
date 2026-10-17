#!/usr/bin/env python3
"""Populate the dev DB with demo accounts covering all workspace roles.

Run from the project root:
    cd server && python ../scripts/seed_dev_users.py

Accounts after seeding
----------------------
SuperAdmin
  platform.admin@ragkit.io   maple.forest9

Default workspace
  alice.morgan@ragkit.io     harbor.tide4   admin
  bob.chen@ragkit.io         silver.peak6   member
  clara.kim@ragkit.io        river.stone2   viewer

제조 workspace
  bob.chen@ragkit.io         (same)         member
  dan.okafor@ragkit.io       echo.trail7    viewer

금융 workspace
  elena.park@ragkit.io       golden.gate5   member
  felix.wu@ragkit.io         winter.cove3   viewer
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from project root or server/
server_dir = Path(__file__).resolve().parent.parent / "server"
sys.path.insert(0, str(server_dir))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SuperAdmin, User, Workspace, WorkspaceMembership, WorkspaceRole
from app.db.session import SessionLocal
from app.security.passwords import hash_password

USERS: list[dict] = [
    {"email": "platform.admin@ragkit.io", "password": "maple.forest9",  "super_admin": True},
    {"email": "alice.morgan@ragkit.io",   "password": "harbor.tide4"},
    {"email": "bob.chen@ragkit.io",       "password": "silver.peak6"},
    {"email": "clara.kim@ragkit.io",      "password": "river.stone2"},
    {"email": "dan.okafor@ragkit.io",     "password": "echo.trail7"},
    {"email": "elena.park@ragkit.io",     "password": "golden.gate5"},
    {"email": "felix.wu@ragkit.io",       "password": "winter.cove3"},
]

# (user_email, workspace_slug, role)
MEMBERSHIPS: list[tuple[str, str, WorkspaceRole]] = [
    ("platform.admin@ragkit.io", "default",     WorkspaceRole.admin),
    ("alice.morgan@ragkit.io",   "default",     WorkspaceRole.admin),
    ("bob.chen@ragkit.io",       "default",     WorkspaceRole.member),
    ("clara.kim@ragkit.io",      "default",     WorkspaceRole.viewer),
    ("bob.chen@ragkit.io",       "manufacture", WorkspaceRole.member),
    ("dan.okafor@ragkit.io",     "manufacture", WorkspaceRole.viewer),
    ("elena.park@ragkit.io",     "finance",     WorkspaceRole.member),
    ("felix.wu@ragkit.io",       "finance",     WorkspaceRole.viewer),
]

OLD_ADMIN_EMAIL = "admin@example.com"
NEW_ADMIN_EMAIL = "platform.admin@ragkit.io"
NEW_ADMIN_PASSWORD = "maple.forest9"


def _get_or_create_user(db: Session, email: str, password: str) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        user = User(email=email, hashed_password=hash_password(password))
        db.add(user)
        db.flush()
        print(f"  created  {email}")
    else:
        print(f"  exists   {email}")
    return user


def seed(db: Session) -> None:
    # Rename the bootstrap admin if the old placeholder still exists
    old_admin = db.execute(select(User).where(User.email == OLD_ADMIN_EMAIL)).scalar_one_or_none()
    if old_admin:
        old_admin.email = NEW_ADMIN_EMAIL
        old_admin.hashed_password = hash_password(NEW_ADMIN_PASSWORD)
        db.flush()
        print(f"  renamed  {OLD_ADMIN_EMAIL} -> {NEW_ADMIN_EMAIL}")

    # Upsert all demo users
    user_map: dict[str, User] = {}
    print("\nUsers:")
    for u in USERS:
        user = _get_or_create_user(db, u["email"], u["password"])
        user_map[u["email"]] = user
        if u.get("super_admin"):
            exists = db.execute(select(SuperAdmin).where(SuperAdmin.user_id == user.id)).first()
            if not exists:
                db.add(SuperAdmin(user_id=user.id))
                print(f"  granted  super_admin -> {u['email']}")

    # Upsert memberships
    workspace_map: dict[str, Workspace] = {}
    for svc in db.execute(select(Workspace)).scalars():
        workspace_map[svc.slug] = svc

    print("\nMemberships:")
    for email, slug, role in MEMBERSHIPS:
        svc = workspace_map.get(slug)
        if svc is None:
            print(f"  SKIP     {email} / {slug} (workspace not found)")
            continue
        user = user_map.get(email)
        if user is None:
            print(f"  SKIP     {email} / {slug} (user not found)")
            continue
        existing = db.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == user.id,
                WorkspaceMembership.workspace_id == svc.id,
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(WorkspaceMembership(user_id=user.id, workspace_id=svc.id, role=role))
            print(f"  added    {email} @ {slug} [{role.value}]")
        else:
            existing.role = role
            print(f"  updated  {email} @ {slug} [{role.value}]")

    db.commit()
    print("\nDone.")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()

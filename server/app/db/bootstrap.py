"""Create the first admin user, with a default workspace and agent, when the database is empty."""

from __future__ import annotations

import logging
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Agent, SuperAdmin, User, Workspace, WorkspaceMembership, WorkspaceRole
from app.security.passwords import hash_password

logger = logging.getLogger(__name__)


def bootstrap_admin(db: Session) -> None:
    settings = get_settings()
    if db.execute(select(User.id).limit(1)).first():
        return

    password_env = settings.admin_bootstrap.password_env
    password = os.getenv(password_env)
    if not password:
        logger.warning("No users yet and %s is not set — skipping bootstrap", password_env)
        return

    user = User(
        email=settings.admin_bootstrap.email,
        hashed_password=hash_password(password),
    )
    db.add(user)
    db.flush()
    db.add(SuperAdmin(user_id=user.id))

    workspace = Workspace(name="Default", slug="default")
    db.add(workspace)
    db.flush()
    db.add(Agent(workspace_id=workspace.id, name="Default"))
    db.add(WorkspaceMembership(user_id=user.id, workspace_id=workspace.id, role=WorkspaceRole.admin))
    db.commit()
    logger.info("Bootstrapped superadmin %s with a default workspace and agent", user.email)

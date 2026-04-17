"""Create the first admin user when the database is empty."""

from __future__ import annotations

import logging
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import User
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

    db.add(
        User(
            email=settings.admin_bootstrap.email,
            hashed_password=hash_password(password),
        )
    )
    db.commit()
    logger.info("Bootstrapped user %s", settings.admin_bootstrap.email)

"""add agent_config to services

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("services", sa.Column("agent_config", sa.JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("services", "agent_config")

"""add chat_turn_sources table

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_turn_sources",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer,
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("turn_index", sa.Integer, nullable=False),
        sa.Column("sources_json", sa.JSON, nullable=False, server_default="[]"),
        sa.UniqueConstraint("session_id", "turn_index", name="uq_turn_sources"),
    )


def downgrade() -> None:
    op.drop_table("chat_turn_sources")

"""add message_feedback; snapshot the system prompt on eval runs

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_feedback",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("service_id", sa.Integer, sa.ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_index", sa.Integer, nullable=False),
        sa.Column("rating", sa.SmallInteger, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("session_id", "turn_index", name="uq_feedback_turn"),
        sa.CheckConstraint("rating IN (-1, 1)", name="ck_feedback_rating"),
    )
    with op.batch_alter_table("eval_runs") as batch:
        batch.add_column(sa.Column("prompt_name", sa.String(255), nullable=True))
        batch.add_column(sa.Column("system_prompt", sa.Text, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("eval_runs") as batch:
        batch.drop_column("system_prompt")
        batch.drop_column("prompt_name")
    op.drop_table("message_feedback")

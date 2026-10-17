"""add mcp_servers (per workspace) and mcp_tool_calls (audit + pending approvals)

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "workspace_id", sa.Integer, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("auth_env_var", sa.String(128), nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("tools", sa.JSON, nullable=True),
        sa.Column("tools_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", "name", name="uq_mcp_server_name"),
    )
    op.create_table(
        "mcp_tool_calls",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("agent_id", sa.Integer, sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "session_id", sa.Integer, sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=True, index=True
        ),
        sa.Column("server_id", sa.Integer, sa.ForeignKey("mcp_servers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("server_name", sa.String(255), nullable=False),
        sa.Column("tool", sa.String(255), nullable=False),
        sa.Column("args", sa.JSON, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("interrupt_id", sa.String(64), nullable=True, unique=True),
        sa.Column("run_options", sa.JSON, nullable=True),
        sa.Column("requested_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_args", sa.JSON, nullable=True),
        sa.Column("result", sa.Text, nullable=True),
        sa.Column("is_error", sa.Boolean, nullable=False, server_default=sa.false()),
        *_timestamps(),
    )


def downgrade() -> None:
    op.drop_table("mcp_tool_calls")
    op.drop_table("mcp_servers")

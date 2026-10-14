"""drop orphan is_superadmin column from users

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The column only exists in databases first built by `create_all` from an
    # older model; 0001 never creates it. Drop it where present so a fresh
    # database (e.g. a new Postgres) migrates cleanly too.
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    if "is_superadmin" not in columns:
        return
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("is_superadmin")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("is_superadmin", sa.Boolean(), nullable=False, server_default="0"))

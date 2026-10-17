"""agents with no document sets now search nothing — keep existing ones whole

Until now an agent with no document sets searched every document in its
workspace. That default is gone: an agent searches only its sets. So that an
upgrade doesn't silently empty existing agents, each workspace with such an
agent and with documents gets an "All documents" set holding its current
documents, and those agents select it.

Downgrade leaves the sets in place: under the old rule they still give the
same scope.

Revision ID: 0015
Revises: 0014
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SET_NAME = "All documents"

_agents = sa.table(
    "agents",
    sa.column("id", sa.Integer),
    sa.column("workspace_id", sa.Integer),
    sa.column("agent_config", sa.JSON),
)
_documents = sa.table("documents", sa.column("id", sa.Integer), sa.column("workspace_id", sa.Integer))
_sets = sa.table(
    "document_sets",
    sa.column("id", sa.Integer),
    sa.column("workspace_id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("description", sa.Text),
)
_members = sa.table(
    "document_set_documents", sa.column("document_set_id", sa.Integer), sa.column("document_id", sa.Integer)
)


def upgrade() -> None:
    conn = op.get_bind()
    by_workspace: dict[int, list[tuple[int, dict]]] = {}
    for agent_id, workspace_id, cfg in conn.execute(sa.select(_agents.c.id, _agents.c.workspace_id, _agents.c.agent_config)):
        cfg = dict(cfg or {})
        if not cfg.get("document_set_ids"):
            by_workspace.setdefault(workspace_id, []).append((agent_id, cfg))

    for workspace_id, agents in by_workspace.items():
        doc_ids = list(conn.execute(sa.select(_documents.c.id).where(_documents.c.workspace_id == workspace_id)).scalars())
        if not doc_ids:
            continue  # nothing to lose
        taken = set(conn.execute(sa.select(_sets.c.name).where(_sets.c.workspace_id == workspace_id)).scalars())
        name, n = SET_NAME, 2
        while name in taken:
            name, n = f"{SET_NAME} ({n})", n + 1
        set_id = conn.execute(
            sa.insert(_sets)
            .values(workspace_id=workspace_id, name=name, description="Created on upgrade: every document at the time")
            .returning(_sets.c.id)
        ).scalar_one()
        conn.execute(sa.insert(_members), [{"document_set_id": set_id, "document_id": d} for d in doc_ids])
        for agent_id, cfg in agents:
            cfg["document_set_ids"] = [set_id]
            conn.execute(sa.update(_agents).where(_agents.c.id == agent_id).values(agent_config=cfg))


def downgrade() -> None:
    pass

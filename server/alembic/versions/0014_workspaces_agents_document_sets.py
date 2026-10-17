"""services → workspaces; agents as their own table; document sets

A service used to be both the tenant (members, documents) and the agent (model,
router, chats). This splits the two: the tenant becomes a workspace, and each
workspace gets agents of its own. Existing data maps one-to-one — every service
becomes a workspace with a single agent of the same name, which takes over the
service's agent config, system prompts, chat sessions, eval runs and feedback.
Agent configs refer to delegates by id; those pointed at services and are
rewritten to point at the agents that replace them.

SQLite can't drop a column that carries a foreign key, and Alembic's batch mode
rebuilds tables from reflection — which silently dropped ON DELETE CASCADE and
named UNIQUE constraints on tables whose foreign keys are declared inline. So on
SQLite the affected tables are rebuilt from the explicit target schemas below;
Postgres takes plain ALTER statements, which keep every constraint.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-15
"""
from collections.abc import Callable
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables whose owner moves from the service (now workspace) to its agent.
AGENT_OWNED = ("system_prompts", "chat_sessions", "eval_runs", "message_feedback")


def _ts() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _owner_fk(col: str, table: str) -> sa.Column:
    return sa.Column(col, sa.Integer, sa.ForeignKey(f"{table}.id", ondelete="CASCADE"), nullable=False)


# Target schemas, parameterised by the owner column so upgrade (agent_id →
# agents) and downgrade (service_id → workspaces) share one definition each.
SCHEMAS: dict[str, Callable[[str, str], list]] = {
    "system_prompts": lambda col, ref: [
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        _owner_fk(col, ref),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_ts(),
    ],
    "chat_sessions": lambda col, ref: [
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        _owner_fk(col, ref),
        sa.Column("title", sa.String(255), nullable=True),
        *_ts(),
    ],
    "eval_runs": lambda col, ref: [
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        _owner_fk(col, ref),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("config_snapshot", sa.JSON, nullable=False),
        sa.Column("cases", sa.JSON, nullable=False),
        sa.Column("results", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("summary", sa.JSON, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        *_ts(),
        sa.Column("prompt_name", sa.String(255), nullable=True),
        sa.Column("system_prompt", sa.Text, nullable=True),
    ],
    "message_feedback": lambda col, ref: [
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        _owner_fk(col, ref),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("turn_index", sa.Integer, nullable=False),
        sa.Column("rating", sa.SmallInteger, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        *_ts(),
        sa.UniqueConstraint("session_id", "turn_index", name="uq_feedback_turn"),
        sa.CheckConstraint("rating IN (-1, 1)", name="ck_feedback_rating"),
    ],
}

# Extra indexes each table carries besides the owner column's.
EXTRA_INDEXES = {"chat_sessions": [("ix_chat_sessions_user_id", ["user_id"])]}


def _memberships_schema(col: str, ref: str, unique_name: str) -> list:
    return [
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        _owner_fk(col, ref),
        sa.Column("role", sa.String(6), nullable=False),
        *_ts(),
        sa.UniqueConstraint("user_id", col, name=unique_name),
    ]


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def _sqlite_rebuild(name: str, new_name: str, schema: list, select_sql: str, indexes: list) -> None:
    """Recreate `name` as `new_name` with an explicit schema and copy the rows.

    Referenced tables are declared as stubs only so SQLAlchemy can render the
    REFERENCES clauses; they are never created. Foreign keys aren't enforced
    on Alembic's connection, so dropping the old table cascades nothing.
    """
    bind = op.get_bind()
    md = sa.MetaData()
    for stub in ("users", "workspaces", "agents", "chat_sessions"):
        sa.Table(stub, md, sa.Column("id", sa.Integer, primary_key=True))
    tmp = sa.Table(f"_new_{new_name}", md, *schema)
    tmp.create(bind)
    cols = ", ".join(c.name for c in tmp.columns)
    bind.execute(sa.text(f"INSERT INTO _new_{new_name} ({cols}) {select_sql}"))
    op.drop_table(name)
    op.rename_table(f"_new_{new_name}", new_name)
    for ix_name, ix_cols in indexes:
        op.create_index(ix_name, new_name, ix_cols)


def _copy_select(table: str, owner_col: str, owner_expr: str) -> str:
    """SELECT for one rebuilt table: every column as-is, the owner recomputed."""
    names = [c.name for c in SCHEMAS[table]("x", "y") if isinstance(c, sa.Column)]
    exprs = [owner_expr if n == "x" else n for n in names]
    return f"SELECT {', '.join(exprs)} FROM {table}"  # noqa: S608 — fixed identifiers


_agents = sa.table(
    "agents",
    sa.column("id", sa.Integer),
    sa.column("workspace_id", sa.Integer),
    sa.column("agent_config", sa.JSON),
)


def _remap_delegates(mapping: dict[int, int], configs: list[tuple[int, dict | None]], table) -> None:
    """Rewrite `delegates` id lists in stored configs through `mapping`."""
    bind = op.get_bind()
    for row_id, cfg in configs:
        if not cfg or not cfg.get("delegates"):
            continue
        cfg = {**cfg, "delegates": [mapping[d] for d in cfg["delegates"] if d in mapping]}
        bind.execute(table.update().where(table.c.id == row_id).values(agent_config=cfg))


def _rename_owner_column(table: str, old: str, new: str) -> None:
    """Rename a plain foreign-key column; both backends keep its constraint."""
    op.drop_index(f"ix_{table}_{old}", table_name=table)
    op.execute(f'ALTER TABLE {table} RENAME COLUMN {old} TO {new}')
    op.create_index(f"ix_{table}_{new}", table, [new])


def upgrade() -> None:
    bind = op.get_bind()

    # Rows left behind by deleted sessions: SQLite never enforced the cascades.
    for table in ("chat_turn_sources", "message_feedback"):
        bind.execute(sa.text(
            f"DELETE FROM {table} WHERE session_id NOT IN (SELECT id FROM chat_sessions)"  # noqa: S608
        ))

    # ── tenant: services → workspaces ──
    op.drop_index("ix_services_slug", table_name="services")
    op.rename_table("services", "workspaces")
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"], unique=True)

    if _is_sqlite():
        _sqlite_rebuild(
            "service_memberships", "workspace_memberships",
            _memberships_schema("workspace_id", "workspaces", "uq_user_workspace"),
            "SELECT id, user_id, service_id, role, created_at, updated_at FROM service_memberships", [],
        )
    else:
        op.rename_table("service_memberships", "workspace_memberships")
        op.execute("ALTER TABLE workspace_memberships RENAME CONSTRAINT uq_user_service TO uq_user_workspace")
        op.execute("ALTER TABLE workspace_memberships RENAME COLUMN service_id TO workspace_id")

    _rename_owner_column("documents", "service_id", "workspace_id")
    _rename_owner_column("pipelines", "service_id", "workspace_id")

    # ── agents: one per existing workspace, inheriting its settings ──
    op.create_table(
        "agents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("agent_config", sa.JSON, nullable=True),
        *_ts(),
    )
    op.create_index("ix_agents_workspace_id", "agents", ["workspace_id"])
    bind.execute(sa.text(
        "INSERT INTO agents (workspace_id, name, agent_config, created_at, updated_at) "
        "SELECT id, name, agent_config, created_at, updated_at FROM workspaces ORDER BY id"
    ))
    rows = bind.execute(sa.select(_agents.c.id, _agents.c.workspace_id, _agents.c.agent_config)).all()
    _remap_delegates({ws: agent for agent, ws, _ in rows}, [(agent, cfg) for agent, _, cfg in rows], _agents)
    op.execute("ALTER TABLE workspaces DROP COLUMN agent_config")

    # ── agent-owned rows follow their service's agent ──
    owner = "(SELECT a.id FROM agents a WHERE a.workspace_id = {t}.service_id)"
    for table in AGENT_OWNED:
        indexes = [(f"ix_{table}_agent_id", ["agent_id"]), *EXTRA_INDEXES.get(table, [])]
        if _is_sqlite():
            _sqlite_rebuild(
                table, table, SCHEMAS[table]("agent_id", "agents"),
                _copy_select(table, "agent_id", owner.format(t=table)), indexes,
            )
        else:
            op.add_column(table, sa.Column("agent_id", sa.Integer, nullable=True))
            op.execute(f"UPDATE {table} SET agent_id = {owner.format(t=table)}")
            op.drop_index(f"ix_{table}_service_id", table_name=table)
            op.drop_column(table, "service_id")
            op.alter_column(table, "agent_id", nullable=False, existing_type=sa.Integer)
            op.create_foreign_key(f"fk_{table}_agent_id", table, "agents", ["agent_id"], ["id"], ondelete="CASCADE")
            op.create_index(f"ix_{table}_agent_id", table, ["agent_id"])

    # ── document sets ──
    op.create_table(
        "document_sets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Integer, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        *_ts(),
        sa.UniqueConstraint("workspace_id", "name", name="uq_document_set_name"),
    )
    op.create_index("ix_document_sets_workspace_id", "document_sets", ["workspace_id"])
    op.create_table(
        "document_set_documents",
        sa.Column("document_set_id", sa.Integer, sa.ForeignKey("document_sets.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("ix_document_set_documents_document_id", "document_set_documents", ["document_id"])


def downgrade() -> None:
    """Back to one agent per service. Extra agents (and their chats, prompts,
    evals, feedback) are folded into the workspace's first agent; document sets
    are dropped. Lossy by nature — services could only ever hold one agent."""
    bind = op.get_bind()

    op.drop_table("document_set_documents")
    op.drop_table("document_sets")

    owner = "(SELECT a.workspace_id FROM agents a WHERE a.id = {t}.agent_id)"
    for table in AGENT_OWNED:
        indexes = [(f"ix_{table}_service_id", ["service_id"]), *EXTRA_INDEXES.get(table, [])]
        if _is_sqlite():
            _sqlite_rebuild(
                table, table, SCHEMAS[table]("service_id", "workspaces"),
                _copy_select(table, "service_id", owner.format(t=table)), indexes,
            )
        else:
            op.add_column(table, sa.Column("service_id", sa.Integer, nullable=True))
            op.execute(f"UPDATE {table} SET service_id = {owner.format(t=table)}")
            op.drop_index(f"ix_{table}_agent_id", table_name=table)
            op.drop_column(table, "agent_id")
            op.alter_column(table, "service_id", nullable=False, existing_type=sa.Integer)
            op.create_foreign_key(
                f"fk_{table}_service_id", table, "workspaces", ["service_id"], ["id"], ondelete="CASCADE"
            )
            op.create_index(f"ix_{table}_service_id", table, ["service_id"])

    op.add_column("workspaces", sa.Column("agent_config", sa.JSON, nullable=True))
    rows = bind.execute(
        sa.select(_agents.c.id, _agents.c.workspace_id, _agents.c.agent_config).order_by(_agents.c.id)
    ).all()
    first_agent: dict[int, dict | None] = {}
    for _, ws, cfg in rows:
        first_agent.setdefault(ws, cfg)
    workspaces = sa.table("workspaces", sa.column("id", sa.Integer), sa.column("agent_config", sa.JSON))
    for ws, cfg in first_agent.items():
        bind.execute(workspaces.update().where(workspaces.c.id == ws).values(agent_config=cfg))
    _remap_delegates({agent: ws for agent, ws, _ in rows}, list(first_agent.items()), workspaces)
    op.drop_index("ix_agents_workspace_id", table_name="agents")
    op.drop_table("agents")

    _rename_owner_column("pipelines", "workspace_id", "service_id")
    _rename_owner_column("documents", "workspace_id", "service_id")

    if _is_sqlite():
        _sqlite_rebuild(
            "workspace_memberships", "service_memberships",
            _memberships_schema("service_id", "workspaces", "uq_user_service"),
            "SELECT id, user_id, workspace_id, role, created_at, updated_at FROM workspace_memberships", [],
        )
    else:
        op.execute("ALTER TABLE workspace_memberships RENAME COLUMN workspace_id TO service_id")
        op.execute("ALTER TABLE workspace_memberships RENAME CONSTRAINT uq_user_workspace TO uq_user_service")
        op.rename_table("workspace_memberships", "service_memberships")

    op.drop_index("ix_workspaces_slug", table_name="workspaces")
    op.rename_table("workspaces", "services")
    op.create_index("ix_services_slug", "services", ["slug"], unique=True)

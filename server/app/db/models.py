"""ORM models: minimal user + document (A option: chunks not stored in RDB)."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UTCDateTime


class DocumentStatus(str, enum.Enum):
    pending = "pending"
    chunking = "chunking"
    embedding = "embedding"
    indexed = "indexed"
    failed = "failed"


class WorkspaceRole(str, enum.Enum):
    admin = "admin"
    member = "member"
    viewer = "viewer"


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)


class SuperAdmin(Base):
    __tablename__ = "super_admins"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class Workspace(TimestampMixin, Base):
    """The tenant: who can see what. Members, documents, document sets and
    pipelines belong to a workspace; its agents share them."""

    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)


class WorkspaceMembership(TimestampMixin, Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (UniqueConstraint("user_id", "workspace_id", name="uq_user_workspace"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    workspace_id: Mapped[int] = mapped_column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[WorkspaceRole] = mapped_column(
        Enum(WorkspaceRole, name="workspace_role", native_enum=False),
        nullable=False,
    )


class Agent(TimestampMixin, Base):
    """An assistant inside a workspace. A workspace can have many; each has its
    own model, router, retrieval scope (document sets), prompts, chats and evals."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Model, retrieval, router, delegation and landing-card settings. Parsed and
    # validated through app.schemas.agent_config.AgentConfig; NULL means defaults.
    agent_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", native_enum=False),
        nullable=False,
        default=DocumentStatus.pending,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(255), nullable=True)


class DocumentSet(TimestampMixin, Base):
    """A named group of a workspace's documents. A document can be in many sets;
    an agent searches the sets it selects (or every document if it selects none)."""

    __tablename__ = "document_sets"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_document_set_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class DocumentSetDocument(Base):
    __tablename__ = "document_set_documents"

    document_set_id: Mapped[int] = mapped_column(Integer, ForeignKey("document_sets.id", ondelete="CASCADE"), primary_key=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True, index=True)


class SystemPrompt(TimestampMixin, Base):
    __tablename__ = "system_prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ChatTurnSources(Base):
    """Sources retrieved for each assistant turn, keyed by (session_id, turn_index)."""
    __tablename__ = "chat_turn_sources"
    __table_args__ = (UniqueConstraint("session_id", "turn_index", name="uq_turn_sources"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    sources_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)


class ChatTurnLog(TimestampMixin, Base):
    """What happened on one answered turn, for finding where an agent falls short.

    The headline signal is `cited_count == 0` on a route that searched: vector
    search nearly always returns top_k hits, so "no sources" says little, but an
    answer that cites none of what it found is one the documents didn't support
    — usually "the documents don't cover this".
    """

    __tablename__ = "chat_turn_logs"
    __table_args__ = (UniqueConstraint("session_id", "turn_index", name="uq_turn_log"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    # Same answer index as ChatTurnSources and MessageFeedback.
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # The user's words, and the standalone rewrite routing and search acted on —
    # the one that still makes sense out of the chat (e.g. as an eval case).
    question: Mapped[str] = mapped_column(Text, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    route: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Distinct [N] markers in the answer that name a source it actually found.
    cited_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class McpServer(TimestampMixin, Base):
    """A remote MCP server registered in a workspace; its agents can use its tools.

    Only streamable-HTTP servers: a stdio server would run a process on this
    host, which a workspace admin must not be able to do. The token is never
    stored — `auth_env_var` names the environment variable holding it.
    """

    __tablename__ = "mcp_servers"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_mcp_server_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    auth_env_var: Mapped[str | None] = mapped_column(String(128), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # The server's tool list as of the last refresh: name, description,
    # input_schema, read_only. Agents pick from this; runs build tools from it
    # without a round trip to the server.
    tools: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    tools_refreshed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ToolCallStatus(str, enum.Enum):
    auto = "auto"          # ran without asking (approval not required)
    pending = "pending"    # waiting for the user
    approved = "approved"  # the user approved; it ran
    rejected = "rejected"  # the user declined; it did not run
    expired = "expired"    # the conversation moved on (an edit) before a decision


class McpToolCall(TimestampMixin, Base):
    """One MCP tool call by an agent — the audit trail, and the pending approval
    a paused run waits on (`interrupt_id` names the interrupt to resume)."""

    __tablename__ = "mcp_tool_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    # Null for runs outside a chat session (stateless chat, evaluations).
    session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    server_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("mcp_servers.id", ondelete="SET NULL"), nullable=True)
    server_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tool: Mapped[str] = mapped_column(String(255), nullable=False)
    args: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[ToolCallStatus] = mapped_column(Enum(ToolCallStatus, native_enum=False, length=16), nullable=False)
    interrupt_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    # How the paused run was started, so the resume rebuilds the same graph.
    run_options: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    requested_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # Arguments as approved, when the user edited them.
    approved_args: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PipelineStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class Pipeline(TimestampMixin, Base):
    __tablename__ = "pipelines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    graph_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[PipelineStatus] = mapped_column(
        Enum(PipelineStatus, name="pipeline_status", native_enum=False),
        nullable=False,
        default=PipelineStatus.draft,
        server_default=PipelineStatus.draft.value,
    )


class EvalRun(TimestampMixin, Base):
    """One evaluation: a question set run against a snapshot of an agent's config.

    The config is snapshotted so a run stays interpretable after the agent's
    settings change — which is the point when comparing two runs.
    """

    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")  # pending|running|done|failed
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    cases: Mapped[list[Any]] = mapped_column(JSON, nullable=False)
    # One entry per case, appended as each finishes so the UI can show progress.
    results: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The system prompt the run used, copied in at creation so a later edit or
    # activation of another prompt can't change what a past run measured.
    prompt_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)


class MessageFeedback(TimestampMixin, Base):
    """A user's 👍/👎 on one assistant answer.

    The question and answer are copied from the chat history when the rating
    is saved, so feedback stays readable — and importable into an evaluation —
    even after the session is deleted or the history format changes.
    """

    __tablename__ = "message_feedback"
    __table_args__ = (
        UniqueConstraint("session_id", "turn_index", name="uq_feedback_turn"),
        CheckConstraint("rating IN (-1, 1)", name="ck_feedback_rating"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(Integer, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Which assistant answer in the session, counting from 0 — the same index
    # ChatTurnSources uses.
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # +1 or -1
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

"""ORM models: minimal user + document (A option: chunks not stored in RDB)."""

from __future__ import annotations

import enum
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

from app.db.base import Base, TimestampMixin


class DocumentStatus(str, enum.Enum):
    pending = "pending"
    chunking = "chunking"
    embedding = "embedding"
    indexed = "indexed"
    failed = "failed"


class ServiceRole(str, enum.Enum):
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


class Service(TimestampMixin, Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Per-agent settings (model, retrieval, router, landing card). Parsed and
    # validated through app.schemas.agent_config.AgentConfig; NULL means defaults.
    agent_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class ServiceMembership(TimestampMixin, Base):
    __tablename__ = "service_memberships"
    __table_args__ = (UniqueConstraint("user_id", "service_id", name="uq_user_service"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[ServiceRole] = mapped_column(
        Enum(ServiceRole, name="service_role", native_enum=False),
        nullable=False,
    )


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
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


class SystemPrompt(TimestampMixin, Base):
    __tablename__ = "system_prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ChatSession(TimestampMixin, Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ChatTurnSources(Base):
    """Sources retrieved for each assistant turn, keyed by (session_id, turn_index)."""
    __tablename__ = "chat_turn_sources"
    __table_args__ = (UniqueConstraint("session_id", "turn_index", name="uq_turn_sources"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    sources_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)


class PipelineStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class Pipeline(TimestampMixin, Base):
    __tablename__ = "pipelines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
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
    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
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
    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Which assistant answer in the session, counting from 0 — the same index
    # ChatTurnSources uses.
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # +1 or -1
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)

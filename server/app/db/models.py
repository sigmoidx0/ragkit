"""ORM models: minimal user + document (A option: chunks not stored in RDB)."""

from __future__ import annotations

import enum

from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
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

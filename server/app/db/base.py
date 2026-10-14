"""SQLAlchemy declarative base."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """A timestamp that always comes back timezone-aware, in UTC.

    Postgres `timestamptz` already does this, but SQLite has no time zone type
    and returns naive datetimes. Serialized without an offset, those were read
    by browsers as *local* time — every timestamp showed 9 hours off in Korea.
    Values are stored in UTC either way (`now()` / CURRENT_TIMESTAMP is UTC),
    so tagging naive ones as UTC on the way out is exact, not a guess.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

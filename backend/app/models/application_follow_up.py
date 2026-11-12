
"""Persistent application follow-up tasks and audit events."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApplicationFollowUp(Base):
    __tablename__ = "application_follow_ups"

    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "kind",
            "due_at",
            name="uq_follow_up_application_kind_due",
        ),
        CheckConstraint(
            "kind IN ('status_check', 'follow_up')",
            name="ck_follow_up_kind",
        ),
        CheckConstraint(
            "state IN ('pending', 'completed', 'dismissed')",
            name="ck_follow_up_state",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "applications.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    kind: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )

    note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    resolution_note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ApplicationFollowUpEvent(Base):
    __tablename__ = "application_follow_up_events"

    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'created', 'completed', 'dismissed', 'auto_closed')",
            name="ck_follow_up_event_type",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    follow_up_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "application_follow_ups.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    actor: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

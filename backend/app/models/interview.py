"""Interviews and persistent in-app reminders."""

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


class Interview(Base):
    __tablename__ = "interviews"

    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled')",
            name="ck_interview_status",
        ),
        CheckConstraint(
            "mode IN ('video', 'phone', 'onsite')",
            name="ck_interview_mode",
        ),
        CheckConstraint(
            "ends_at > starts_at",
            name="ck_interview_valid_interval",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_interview_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(150), nullable=False
    )

    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    mode: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    location_or_link: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    notes: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="scheduled"
    )

    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
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


class InterviewNotification(Base):
    __tablename__ = "interview_notifications"

    __table_args__ = (
        UniqueConstraint(
            "interview_id",
            "minutes_before",
            name="uq_interview_notification_offset",
        ),
        CheckConstraint(
            "minutes_before IN (0, 60, 1440)",
            name="ck_interview_notification_offset",
        ),
        CheckConstraint(
            "state IN ('scheduled', 'available', 'read', 'cancelled')",
            name="ck_interview_notification_state",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    interview_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    minutes_before: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="scheduled",
        index=True,
    )

    available_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
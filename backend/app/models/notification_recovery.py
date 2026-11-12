
"""Persistent audit records for notification recovery runs."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationRecoveryRun(Base):
    __tablename__ = "notification_recovery_runs"

    __table_args__ = (
        CheckConstraint(
            "scanned >= 0 AND released >= 0 AND cancelled >= 0",
            name="ck_notification_recovery_counts",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "candidate_profiles.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    scanned: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    released: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    cancelled: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

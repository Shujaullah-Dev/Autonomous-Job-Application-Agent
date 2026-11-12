
"""Persist prepared manual application handoffs."""

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


class SubmissionHandoff(Base):
    __tablename__ = "submission_handoffs"

    __table_args__ = (
        UniqueConstraint(
            "application_id",
            "revision_number",
            name="uq_submission_handoff_revision",
        ),
        CheckConstraint(
            "revision_number >= 1",
            name="ck_submission_handoff_revision_positive",
        ),
        CheckConstraint(
            "status = 'prepared'",
            name="ck_submission_handoff_prepared_only",
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

    revision_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    provider_hint: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    destination_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="prepared",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
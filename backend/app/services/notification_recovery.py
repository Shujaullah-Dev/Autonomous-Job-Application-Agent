
"""Inspect and reconcile interview notifications safely."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.candidate import CandidateProfile
from app.models.interview import Interview, InterviewNotification
from app.models.notification_recovery import NotificationRecoveryRun


class RecoveryCandidateNotFound(Exception):
    pass


@dataclass(frozen=True)
class RecoveryResult:
    candidate_id: uuid.UUID
    scanned: int
    released: int
    cancelled: int
    dry_run: bool
    limit: int
    checked_at: datetime
    run_id: uuid.UUID | None = None


def utc_value(value: datetime) -> datetime:
    """Normalize SQLite-naive and PostgreSQL-aware UTC values."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def reconcile_notifications(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    dry_run: bool,
    limit: int = 100,
    now: datetime | None = None,
) -> RecoveryResult:
    """
    Repair only candidate-scoped scheduled notifications.

    - Eligible overdue reminders become available.
    - Expired/inactive reminders become cancelled.
    - Read or already available reminders are never modified.
    - One audit row is saved only when changes occur.
    """

    if not 1 <= limit <= 200:
        raise ValueError("limit must be 1..200")

    current = utc_value(now or datetime.now(UTC))

    candidate_query = select(CandidateProfile.id).where(
        CandidateProfile.id == candidate_id
    )

    if not dry_run:
        candidate_query = candidate_query.with_for_update()

    if db.scalar(candidate_query) is None:
        raise RecoveryCandidateNotFound()

    statement = (
        select(
            InterviewNotification,
            Interview.status,
            Interview.ends_at,
            Application.status,
        )
        .join(
            Interview,
            Interview.id == InterviewNotification.interview_id,
        )
        .join(
            Application,
            Application.id == Interview.application_id,
        )
        .where(
            Application.candidate_id == candidate_id,
            InterviewNotification.state == "scheduled",
            or_(
                InterviewNotification.due_at <= current,
                Interview.ends_at <= current,
                Interview.status != "scheduled",
                Application.status != "interview",
            ),
        )
        .order_by(
            InterviewNotification.due_at.asc(),
            InterviewNotification.id.asc(),
        )
        .limit(limit)
    )

    if not dry_run:
        statement = statement.with_for_update(
            of=InterviewNotification,
            skip_locked=True,
        )

    rows = db.execute(statement).all()

    released = 0
    cancelled = 0

    for notification, interview_status, ends_at, application_status in rows:
        stale = (
            interview_status != "scheduled"
            or application_status != "interview"
            or utc_value(ends_at) <= current
        )

        if stale:
            cancelled += 1

            if not dry_run:
                notification.state = "cancelled"

        elif utc_value(notification.due_at) <= current:
            released += 1

            if not dry_run:
                notification.state = "available"
                notification.available_at = current

    run_id = None

    if not dry_run and (released or cancelled):
        audit = NotificationRecoveryRun(
            candidate_id=candidate_id,
            scanned=len(rows),
            released=released,
            cancelled=cancelled,
        )
        db.add(audit)
        db.flush()
        run_id = audit.id

    if not dry_run:
        db.commit()

    return RecoveryResult(
        candidate_id=candidate_id,
        scanned=len(rows),
        released=released,
        cancelled=cancelled,
        dry_run=dry_run,
        limit=limit,
        checked_at=current,
        run_id=run_id,
    )

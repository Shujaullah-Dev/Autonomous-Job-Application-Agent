"""Interview scheduling and in-app notification services."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.candidate import CandidateProfile
from app.models.interview import Interview, InterviewNotification
from app.services.application_tracking import get_application

UTC = timezone.utc  # noqa: UP017


class InterviewConflict(Exception):
    pass


class InterviewNotFound(Exception):
    pass


VALID_REMINDERS = {0, 60, 1440}
MAX_DAYS_AHEAD = 365
MAX_DURATION = timedelta(hours=6)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InterviewConflict("A timezone offset is required")
    return value.astimezone(UTC)


def validate_interval(
    starts_at: datetime,
    ends_at: datetime,
    *,
    now: datetime,
) -> tuple[datetime, datetime]:
    start = as_utc(starts_at)
    end = as_utc(ends_at)
    current = as_utc(now)

    if start <= current:
        raise InterviewConflict("Interview must start in the future")
    if end <= start:
        raise InterviewConflict("End time must follow start time")
    if end - start > MAX_DURATION:
        raise InterviewConflict("Interview cannot exceed 6 hours")
    if start > current + timedelta(days=MAX_DAYS_AHEAD):
        raise InterviewConflict("Interview is too far in the future")

    return start, end


def lock_candidate(db: Session, candidate_id: uuid.UUID) -> None:
    """Serialize interview changes per candidate on PostgreSQL."""
    db.scalar(
        select(CandidateProfile.id)
        .where(CandidateProfile.id == candidate_id)
        .with_for_update()
    )


def check_overlap(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    start: datetime,
    end: datetime,
    exclude_id: uuid.UUID | None = None,
) -> None:
    statement = (
        select(Interview.id)
        .join(Application, Application.id == Interview.application_id)
        .where(
            Application.candidate_id == candidate_id,
            Interview.status == "scheduled",
            Interview.starts_at < end,
            Interview.ends_at > start,
        )
    )

    if exclude_id is not None:
        statement = statement.where(Interview.id != exclude_id)

    if db.scalar(statement.limit(1)) is not None:
        raise InterviewConflict(
            "Another scheduled interview overlaps this time"
        )


def get_interview(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    interview_id: uuid.UUID,
    lock: bool = False,
) -> Interview:
    statement = (
        select(Interview)
        .join(Application, Application.id == Interview.application_id)
        .where(
            Interview.id == interview_id,
            Application.candidate_id == candidate_id,
        )
    )

    if lock:
        statement = statement.with_for_update()

    interview = db.scalar(statement)

    if interview is None:
        raise InterviewNotFound()

    return interview


def sync_reminders(
    db: Session,
    *,
    interview: Interview,
    offsets: tuple[int, ...],
    now: datetime,
) -> None:
    """Create/rebuild reminders after interview creation or rescheduling."""

    if len(set(offsets)) != len(offsets):
        raise InterviewConflict("Duplicate reminder offsets")

    if not set(offsets).issubset(VALID_REMINDERS):
        raise InterviewConflict("Invalid reminder offset")

    existing = {
        item.minutes_before: item
        for item in db.scalars(
            select(InterviewNotification).where(
                InterviewNotification.interview_id == interview.id
            )
        ).all()
    }

    for offset, item in existing.items():
        if offset not in offsets:
            item.state = "cancelled"

    for offset in offsets:
        due = interview.starts_at - timedelta(minutes=offset)
        item = existing.get(offset)

        # Never create an already-missed advance reminder.
        if due <= now:
            if item is not None:
                item.state = "cancelled"
            continue

        if item is None:
            db.add(
                InterviewNotification(
                    interview_id=interview.id,
                    minutes_before=offset,
                    due_at=due,
                    state="scheduled",
                )
            )
        else:
            # A rescheduled interview needs fresh reminders.
            item.due_at = due
            item.state = "scheduled"
            item.available_at = None
            item.read_at = None


def stop_reminders(db: Session, interview_id: uuid.UUID) -> None:
    """Stop reminders that have not been acknowledged as read."""

    items = db.scalars(
        select(InterviewNotification).where(
            InterviewNotification.interview_id == interview_id,
            InterviewNotification.state.in_(["scheduled", "available"]),
        )
    ).all()

    for item in items:
        item.state = "cancelled"


def create_interview(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    title: str,
    starts_at: datetime,
    ends_at: datetime,
    mode: str,
    location_or_link: str | None = None,
    notes: str | None = None,
    reminder_minutes: tuple[int, ...] = (1440, 60),
    now: datetime | None = None,
) -> Interview:
    current = as_utc(now or datetime.now(UTC))
    start, end = validate_interval(starts_at, ends_at, now=current)

    if mode not in {"video", "phone", "onsite"}:
        raise InterviewConflict("Invalid interview mode")
    if not title.strip():
        raise InterviewConflict("Interview title is required")

    application = get_application(
        db,
        candidate_id=candidate_id,
        application_id=application_id,
        lock=True,
    )
    lock_candidate(db, candidate_id)

    if application.status != "interview":
        raise InterviewConflict(
            "Application must be in interview status"
        )

    check_overlap(
        db, candidate_id=candidate_id, start=start, end=end
    )

    interview = Interview(
        application_id=application.id,
        title=title.strip(),
        starts_at=start,
        ends_at=end,
        mode=mode,
        location_or_link=location_or_link,
        notes=notes,
        status="scheduled",
        version=1,
    )

    db.add(interview)
    db.flush()

    sync_reminders(
        db,
        interview=interview,
        offsets=reminder_minutes,
        now=current,
    )

    db.commit()
    db.refresh(interview)
    return interview


def reschedule_interview(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    interview_id: uuid.UUID,
    expected_version: int,
    starts_at: datetime,
    ends_at: datetime,
    reminder_minutes: tuple[int, ...],
    now: datetime | None = None,
) -> Interview:
    current = as_utc(now or datetime.now(UTC))
    start, end = validate_interval(starts_at, ends_at, now=current)

    interview = get_interview(
        db, candidate_id=candidate_id,
        interview_id=interview_id, lock=True,
    )
    lock_candidate(db, candidate_id)

    application = get_application(
        db,
        candidate_id=candidate_id,
        application_id=interview.application_id,
    )

    if application.status != "interview":
        raise InterviewConflict("Application is no longer in interview")
    if interview.status != "scheduled":
        raise InterviewConflict("Interview is not scheduled")
    if interview.version != expected_version:
        raise InterviewConflict("Stale interview version")

    check_overlap(
        db,
        candidate_id=candidate_id,
        start=start,
        end=end,
        exclude_id=interview.id,
    )

    interview.starts_at = start
    interview.ends_at = end
    interview.version += 1

    sync_reminders(
        db, interview=interview,
        offsets=reminder_minutes, now=current,
    )

    db.commit()
    db.refresh(interview)
    return interview


def finish_interview(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    interview_id: uuid.UUID,
    expected_version: int,
    action: str,
    now: datetime | None = None,
) -> Interview:
    current = as_utc(now or datetime.now(UTC))
    interview = get_interview(
        db, candidate_id=candidate_id,
        interview_id=interview_id, lock=True,
    )

    if interview.status != "scheduled":
        raise InterviewConflict("Interview is already resolved")
    if interview.version != expected_version:
        raise InterviewConflict("Stale interview version")
    if action not in {"complete", "cancel"}:
        raise InterviewConflict("Invalid interview action")

    scheduled_start = interview.starts_at
    if scheduled_start.tzinfo is None:
        scheduled_start = scheduled_start.replace(tzinfo=UTC)

    if action == "complete" and current < scheduled_start:
        raise InterviewConflict(
            "Cannot mark a future interview completed"
        )

    interview.status = (
        "completed" if action == "complete" else "cancelled"
    )
    interview.version += 1
    stop_reminders(db, interview.id)

    db.commit()
    db.refresh(interview)
    return interview


def publish_due_notifications(
    db: Session,
    *,
    candidate_id: uuid.UUID | None = None,
    now: datetime | None = None,
    limit: int = 100,
) -> int:
    """
    Move due reminders into the in-app inbox.

    No email, push notification or external action occurs.
    """
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")

    current = as_utc(now or datetime.now(UTC))

    statement = (
        select(InterviewNotification)
        .join(
            Interview,
            Interview.id == InterviewNotification.interview_id,
        )
        .join(
            Application,
            Application.id == Interview.application_id,
        )
        .where(
            InterviewNotification.state == "scheduled",
            InterviewNotification.due_at <= current,
            Interview.status == "scheduled",
            Interview.ends_at > current,
            Application.status == "interview",
        )
        .order_by(
            InterviewNotification.due_at,
            InterviewNotification.id,
        )
        .limit(limit)
        .with_for_update(skip_locked=True)
    )

    if candidate_id is not None:
        statement = statement.where(
            Application.candidate_id == candidate_id
        )

    items = db.scalars(statement).all()

    for item in items:
        item.state = "available"
        item.available_at = current

    db.commit()
    return len(items)


def mark_notification_read(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    notification_id: uuid.UUID,
    now: datetime | None = None,
) -> InterviewNotification:
    notification = db.scalar(
        select(InterviewNotification)
        .join(
            Interview,
            Interview.id == InterviewNotification.interview_id,
        )
        .join(
            Application,
            Application.id == Interview.application_id,
        )
        .where(
            InterviewNotification.id == notification_id,
            Application.candidate_id == candidate_id,
        )
        .with_for_update()
    )

    if notification is None:
        raise InterviewNotFound()

    if notification.state == "read":
        return notification

    if notification.state != "available":
        raise InterviewConflict(
            "Only available in-app notifications can be read"
        )

    notification.state = "read"
    notification.read_at = as_utc(now or datetime.now(UTC))
    db.commit()
    db.refresh(notification)
    return notification
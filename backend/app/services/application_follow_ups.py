
"""Schedule and resolve application follow-ups."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application_follow_up import (
    ApplicationFollowUp,
    ApplicationFollowUpEvent,
)
from app.services.application_tracking import get_application

UTC = timezone.utc  # noqa: UP017


class FollowUpConflict(Exception):
    pass


class FollowUpNotFound(Exception):
    pass


ACTIVE_APPLICATION_STATES = {"submitted", "interview"}
TERMINAL_APPLICATION_STATES = {
    "offered",
    "rejected",
    "withdrawn",
}
MAX_FOLLOW_UP_DAYS = 365


def utc_datetime(value: datetime) -> datetime:
    """Normalize an offset-aware datetime to UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise FollowUpConflict(
            "Follow-up time must include a timezone offset"
        )

    return value.astimezone(UTC)


def schedule_follow_up(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    kind: str,
    due_at: datetime,
    note: str | None = None,
    now: datetime | None = None,
) -> ApplicationFollowUp:
    """
    Schedule a follow-up for an actually tracked submission.

    Does not send notifications or employer messages.
    """

    if kind not in {"status_check", "follow_up"}:
        raise FollowUpConflict("Unsupported follow-up kind")

    current_time = utc_datetime(now or datetime.now(UTC))
    due = utc_datetime(due_at)

    if due <= current_time:
        raise FollowUpConflict(
            "Follow-up due date must be in the future"
        )

    if due > current_time + timedelta(
        days=MAX_FOLLOW_UP_DAYS
    ):
        raise FollowUpConflict(
            "Follow-up cannot be more than 365 days ahead"
        )

    application = get_application(
        db,
        candidate_id=candidate_id,
        application_id=application_id,
        lock=True,
    )

    if application.status not in ACTIVE_APPLICATION_STATES:
        raise FollowUpConflict(
            "Follow-ups require submitted or interview status"
        )

    existing = db.scalar(
        select(ApplicationFollowUp.id).where(
            ApplicationFollowUp.application_id
            == application.id,
            ApplicationFollowUp.kind == kind,
            ApplicationFollowUp.due_at == due,
        )
    )

    if existing is not None:
        raise FollowUpConflict(
            "This follow-up already exists"
        )

    follow_up = ApplicationFollowUp(
        application_id=application.id,
        kind=kind,
        due_at=due,
        state="pending",
        note=note,
    )

    db.add(follow_up)
    db.flush()

    db.add(
        ApplicationFollowUpEvent(
            follow_up_id=follow_up.id,
            event_type="created",
            actor="api_caller",
            note=note,
        )
    )

    db.commit()
    db.refresh(follow_up)

    return follow_up


def get_follow_up(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    follow_up_id: uuid.UUID,
    lock: bool = False,
) -> ApplicationFollowUp:
    """Require candidate and application ownership match."""

    application = get_application(
        db,
        candidate_id=candidate_id,
        application_id=application_id,
        lock=lock,
    )

    query = select(ApplicationFollowUp).where(
        ApplicationFollowUp.id == follow_up_id,
        ApplicationFollowUp.application_id == application.id,
    )

    if lock:
        query = query.with_for_update()

    follow_up = db.scalar(query)

    if follow_up is None:
        raise FollowUpNotFound()

    return follow_up


def resolve_follow_up(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    follow_up_id: uuid.UUID,
    action: str,
    resolution_note: str | None = None,
    now: datetime | None = None,
) -> ApplicationFollowUp:
    """Complete or dismiss a pending reminder."""

    if action not in {"complete", "dismiss"}:
        raise FollowUpConflict("Invalid follow-up action")

    follow_up = get_follow_up(
        db,
        candidate_id=candidate_id,
        application_id=application_id,
        follow_up_id=follow_up_id,
        lock=True,
    )

    if follow_up.state != "pending":
        raise FollowUpConflict(
            "Follow-up has already been resolved"
        )

    event_type = (
        "completed" if action == "complete" else "dismissed"
    )

    follow_up.state = (
        "completed" if action == "complete" else "dismissed"
    )

    follow_up.resolved_at = utc_datetime(
        now or datetime.now(UTC)
    )
    follow_up.resolution_note = resolution_note

    db.add(
        ApplicationFollowUpEvent(
            follow_up_id=follow_up.id,
            event_type=event_type,
            actor="api_caller",
            note=resolution_note,
        )
    )

    db.commit()
    db.refresh(follow_up)

    return follow_up

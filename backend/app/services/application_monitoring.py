
"""Read-only application and follow-up monitoring."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.application_follow_up import ApplicationFollowUp

UTC = timezone.utc  # noqa: UP017

FollowUpWindow = Literal[
    "all",
    "overdue",
    "next_7_days",
]


def list_candidate_follow_ups(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    application_id: uuid.UUID | None = None,
    state: str | None = None,
    window: FollowUpWindow = "all",
    limit: int = 20,
    offset: int = 0,
    now: datetime | None = None,
) -> tuple[int, list[tuple[ApplicationFollowUp, str]]]:
    """
    List follow-ups with filters and pagination.

    Overdue and next-7-days views only include pending tasks.
    """

    current = now or datetime.now(UTC)

    filters = [
        Application.candidate_id == candidate_id,
    ]

    if application_id is not None:
        filters.append(
            ApplicationFollowUp.application_id
            == application_id
        )

    if state is not None:
        filters.append(ApplicationFollowUp.state == state)

    if window == "overdue":
        filters.extend(
            [
                ApplicationFollowUp.state == "pending",
                ApplicationFollowUp.due_at <= current,
            ]
        )

    elif window == "next_7_days":
        filters.extend(
            [
                ApplicationFollowUp.state == "pending",
                ApplicationFollowUp.due_at > current,
                ApplicationFollowUp.due_at
                <= current + timedelta(days=7),
            ]
        )

    join_condition = (
        Application.id == ApplicationFollowUp.application_id
    )

    total = db.scalar(
        select(func.count(ApplicationFollowUp.id))
        .join(Application, join_condition)
        .where(*filters)
    ) or 0

    rows = db.execute(
        select(
            ApplicationFollowUp,
            Application.job_title,
        )
        .join(Application, join_condition)
        .where(*filters)
        .order_by(
            ApplicationFollowUp.due_at.asc(),
            ApplicationFollowUp.id.asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    return total, [
        (follow_up, job_title)
        for follow_up, job_title in rows
    ]


def application_monitoring_summary(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    now: datetime | None = None,
) -> dict:
    """Calculate counts for the candidate's monitoring dashboard."""

    current = now or datetime.now(UTC)

    status_rows = db.execute(
        select(
            Application.status,
            func.count(Application.id),
        )
        .where(Application.candidate_id == candidate_id)
        .group_by(Application.status)
    ).all()

    status_counts = {
        status: count
        for status, count in status_rows
    }

    join_condition = (
        Application.id == ApplicationFollowUp.application_id
    )

    def count_follow_ups(*extra_filters) -> int:
        return db.scalar(
            select(func.count(ApplicationFollowUp.id))
            .join(Application, join_condition)
            .where(
                Application.candidate_id == candidate_id,
                *extra_filters,
            )
        ) or 0

    pending = count_follow_ups(
        ApplicationFollowUp.state == "pending"
    )

    overdue = count_follow_ups(
        ApplicationFollowUp.state == "pending",
        ApplicationFollowUp.due_at <= current,
    )

    due_soon = count_follow_ups(
        ApplicationFollowUp.state == "pending",
        ApplicationFollowUp.due_at > current,
        ApplicationFollowUp.due_at
        <= current + timedelta(days=7),
    )

    return {
        "total_applications": sum(status_counts.values()),
        "applications_by_status": status_counts,
        "pending_follow_ups": pending,
        "overdue_follow_ups": overdue,
        "due_next_7_days": due_soon,
        "checked_at": current,
    }

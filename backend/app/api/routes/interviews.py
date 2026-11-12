"""Interviews, calendar export and in-app notification inbox."""

import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from app.api.routes.jobs import require_dev_write_key
from app.db.session import get_db
from app.models.application import Application
from app.models.interview import Interview, InterviewNotification
from app.schemas.interview import (
    InterviewAction,
    InterviewCreate,
    InterviewDetail,
    InterviewList,
    InterviewRead,
    InterviewReminderRead,
    InterviewReschedule,
    NotificationItem,
    NotificationList,
    NotificationRefreshResult,
)
from app.services.application_tracking import ApplicationNotFound
from app.services.interview_calendar import render_interview_calendar
from app.services.interview_scheduling import (
    InterviewConflict,
    InterviewNotFound,
    create_interview,
    finish_interview,
    get_interview,
    mark_notification_read,
    publish_due_notifications,
    reschedule_interview,
)
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

UTC = timezone.utc  # noqa: UP017


router = APIRouter(
    prefix="/api/v1/candidates",
    tags=["Interviews and Notifications"],
    dependencies=[Depends(require_dev_write_key)],
)


def interview_detail(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    interview_id: uuid.UUID,
) -> InterviewDetail:
    interview = get_interview(
        db,
        candidate_id=candidate_id,
        interview_id=interview_id,
    )

    reminders = db.scalars(
        select(InterviewNotification)
        .where(InterviewNotification.interview_id == interview.id)
        .order_by(InterviewNotification.minutes_before.desc())
    ).all()

    details = InterviewRead.model_validate(interview).model_dump()

    return InterviewDetail(
        **details,
        reminders=[
            InterviewReminderRead.model_validate(row)
            for row in reminders
        ],
    )


def notification_item(
    row: tuple,
) -> NotificationItem:
    notice, interview_title, job_title, starts_at = row

    data = InterviewReminderRead.model_validate(
        notice
    ).model_dump()

    return NotificationItem(
        **data,
        interview_title=interview_title,
        job_title=job_title,
        interview_starts_at=starts_at,
    )


@router.post(
    "/{candidate_id}/applications/{application_id}/interviews",
    response_model=InterviewDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_application_interview(
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    payload: InterviewCreate,
    db: Annotated[Session, Depends(get_db)],
) -> InterviewDetail:
    try:
        interview = create_interview(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            title=payload.title,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            mode=payload.mode,
            location_or_link=payload.location_or_link,
            notes=payload.notes,
            reminder_minutes=tuple(payload.reminder_minutes),
        )

        return interview_detail(
            db, candidate_id=candidate_id, interview_id=interview.id
        )

    except ApplicationNotFound:
        db.rollback()
        raise HTTPException(404, "Application not found") from None
    except InterviewConflict as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from None
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Interview constraint conflict") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Database unavailable") from None


@router.get(
    "/{candidate_id}/interviews",
    response_model=InterviewList,
)
def list_candidate_interviews(
    candidate_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    interview_status: Literal[
        "scheduled", "completed", "cancelled"
    ] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InterviewList:
    filters = [Application.candidate_id == candidate_id]

    if interview_status is not None:
        filters.append(Interview.status == interview_status)

    try:
        total = db.scalar(
            select(func.count(Interview.id))
            .join(Application, Application.id == Interview.application_id)
            .where(*filters)
        ) or 0

        rows = db.scalars(
            select(Interview)
            .join(Application, Application.id == Interview.application_id)
            .where(*filters)
            .order_by(Interview.starts_at, Interview.id)
            .offset(offset)
            .limit(limit)
        ).all()

        return InterviewList(
            total=total,
            limit=limit,
            offset=offset,
            items=[InterviewRead.model_validate(row) for row in rows],
        )

    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable") from None


@router.get(
    "/{candidate_id}/interviews/{interview_id}",
    response_model=InterviewDetail,
)
def read_candidate_interview(
    candidate_id: uuid.UUID,
    interview_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> InterviewDetail:
    try:
        return interview_detail(
            db, candidate_id=candidate_id, interview_id=interview_id
        )
    except InterviewNotFound:
        raise HTTPException(404, "Interview not found") from None
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable") from None


@router.patch(
    "/{candidate_id}/interviews/{interview_id}",
    response_model=InterviewDetail,
)
def update_interview_schedule(
    candidate_id: uuid.UUID,
    interview_id: uuid.UUID,
    payload: InterviewReschedule,
    db: Annotated[Session, Depends(get_db)],
) -> InterviewDetail:
    try:
        reschedule_interview(
            db,
            candidate_id=candidate_id,
            interview_id=interview_id,
            expected_version=payload.expected_version,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            reminder_minutes=tuple(payload.reminder_minutes),
        )
        return interview_detail(
            db, candidate_id=candidate_id, interview_id=interview_id
        )

    except (InterviewNotFound, ApplicationNotFound):
        db.rollback()
        raise HTTPException(404, "Interview not found") from None
    except InterviewConflict as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from None
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Interview constraint conflict") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Database unavailable") from None


@router.post(
    "/{candidate_id}/interviews/{interview_id}/action",
    response_model=InterviewDetail,
)
def update_interview_state(
    candidate_id: uuid.UUID,
    interview_id: uuid.UUID,
    payload: InterviewAction,
    db: Annotated[Session, Depends(get_db)],
) -> InterviewDetail:
    try:
        finish_interview(
            db,
            candidate_id=candidate_id,
            interview_id=interview_id,
            expected_version=payload.expected_version,
            action=payload.action,
        )
        return interview_detail(
            db, candidate_id=candidate_id, interview_id=interview_id
        )
    except InterviewNotFound:
        db.rollback()
        raise HTTPException(404, "Interview not found") from None
    except InterviewConflict as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Database unavailable") from None


@router.get(
    "/{candidate_id}/interviews/{interview_id}/calendar.ics",
)
def download_interview_calendar(
    candidate_id: uuid.UUID,
    interview_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        interview = get_interview(
            db, candidate_id=candidate_id, interview_id=interview_id
        )

        application = db.get(Application, interview.application_id)

        if application is None:
            raise HTTPException(404, "Application not found")

        contents = render_interview_calendar(
            interview,
            job_title=application.job_title,
            company_name=application.company_name,
        )

        return Response(
            content=contents,
            media_type="text/calendar; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="interview-{interview.id}.ics"'
                ),
                "Cache-Control": "private, no-store",
            },
        )

    except InterviewNotFound:
        raise HTTPException(404, "Interview not found") from None
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable") from None


@router.post(
    "/{candidate_id}/interview-notifications/refresh",
    response_model=NotificationRefreshResult,
)
def refresh_interview_notifications(
    candidate_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> NotificationRefreshResult:
    try:
        checked_at = datetime.now(UTC)
        count = publish_due_notifications(
            db,
            candidate_id=candidate_id,
            now=checked_at,
            limit=limit,
        )
        return NotificationRefreshResult(
            released=count,
            checked_at=checked_at,
            message=(
                "Due notifications made available in-app. "
                "No email or push notification was sent."
            ),
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Database unavailable") from None


@router.get(
    "/{candidate_id}/interview-notifications",
    response_model=NotificationList,
)
def list_interview_notifications(
    candidate_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    unread_only: bool = True,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NotificationList:
    states = ["available"] if unread_only else ["available", "read"]

    filters = [
        Application.candidate_id == candidate_id,
        InterviewNotification.state.in_(states),
    ]

    join_interview = (
        Interview.id == InterviewNotification.interview_id
    )
    join_application = (
        Application.id == Interview.application_id
    )

    try:
        total = db.scalar(
            select(func.count(InterviewNotification.id))
            .join(Interview, join_interview)
            .join(Application, join_application)
            .where(*filters)
        ) or 0

        rows = db.execute(
            select(
                InterviewNotification,
                Interview.title,
                Application.job_title,
                Interview.starts_at,
            )
            .join(Interview, join_interview)
            .join(Application, join_application)
            .where(*filters)
            .order_by(
                InterviewNotification.available_at.desc(),
                InterviewNotification.id.desc(),
            )
            .limit(limit)
        ).all()

        return NotificationList(
            total=total,
            items=[notification_item(row) for row in rows],
        )
    except SQLAlchemyError:
        raise HTTPException(503, "Database unavailable") from None


@router.post(
    "/{candidate_id}/interview-notifications/{notification_id}/read",
    response_model=NotificationItem,
)
def acknowledge_interview_notification(
    candidate_id: uuid.UUID,
    notification_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> NotificationItem:
    try:
        mark_notification_read(
            db,
            candidate_id=candidate_id,
            notification_id=notification_id,
        )

        row = db.execute(
            select(
                InterviewNotification,
                Interview.title,
                Application.job_title,
                Interview.starts_at,
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
                InterviewNotification.id == notification_id,
                Application.candidate_id == candidate_id,
            )
        ).one()

        return notification_item(row)

    except InterviewNotFound:
        db.rollback()
        raise HTTPException(404, "Notification not found") from None
    except InterviewConflict as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Database unavailable") from None
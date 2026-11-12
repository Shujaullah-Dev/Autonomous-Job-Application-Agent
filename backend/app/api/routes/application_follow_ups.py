
"""Application follow-up and monitoring endpoints."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from app.api.routes.jobs import require_dev_write_key
from app.db.session import get_db
from app.models.application_follow_up import (
    ApplicationFollowUpEvent,
)
from app.schemas.application_follow_up import (
    ApplicationMonitoringResponse,
    FollowUpCreateRequest,
    FollowUpDetailResponse,
    FollowUpEventRead,
    FollowUpListItem,
    FollowUpListResponse,
    FollowUpRead,
    FollowUpResolveRequest,
    FollowUpState,
)
from app.services.application_follow_ups import (
    FollowUpConflict,
    FollowUpNotFound,
    get_follow_up,
    resolve_follow_up,
    schedule_follow_up,
)
from app.services.application_monitoring import (
    application_monitoring_summary,
    list_candidate_follow_ups,
)
from app.services.application_tracking import (
    ApplicationNotFound,
    get_application,
)
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/v1/candidates",
    tags=["Application Follow-Ups"],
    dependencies=[Depends(require_dev_write_key)],
)


def read_follow_up_detail(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    follow_up_id: uuid.UUID,
) -> FollowUpDetailResponse:
    follow_up = get_follow_up(
        db,
        candidate_id=candidate_id,
        application_id=application_id,
        follow_up_id=follow_up_id,
    )

    history = db.scalars(
        select(ApplicationFollowUpEvent)
        .where(
            ApplicationFollowUpEvent.follow_up_id
            == follow_up.id
        )
        .order_by(ApplicationFollowUpEvent.id)
    ).all()

    data = FollowUpRead.model_validate(follow_up).model_dump()

    return FollowUpDetailResponse(
        **data,
        history=[
            FollowUpEventRead.model_validate(event)
            for event in history
        ],
    )


@router.post(
    "/{candidate_id}/applications/{application_id}/follow-ups",
    response_model=FollowUpDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_application_follow_up(
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    payload: FollowUpCreateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> FollowUpDetailResponse:
    try:
        task = schedule_follow_up(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            kind=payload.kind,
            due_at=payload.due_at,
            note=payload.note,
        )

        return read_follow_up_detail(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            follow_up_id=task.id,
        )

    except ApplicationNotFound:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        ) from None

    except FollowUpConflict as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from None

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Duplicate follow-up or constraint conflict",
        ) from None

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Could not schedule follow-up",
        ) from None


@router.get(
    "/{candidate_id}/applications/{application_id}/follow-ups",
    response_model=FollowUpListResponse,
)
def list_application_follow_ups(
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[
        int, Query(ge=1, le=100)
    ] = 20,
    offset: Annotated[
        int, Query(ge=0)
    ] = 0,
) -> FollowUpListResponse:
    try:
        get_application(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
        )

        total, rows = list_candidate_follow_ups(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            limit=limit,
            offset=offset,
        )

        return FollowUpListResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=[
                FollowUpListItem(
                    **FollowUpRead.model_validate(
                        task
                    ).model_dump(),
                    job_title=job_title,
                )
                for task, job_title in rows
            ],
        )

    except ApplicationNotFound:
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        ) from None

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from None


@router.get(
    "/{candidate_id}/follow-ups",
    response_model=FollowUpListResponse,
)
def list_all_candidate_follow_ups(
    candidate_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    state: FollowUpState | None = None,
    window: Literal[
        "all",
        "overdue",
        "next_7_days",
    ] = "all",
    limit: Annotated[
        int, Query(ge=1, le=100)
    ] = 20,
    offset: Annotated[
        int, Query(ge=0)
    ] = 0,
) -> FollowUpListResponse:
    if window != "all" and state not in {None, "pending"}:
        raise HTTPException(
            status_code=422,
            detail="Date-window filters require pending state",
        )

    try:
        total, rows = list_candidate_follow_ups(
            db,
            candidate_id=candidate_id,
            state=state,
            window=window,
            limit=limit,
            offset=offset,
        )

        return FollowUpListResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=[
                FollowUpListItem(
                    **FollowUpRead.model_validate(
                        task
                    ).model_dump(),
                    job_title=job_title,
                )
                for task, job_title in rows
            ],
        )

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from None


@router.post(
    "/{candidate_id}/applications/{application_id}"
    "/follow-ups/{follow_up_id}/resolve",
    response_model=FollowUpDetailResponse,
)
def resolve_application_follow_up(
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    follow_up_id: uuid.UUID,
    payload: FollowUpResolveRequest,
    db: Annotated[Session, Depends(get_db)],
) -> FollowUpDetailResponse:
    try:
        task = resolve_follow_up(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            follow_up_id=follow_up_id,
            action=payload.action,
            resolution_note=payload.resolution_note,
        )

        return read_follow_up_detail(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            follow_up_id=task.id,
        )

    except (ApplicationNotFound, FollowUpNotFound):
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail="Follow-up not found",
        ) from None

    except FollowUpConflict as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from None

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Could not resolve follow-up",
        ) from None


@router.get(
    "/{candidate_id}/application-monitoring",
    response_model=ApplicationMonitoringResponse,
)
def get_application_monitoring(
    candidate_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ApplicationMonitoringResponse:
    try:
        snapshot = application_monitoring_summary(
            db,
            candidate_id=candidate_id,
            now=datetime.now(UTC),
        )

        return ApplicationMonitoringResponse(
            candidate_id=candidate_id,
            **snapshot,
            message=(
                "On-demand application monitoring only. "
                "No background notifications or employer "
                "messages have been sent."
            ),
        )

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from None

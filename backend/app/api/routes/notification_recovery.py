
"""Development-only readiness and recovery endpoints."""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from app.api.routes.jobs import require_dev_write_key
from app.db.session import get_db
from app.models.candidate import CandidateProfile
from app.models.notification_recovery import NotificationRecoveryRun
from app.schemas.notification_recovery import (
    ReadinessResponse,
    RecoveryApplyRequest,
    RecoveryResponse,
    RecoveryRunList,
    RecoveryRunRead,
)
from app.services.notification_recovery import (
    RecoveryCandidateNotFound,
    RecoveryResult,
    reconcile_notifications,
)
from app.services.reliability import read_with_retry
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

UTC = timezone.utc  # noqa: UP017

router = APIRouter(
    tags=["Reliability and Recovery"],
    dependencies=[Depends(require_dev_write_key)],
)


def response_from_result(
    result: RecoveryResult,
) -> RecoveryResponse:
    if result.dry_run:
        message = (
            "Preview only. No notification records were changed."
        )
    else:
        message = (
            "Recovery processed in the database. "
            "No external notifications or messages were sent."
        )

    return RecoveryResponse(
        candidate_id=result.candidate_id,
        scanned=result.scanned,
        released=result.released,
        cancelled=result.cancelled,
        dry_run=result.dry_run,
        limit=result.limit,
        checked_at=result.checked_at,
        run_id=result.run_id,
        message=message,
    )


@router.get(
    "/api/v1/ops/readiness",
    response_model=ReadinessResponse,
)
def check_readiness(
    db: Annotated[Session, Depends(get_db)],
) -> ReadinessResponse:
    """Verify database connectivity using a safe read-only retry."""

    try:
        read_with_retry(
            db,
            lambda: db.execute(text("SELECT 1")).scalar_one(),
        )

        return ReadinessResponse(
            status="ready",
            database="connected",
            checked_at=datetime.now(UTC),
        )

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database is not ready",
            headers={"Retry-After": "5"},
        ) from None


@router.get(
    "/api/v1/candidates/{candidate_id}/notification-recovery/preview",
    response_model=RecoveryResponse,
)
def preview_notification_recovery(
    candidate_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> RecoveryResponse:
    """Inspect recoverable notifications without modifying data."""

    try:
        result = reconcile_notifications(
            db,
            candidate_id=candidate_id,
            dry_run=True,
            limit=limit,
        )
        return response_from_result(result)

    except RecoveryCandidateNotFound:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        ) from None

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Recovery inspection unavailable",
        ) from None


@router.post(
    "/api/v1/candidates/{candidate_id}/notification-recovery/apply",
    response_model=RecoveryResponse,
)
def apply_notification_recovery(
    candidate_id: uuid.UUID,
    payload: RecoveryApplyRequest,
    db: Annotated[Session, Depends(get_db)],
) -> RecoveryResponse:
    """Perform confirmed, candidate-scoped notification repair."""

    try:
        result = reconcile_notifications(
            db,
            candidate_id=candidate_id,
            dry_run=False,
            limit=payload.limit,
        )
        return response_from_result(result)

    except RecoveryCandidateNotFound:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        ) from None

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Recovery failed; transaction rolled back",
        ) from None


@router.get(
    "/api/v1/candidates/{candidate_id}/notification-recovery/runs",
    response_model=RecoveryRunList,
)
def list_recovery_runs(
    candidate_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RecoveryRunList:
    try:
        if db.get(CandidateProfile, candidate_id) is None:
            raise HTTPException(404, "Candidate not found")

        base = select(NotificationRecoveryRun).where(
            NotificationRecoveryRun.candidate_id == candidate_id
        )

        total = db.scalar(
            select(func.count(NotificationRecoveryRun.id)).where(
                NotificationRecoveryRun.candidate_id == candidate_id
            )
        ) or 0

        runs = db.scalars(
            base.order_by(
                NotificationRecoveryRun.created_at.desc(),
                NotificationRecoveryRun.id.desc(),
            ).limit(limit)
        ).all()

        return RecoveryRunList(
            total=total,
            items=[
                RecoveryRunRead.model_validate(run)
                for run in runs
            ],
        )

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Recovery history unavailable",
        ) from None

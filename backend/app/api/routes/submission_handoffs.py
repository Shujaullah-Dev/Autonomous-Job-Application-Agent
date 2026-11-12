
"""Manual submission preflight and handoff API."""

import uuid
from dataclasses import asdict
from typing import Annotated

from app.api.routes.jobs import require_dev_write_key
from app.db.session import get_db
from app.models.submission_handoff import SubmissionHandoff
from app.schemas.submission_handoff import (
    ManualHandoffRequest,
    ManualHandoffResponse,
    SubmissionPreflightResponse,
)
from app.services.application_tracking import (
    ApplicationNotFound,
    get_application,
)
from app.services.submission_handoff_service import (
    HandoffConflict,
    HandoffNotFound,
    get_latest_handoff,
    prepare_manual_handoff,
)
from app.services.submission_preflight import (
    evaluate_submission_preflight,
)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/v1/candidates",
    tags=["Submission Handoffs"],
    dependencies=[Depends(require_dev_write_key)],
)


def handoff_response(
    handoff: SubmissionHandoff,
    *,
    newly_created: bool,
) -> ManualHandoffResponse:
    return ManualHandoffResponse(
        handoff_id=handoff.id,
        application_id=handoff.application_id,
        revision_number=handoff.revision_number,
        status="prepared",
        provider_hint=handoff.provider_hint,
        destination_url=handoff.destination_url,
        created_at=handoff.created_at,
        newly_created=newly_created,
        message=(
            "Manual application handoff prepared only. "
            "No external page was opened and no application "
            "was submitted by this API."
        ),
    )


@router.get(
    "/{candidate_id}/applications/{application_id}"
    "/submission-preflight",
    response_model=SubmissionPreflightResponse,
)
def check_submission_preflight(
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> SubmissionPreflightResponse:
    try:
        application = get_application(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
        )

        report = evaluate_submission_preflight(
            db,
            application,
        )

        return SubmissionPreflightResponse.model_validate(
            asdict(report)
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


@router.post(
    "/{candidate_id}/applications/{application_id}"
    "/manual-handoff",
    response_model=ManualHandoffResponse,
)
def create_manual_handoff(
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    payload: ManualHandoffRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ManualHandoffResponse:
    try:
        handoff, created = prepare_manual_handoff(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            expected_revision=payload.expected_revision,
        )

        return handoff_response(
            handoff,
            newly_created=created,
        )

    except ApplicationNotFound:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        ) from None

    except HandoffConflict as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from None

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Concurrent handoff request conflicted",
        ) from None

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Could not prepare manual handoff",
        ) from None


@router.get(
    "/{candidate_id}/applications/{application_id}"
    "/manual-handoff",
    response_model=ManualHandoffResponse,
)
def read_manual_handoff(
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ManualHandoffResponse:
    try:
        handoff = get_latest_handoff(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
        )

        return handoff_response(
            handoff,
            newly_created=False,
        )

    except (ApplicationNotFound, HandoffNotFound):
        raise HTTPException(
            status_code=404,
            detail="Manual handoff not found",
        ) from None

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from None
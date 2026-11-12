
"""Persistent application tracking API."""

import uuid
from typing import Annotated

from app.api.routes import job_workflows
from app.api.routes.jobs import require_dev_write_key
from app.db.session import get_db
from app.models.application import Application
from app.schemas.application_tracking import (
    ApplicationDetailResponse,
    ApplicationListResponse,
    ApplicationSummary,
    DraftEditRequest,
    DraftRevisionRead,
    StatusEventRead,
    StatusUpdateRequest,
)
from app.services.application_draft_context import (
    DraftCandidateNotFound,
    DraftJobChanged,
    DraftJobUnavailable,
    load_application_facts,
)
from app.services.application_materials import (
    generate_application_draft,
)
from app.services.application_tracking import (
    ApplicationConflict,
    ApplicationNotFound,
    change_application_status,
    create_tracked_application,
    get_application_details,
    save_draft_revision,
)
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/v1/candidates",
    tags=["Application Tracking"],
    dependencies=[Depends(require_dev_write_key)],
)


def read_detail(
    db: Session,
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
) -> ApplicationDetailResponse:
    try:
        application, revisions, events = (
            get_application_details(
                db,
                candidate_id=candidate_id,
                application_id=application_id,
            )
        )

    except ApplicationNotFound:
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        ) from None

    if not revisions:
        raise HTTPException(
            status_code=409,
            detail="Application has no saved draft revision",
        )

    summary = ApplicationSummary.model_validate(
        application
    )

    return ApplicationDetailResponse(
        **summary.model_dump(),
        latest_draft=DraftRevisionRead.model_validate(
            revisions[-1]
        ),
        revisions=[
            DraftRevisionRead.model_validate(item)
            for item in revisions
        ],
        history=[
            StatusEventRead.model_validate(item)
            for item in events
        ],
        message=(
            "Application tracking only. No application "
            "was submitted by this API."
        ),
    )


@router.post(
    "/{candidate_id}/workflows/{workflow_id}"
    "/tracked-applications/{job_id}",
    response_model=ApplicationDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def track_approved_application(
    candidate_id: uuid.UUID,
    workflow_id: uuid.UUID,
    job_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db)],
) -> ApplicationDetailResponse:
    """Generate and persist a deterministic draft."""

    current = job_workflows.workflow_response(
        candidate_id,
        workflow_id,
    )

    if current.status != "approved":
        raise HTTPException(
            status_code=409,
            detail="Workflow shortlist is not approved",
        )

    if job_id not in current.approved_job_ids:
        raise HTTPException(
            status_code=409,
            detail="Job was not approved in this workflow",
        )

    reviewed = next(
        (
            job
            for job in current.shortlist
            if job.job_id == job_id
        ),
        None,
    )

    if reviewed is None:
        raise HTTPException(
            status_code=409,
            detail="Approved shortlist entry is missing",
        )

    try:
        facts = load_application_facts(
            db,
            candidate_id=candidate_id,
            job_id=job_id,
            approved_title=reviewed.title,
            shortlist_score=reviewed.score,
        )

        # Initial tracked draft is deterministic.
        # No Groq call or unverified generated claim.
        draft = generate_application_draft(
            facts,
            use_ai=False,
        )

        snapshot = {
            "candidate_name": facts.candidate_name,
            "candidate_email": facts.candidate_email,
            "relevant_skills": list(draft.resume_skills),
            "experiences": list(
                draft.resume_experiences
            ),
            "educations": list(
                draft.resume_educations
            ),
        }

        application = create_tracked_application(
            db,
            candidate_id=candidate_id,
            workflow_id=workflow_id,
            job_id=job_id,
            job_title=facts.job_title,
            company_name=facts.company_name,
            job_url=facts.job_url,
            cover_letter=draft.cover_letter,
            resume_snapshot=snapshot,
        )

        return read_detail(
            db,
            candidate_id,
            application.id,
        )

    except DraftCandidateNotFound:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        ) from None

    except (DraftJobUnavailable, DraftJobChanged):
        raise HTTPException(
            status_code=409,
            detail=(
                "Job is unavailable or changed since "
                "the shortlist was approved"
            ),
        ) from None

    except ApplicationConflict as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from None

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Application already exists or conflicts",
        ) from None

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Could not persist application",
        ) from None


@router.get(
    "/{candidate_id}/applications",
    response_model=ApplicationListResponse,
)
def list_candidate_applications(
    candidate_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[
        int, Query(ge=1, le=100)
    ] = 20,
    offset: Annotated[
        int, Query(ge=0)
    ] = 0,
) -> ApplicationListResponse:
    try:
        where_clause = (
            Application.candidate_id == candidate_id
        )

        total = db.scalar(
            select(func.count(Application.id))
            .where(where_clause)
        ) or 0

        rows = db.scalars(
            select(Application)
            .where(where_clause)
            .order_by(
                Application.created_at.desc(),
                Application.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from None

    return ApplicationListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            ApplicationSummary.model_validate(item)
            for item in rows
        ],
    )


@router.get(
    "/{candidate_id}/applications/{application_id}",
    response_model=ApplicationDetailResponse,
)
def get_tracked_application(
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ApplicationDetailResponse:
    try:
        return read_detail(
            db,
            candidate_id,
            application_id,
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from None


@router.patch(
    "/{candidate_id}/applications/{application_id}/draft",
    response_model=ApplicationDetailResponse,
)
def edit_application_draft(
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    payload: DraftEditRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ApplicationDetailResponse:
    try:
        save_draft_revision(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            expected_revision=payload.expected_revision,
            cover_letter=payload.cover_letter,
        )

        return read_detail(
            db,
            candidate_id,
            application_id,
        )

    except ApplicationNotFound:
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        ) from None

    except ApplicationConflict as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from None

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Draft revision conflict",
        ) from None

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Could not save draft revision",
        ) from None


@router.post(
    "/{candidate_id}/applications/{application_id}/status",
    response_model=ApplicationDetailResponse,
)
def update_application_status(
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    payload: StatusUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ApplicationDetailResponse:
    try:
        change_application_status(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            new_status=payload.new_status,
            confirm_reviewed=payload.confirm_reviewed,
            confirm_external_submission=(
                payload.confirm_external_submission
            ),
            note=payload.note,
        )

        return read_detail(
            db,
            candidate_id,
            application_id,
        )

    except ApplicationNotFound:
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        ) from None

    except ApplicationConflict as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from None

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Application status conflict",
        ) from None

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Could not update application status",
        ) from None

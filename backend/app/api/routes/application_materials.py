
"""Generate reviewable materials for approved jobs."""

import logging
import uuid
from typing import Annotated

from app.api.routes import job_workflows
from app.api.routes.jobs import require_dev_write_key
from app.core.config import settings
from app.db.session import get_db
from app.schemas.application_material import (
    ApplicationDraftRequest,
    ApplicationDraftResponse,
    TailoredResumePreview,
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
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
)
from langchain_groq import ChatGroq
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/candidates",
    tags=["Application Materials"],
    dependencies=[Depends(require_dev_write_key)],
)


@router.post(
    "/{candidate_id}/workflows/{workflow_id}"
    "/application-drafts/{job_id}",
    response_model=ApplicationDraftResponse,
)
def create_application_draft(
    candidate_id: uuid.UUID,
    workflow_id: uuid.UUID,
    job_id: Annotated[int, Path(ge=1)],
    payload: ApplicationDraftRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ApplicationDraftResponse:
    """
    Generate a draft for a Day 15 approved job.

    No applications are submitted and no DB rows are written.
    """

    current = job_workflows.workflow_response(
        candidate_id,
        workflow_id,
    )

    # Day 15 approval means selected for preparation only.
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

    reviewed_job = next(
        (
            item
            for item in current.shortlist
            if item.job_id == job_id
        ),
        None,
    )

    if reviewed_job is None:
        raise HTTPException(
            status_code=409,
            detail="Approved shortlist record is missing",
        )

    try:
        facts = load_application_facts(
            db,
            candidate_id=candidate_id,
            job_id=job_id,
            approved_title=reviewed_job.title,
            shortlist_score=reviewed_job.score,
        )

    except DraftCandidateNotFound:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        ) from None

    except DraftJobUnavailable:
        raise HTTPException(
            status_code=409,
            detail=(
                "Job is inactive, unavailable, or excluded "
                "from the current recommendation pool"
            ),
        ) from None

    except DraftJobChanged:
        raise HTTPException(
            status_code=409,
            detail=(
                "Job title changed after shortlist approval; "
                "start a new review workflow"
            ),
        ) from None

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from None

    model = None

    if (
        payload.use_ai
        and settings.application_drafts_ai_enabled
        and settings.groq_api_key
    ):
        try:
            model = ChatGroq(
                model=settings.groq_model,
                api_key=settings.groq_api_key,
                temperature=0,
                timeout=settings.groq_timeout_seconds,
                max_retries=0,
                max_tokens=256,
            )

        except Exception as exc:
            logger.warning(
                "Draft model initialization failed: %s",
                type(exc).__name__,
            )

    result = generate_application_draft(
        facts,
        use_ai=payload.use_ai,
        model=model,
    )

    return ApplicationDraftResponse(
        candidate_id=candidate_id,
        workflow_id=workflow_id,
        job_id=facts.job_id,
        job_title=facts.job_title,
        company_name=facts.company_name,
        job_url=facts.job_url,
        generation_mode=result.generation_mode,
        llm_used=result.llm_used,
        model_name=(
            settings.groq_model
            if result.llm_used
            else None
        ),
        cover_letter=result.cover_letter,
        tailored_resume=TailoredResumePreview(
            candidate_name=facts.candidate_name,
            candidate_email=facts.candidate_email,
            relevant_skills=list(result.resume_skills),
            experiences=list(result.resume_experiences),
            educations=list(result.resume_educations),
        ),
        evidence_used=list(result.evidence_used),
        warnings=list(result.warnings),
        message=(
            "Application draft generated for review. "
            "No application has been submitted or saved."
        ),
    )
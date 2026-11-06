
"""Day 11: Candidate-specific job matching API."""

import uuid
from typing import Annotated

from app.api.routes.jobs import require_dev_write_key
from app.db.session import get_db
from app.schemas.job_match import (
    JobMatchItem,
    JobMatchResponse,
)
from app.services.job_matching import (
    MatchPreferences,
    match_job,
)
from app.services.matching_queries import (
    load_active_jobs,
    load_candidate,
)
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/v1/candidates",
    tags=["Job Matching"],
    dependencies=[Depends(require_dev_write_key)],
)


@router.get(
    "/{candidate_id}/matches",
    response_model=JobMatchResponse,
)
def match_candidate_jobs(
    candidate_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    preferred_work_mode: Annotated[
        str | None,
        Query(pattern=r"^(remote|hybrid|onsite)$"),
    ] = None,
    preferred_location: Annotated[
        str | None,
        Query(max_length=150),
    ] = None,
    minimum_salary: Annotated[
        int | None,
        Query(ge=0),
    ] = None,
    salary_currency: Annotated[
        str | None,
        Query(pattern=r"^[A-Za-z]{3}$"),
    ] = None,
    min_score: Annotated[
        float,
        Query(ge=0, le=100),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 20,
) -> JobMatchResponse:

    if minimum_salary is not None and not salary_currency:
        raise HTTPException(
            status_code=422,
            detail=(
                "salary_currency is required "
                "with minimum_salary"
            ),
        )

    candidate = load_candidate(
        db,
        candidate_id,
    )

    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        )

    preferences = MatchPreferences(
        preferred_work_mode=preferred_work_mode,
        preferred_location=preferred_location,
        minimum_salary=minimum_salary,
        salary_currency=salary_currency,
    )

    jobs = load_active_jobs(db)

    results: list[JobMatchItem] = []

    for job, job_input in jobs:
        match = match_job(
            candidate,
            job_input,
            preferences,
        )

        if match.score < min_score:
            continue

        results.append(
            JobMatchItem(
                job_id=job.id,
                title=job.title,
                company_name=job.company_name,
                location=job.location,
                job_url=job.job_url,
                score=match.score,
                breakdown=match.breakdown,
                matched_skills=match.matched_skills,
                missing_skills=match.missing_skills,
                warnings=match.warnings,
            )
        )

    # Highest score first; ID resolves score ties.
    results.sort(
        key=lambda item: (
            -item.score,
            item.job_id,
        )
    )

    selected = results[:limit]

    return JobMatchResponse(
        candidate_id=str(candidate_id),
        evaluated_jobs=len(jobs),
        returned_jobs=len(selected),
        items=selected,
    )

"""Candidate-specific job matching API."""

import uuid
from typing import Annotated

from app.api.routes.jobs import require_dev_write_key
from app.db.session import get_db
from app.models.candidate import CandidateProfile
from app.schemas.job_match import (
    HybridMatchItem,
    HybridMatchResponse,
    JobMatchItem,
    JobMatchResponse,
)
from app.services.hybrid_matching import hybrid_score
from app.services.job_matching import (
    MatchPreferences,
    match_job,
)
from app.services.matching_queries import (
    load_active_jobs,
    load_candidate,
)
from app.services.semantic_embeddings import (
    MODEL_NAME,
    EmbeddingError,
    candidate_document,
    embed_texts,
)
from app.services.vector_store import nearest_job_similarities
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy.exc import SQLAlchemyError
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
    require_matching_profile(candidate)

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


@router.get(
    "/{candidate_id}/hybrid-matches",
    response_model=HybridMatchResponse,
)
def hybrid_candidate_matches(
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
) -> HybridMatchResponse:
    """Combine Day 11 matching with pgvector similarity."""

    if minimum_salary is not None and not salary_currency:
        raise HTTPException(
            status_code=422,
            detail=(
                "salary_currency is required "
                "with minimum_salary"
            ),
        )

    candidate = load_candidate(db, candidate_id)

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

    similarities: dict[int, float] = {}
    embedding_warning = None

    if jobs:
        profile = db.get(
            CandidateProfile,
            candidate_id,
        )

        text = candidate_document(
            candidate,
            summary=profile.professional_summary,
        )

        try:
            query_vector = embed_texts([text])[0]

        except EmbeddingError:
            embedding_warning = (
                "Local embedding model unavailable; "
                "using rule-based scores"
            )

        else:
            try:
                similarities = nearest_job_similarities(
                    db,
                    job_ids=[
                        job.id
                        for job, _ in jobs
                    ],
                    query_vector=query_vector,
                )

            except (SQLAlchemyError, RuntimeError):
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Vector search unavailable. "
                        "Verify the pgvector migration "
                        "and Supabase connection."
                    ),
                ) from None

    results: list[HybridMatchItem] = []

    for job, job_input in jobs:
        rule_match = match_job(
            candidate,
            job_input,
            preferences,
        )

        combined, semantic = hybrid_score(
            rule_match.score,
            similarities.get(job.id),
        )

        if combined < min_score:
            continue

        warnings = list(rule_match.warnings)

        if semantic is None:
            warnings.append(
                embedding_warning
                or (
                    "No current embedding for this job; "
                    "rule-based score used"
                )
            )

        results.append(
            HybridMatchItem(
                job_id=job.id,
                title=job.title,
                company_name=job.company_name,
                location=job.location,
                job_url=job.job_url,
                score=combined,
                breakdown=rule_match.breakdown,
                matched_skills=rule_match.matched_skills,
                missing_skills=rule_match.missing_skills,
                warnings=warnings,
                rule_score=rule_match.score,
                semantic_score=semantic,
                hybrid_score=combined,
            )
        )

    results.sort(
        key=lambda item: (
            -item.hybrid_score,
            item.job_id,
        )
    )

    selected = results[:limit]

    return HybridMatchResponse(
        candidate_id=str(candidate_id),
        model_name=MODEL_NAME,
        evaluated_jobs=len(jobs),
        embedded_jobs=len(similarities),
        returned_jobs=len(selected),
        items=selected,
    )


def require_matching_profile(candidate) -> None:
    """Avoid ranking from an empty structured career profile."""

    if not candidate.skills and not candidate.titles:
        raise HTTPException(
            status_code=409,
            detail=(
                "Candidate matching profile is incomplete. "
                "Review and import resume skills or "
                "work experience before requesting matches."
            ),
        )

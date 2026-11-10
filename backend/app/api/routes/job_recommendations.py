
"""Ranked candidate job recommendations."""

import uuid
from typing import Annotated, Literal

from app.api.routes.job_matches import require_matching_profile
from app.api.routes.jobs import require_dev_write_key
from app.db.session import get_db
from app.models.candidate import CandidateProfile
from app.schemas.job import WorkMode
from app.schemas.recommendation import (
    RecommendationItem,
    RecommendationResponse,
)
from app.services.job_matching import MatchPreferences
from app.services.matching_queries import (
    MAX_EVALUATED_JOBS,
    load_active_jobs,
    load_candidate,
)
from app.services.recommendation_engine import (
    filter_job_pool,
    rank_recommendations,
)
from app.services.semantic_embeddings import (
    MODEL_NAME,
    EmbeddingError,
    candidate_document,
    embed_texts,
)
from app.services.vector_store import nearest_job_similarities
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/v1/candidates",
    tags=["Job Recommendations"],
    dependencies=[Depends(require_dev_write_key)],
)


@router.get(
    "/{candidate_id}/recommendations",
    response_model=RecommendationResponse,
)
def get_candidate_recommendations(
    candidate_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    mode: Literal["rules", "hybrid"] = "hybrid",
    work_mode: WorkMode | None = None,
    preferred_work_mode: WorkMode | None = None,
    include_unknown_work_mode: bool = False,
    
    title_contains: Annotated[
        str | None,
        Query(max_length=100),
    ] = None,
    location_contains: Annotated[
        str | None,
        Query(max_length=150),
    ] = None,
    source: Annotated[
        str | None,
        Query(max_length=100),
    ] = None,
    preferred_location: Annotated[
        str | None,
        Query(max_length=150),
    ] = None,
    min_score: Annotated[
        float,
        Query(ge=0, le=100),
    ] = 50.0,
    limit: Annotated[
        int,
        Query(ge=1, le=50),
    ] = 20,
    offset: Annotated[
        int,
        Query(ge=0),
    ] = 0,
) -> RecommendationResponse:
    """
    Recommend jobs from the bounded active-job pool.

    Hard filters -> scoring -> relevance gate ->
    stable sort -> pagination.
    """

    if include_unknown_work_mode and work_mode is None:
        raise HTTPException(
            status_code=422,
            detail="include_unknown_work_mode requires a work_mode",
        )

    try:
        candidate = load_candidate(
            db,
            candidate_id,
        )

        if candidate is None:
            raise HTTPException(
                status_code=404,
                detail="Candidate not found",
            )

        # Already exists in the Day 12 code;
        # now we actually enforce the validation.
        require_matching_profile(candidate)

        profile = db.get(
            CandidateProfile,
            candidate_id,
        )

        all_jobs = load_active_jobs(db)

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from None

    jobs = filter_job_pool(
        all_jobs,
        work_mode=work_mode,
        include_unknown_work_mode=include_unknown_work_mode,
        title_contains=title_contains,
        location_contains=location_contains,
        source=source,
    )

    unknown_work_mode_jobs = sum(
        job.work_mode is None
        for job, _ in all_jobs
    )

    filtered_out_jobs = len(all_jobs) - len(jobs)

    preferences = MatchPreferences(
        preferred_work_mode=preferred_work_mode or work_mode,
        preferred_location=preferred_location,
    )

    similarities: dict[int, float] = {}
    embedding_warning: str | None = None

    if jobs and mode == "hybrid":
        document = candidate_document(
            candidate,
            summary=profile.professional_summary,
        )

        try:
            query_vector = embed_texts([document])[0]

        except EmbeddingError:
            embedding_warning = (
                "Local embedding model unavailable; "
                "rule-based fallback was used."
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

            except (SQLAlchemyError, RuntimeError, ValueError):
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Semantic vector search unavailable. "
                        "Verify Supabase and the embedding migration."
                    ),
                ) from None


    # Use one consistent scoring method across
    # the entire recommendation request.
    effective_mode = mode

    if mode == "hybrid":
        if not jobs:
            effective_mode = "rules"

        elif len(similarities) != len(jobs):
            effective_mode = "rules"

            if embedding_warning is None:
                embedding_warning = (
                    "Some jobs lack current embeddings. "
                    "All jobs were ranked using rules "
                    "to ensure comparable scores."
                )


    ranked = rank_recommendations(
        candidate,
        jobs,
        preferences=preferences,
        similarities=similarities,
        mode=effective_mode,
        min_score=min_score,
    )

    # Pagination happens AFTER all evaluated jobs are ranked.
    total_matches = len(ranked.items)
    page_items = ranked.items[
        offset : offset + limit
    ]

    actual_mode = effective_mode

    global_warnings = [
        (
            "Recommendation scores are heuristic ranking "
            "signals, not hiring probabilities."
        ),
        (
            "Hiring-country eligibility and work "
            "authorization have not been verified."
        ),
        (
            "Only the most recent "
            f"{MAX_EVALUATED_JOBS} matching-eligible jobs "
            "by database ID can be evaluated."
        ),
        (
            "Salary compatibility is not verified "
            "without comparable pay periods."
        ),
    ]


    if unknown_work_mode_jobs:
        global_warnings.append(
            f"{unknown_work_mode_jobs} evaluated jobs have "
            "unknown work mode; they cannot be considered "
            "confirmed remote jobs."
        )

    if work_mode and not include_unknown_work_mode:
        global_warnings.append(
            "The work_mode filter is strict: jobs with "
            "unknown work mode were excluded."
        )

    if work_mode and include_unknown_work_mode:
        included_unknown = sum(
            job.work_mode is None
            for job, _ in jobs
        )

        if included_unknown:
            global_warnings.append(
                f"{included_unknown} jobs with unknown work "
                "mode were included for review; none is "
                f"confirmed {work_mode}."
            )

    if preferred_work_mode and not work_mode:
        global_warnings.append(
            "preferred_work_mode changes scoring but does "
            "not filter jobs or verify their work arrangement."
        )

    if min_score < 50:
        global_warnings.append(
            "Scores below 50 are shown for diagnostics; "
            "they are not validated application recommendations."
        )

    if location_contains:
        global_warnings.append(
            "Location filtering compares text only, "
            "not verified geographic eligibility."
        )

    if embedding_warning:
        global_warnings.append(embedding_warning)

    if mode == "hybrid" and jobs and not similarities:
        if not embedding_warning:
            global_warnings.append(
                "No current job embeddings were available; "
                "rule-based scores were used."
            )

    if actual_mode == "mixed":
        global_warnings.append(
            "Some jobs lacked current embeddings and "
            "used rule-based scoring only."
        )

    if not jobs:
        global_warnings.append(
            "No jobs matched the selected hard filters. "
            "Scoring was skipped."
        )
    elif total_matches == 0:
        global_warnings.append(
            "No jobs satisfied the selected score threshold "
            "and relevance-evidence requirements."
        )

    items = [
        RecommendationItem(
            job_id=result.job.id,
            title=result.job.title,
            company_name=result.job.company_name,
            job_url=result.job.job_url,
            location=result.job.location,
            source=result.job.source,
            work_mode=result.job.work_mode,
            posted_at=result.job.posted_at,
            score=result.score,
            rule_score=result.match.score,
            semantic_score=result.semantic_score,
            breakdown=result.match.breakdown,
            matched_skills=result.match.matched_skills,
            missing_skills=result.match.missing_skills,
            reasons=list(result.reasons),
            cautions=(
                list(result.cautions)
                + (
                    [
                        "Work mode is unknown; this job is not "
                        "confirmed remote, hybrid, or onsite."
                    ]
                    if result.job.work_mode is None
                    else []
                )
                + (
                    [
                        "Job location differs from candidate location; "
                        "verify geography and eligibility with employer."
                    ]
                    if result.match.breakdown.get("location") == 0
                    else []
                )
            ),

        )
        for result in page_items
    ]

    return RecommendationResponse(
        candidate_id=str(candidate_id),
        requested_mode=mode,
        ranking_mode=actual_mode,
        model_name=MODEL_NAME if effective_mode == "hybrid" else None,
        evaluated_jobs=len(all_jobs),
        filtered_jobs=len(jobs),
        unknown_work_mode_jobs=unknown_work_mode_jobs,
        filtered_out_jobs=filtered_out_jobs,
        semantic_jobs=len(similarities),
        total_matches=total_matches,
        returned_jobs=len(items),
        below_threshold=ranked.below_threshold,
        insufficient_evidence=ranked.insufficient_evidence,
        limit=limit,
        offset=offset,
        has_more=(offset + len(items) < total_matches),
        warnings=global_warnings,
        items=items,
    )
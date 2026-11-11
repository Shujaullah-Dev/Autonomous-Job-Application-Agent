
"""Load Supabase recommendations for the graph."""

import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.explanation_context import (
    CandidateNotFoundError,
    IncompleteCandidateProfileError,
)
from app.services.job_matching import MatchPreferences
from app.services.job_workflow_graph import WorkflowState
from app.services.matching_queries import (
    load_active_jobs,
    load_candidate,
)
from app.services.recommendation_engine import (
    filter_job_pool,
    rank_recommendations,
)


def load_workflow_recommendations(
    state: WorkflowState,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
) -> list[dict]:
    """
    Load and rank real jobs.

    No database writes.
    Rules mode avoids Groq and pgvector dependencies.
    """

    candidate_id = uuid.UUID(state["candidate_id"])
    options = state.get("options", {})

    with session_factory() as db:
        candidate = load_candidate(
            db,
            candidate_id,
        )

        if candidate is None:
            raise CandidateNotFoundError()

        if not candidate.skills and not candidate.titles:
            raise IncompleteCandidateProfileError()

        all_jobs = load_active_jobs(db)

        filtered = filter_job_pool(
            all_jobs,
            work_mode=options.get("work_mode"),
            include_unknown_work_mode=options.get(
                "include_unknown_work_mode",
                False,
            ),
        )

        preferences = MatchPreferences(
            preferred_work_mode=(
                options.get("preferred_work_mode")
                or options.get("work_mode")
            ),
            preferred_location=options.get(
                "preferred_location"
            ),
        )

        ranked = rank_recommendations(
            candidate,
            filtered,
            preferences=preferences,
            mode="rules",
            min_score=options.get("min_score", 50.0),
        )

        limit = options.get("limit", 5)

        results: list[dict] = []

        for result in ranked.items[:limit]:
            cautions = list(result.cautions)

            if result.job.work_mode is None:
                cautions.append(
                    "Work mode is unknown; this is not "
                    "a confirmed remote job."
                )

            if result.score < 50:
                cautions.append(
                    "Low score: included only because "
                    "a diagnostic threshold was selected."
                )

            results.append(
                {
                    "job_id": result.job.id,
                    "title": result.job.title,
                    "score": result.score,
                    "work_mode": result.job.work_mode,
                    "reasons": list(result.reasons),
                    "cautions": list(
                        dict.fromkeys(cautions)
                    ),
                }
            )

        return results

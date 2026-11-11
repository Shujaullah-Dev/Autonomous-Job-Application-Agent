
"""Load existing, verified recommendation evidence for Day 14."""

import uuid

from sqlalchemy.orm import Session

from app.services.job_matching import MatchPreferences
from app.services.langchain_explanations import EvidenceContext
from app.services.matching_queries import (
    load_active_jobs,
    load_candidate,
)
from app.services.recommendation_engine import (
    rank_recommendations,
)


class CandidateNotFoundError(Exception):
    pass


class IncompleteCandidateProfileError(Exception):
    pass


class RecommendationNotFoundError(Exception):
    pass


def load_explanation_context(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    job_id: int,
) -> EvidenceContext:
    """Load a candidate-specific, rule-based explanation."""

    candidate = load_candidate(db, candidate_id)

    if candidate is None:
        raise CandidateNotFoundError()

    if not candidate.skills and not candidate.titles:
        raise IncompleteCandidateProfileError()

    # Reuses Day 13's active, non-demo, bounded job pool.
    job_pairs = load_active_jobs(db)

    selected = next(
        (
            pair
            for pair in job_pairs
            if pair[0].id == job_id
        ),
        None,
    )

    if selected is None:
        raise RecommendationNotFoundError()

    ranked = rank_recommendations(
        candidate,
        [selected],
        preferences=MatchPreferences(),
        mode="rules",
        min_score=0,
    )

    # Unrelated jobs fail the existing evidence gate.
    if not ranked.items:
        raise RecommendationNotFoundError()

    result = ranked.items[0]
    cautions = list(result.cautions)

    if result.score < 50:
        cautions.append(
            "The score is below the default recommendation "
            "threshold of 50. Review for diagnostic purposes."
        )

    if selected[0].work_mode is None:
        cautions.append(
            "The job's work mode is unknown; remote, hybrid "
            "and onsite eligibility are not confirmed."
        )

    return EvidenceContext(
        job_id=result.job.id,
        job_title=result.job.title,
        score=result.score,
        reasons=result.reasons,
        cautions=tuple(dict.fromkeys(cautions)),
    )
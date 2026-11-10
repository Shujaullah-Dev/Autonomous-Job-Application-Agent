
"""Explainable, evidence-gated job recommendations."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from app.models.job import Job
from app.services.hybrid_matching import hybrid_score
from app.services.job_matching import (
    CandidateInput,
    JobInput,
    MatchPreferences,
    MatchResult,
    match_job,
)

RankingMode = Literal["rules", "hybrid"]
JobPair = tuple[Job, JobInput]


@dataclass(frozen=True)
class RankedRecommendation:
    job: Job
    match: MatchResult
    score: float
    semantic_score: float | None
    reasons: tuple[str, ...]
    cautions: tuple[str, ...]


@dataclass(frozen=True)
class RankingOutcome:
    items: tuple[RankedRecommendation, ...]
    below_threshold: int
    insufficient_evidence: int



def filter_job_pool(
    jobs: Sequence[JobPair],
    *,
    work_mode: str | None = None,
    include_unknown_work_mode: bool = False,
    title_contains: str | None = None,
    location_contains: str | None = None,
    source: str | None = None,
) -> list[JobPair]:
    """
    Apply explicit job filters before ranking.

    If work_mode is provided:
    - Exact work-mode matches are included.
    - Jobs with unknown work mode are excluded
      unless include_unknown_work_mode=True.
    - Known different work modes are excluded.

    Unknown work mode never means confirmed remote.
    """

    title_text = (title_contains or "").strip().casefold()
    location_text = (
        (location_contains or "").strip().casefold()
    )

    selected: list[JobPair] = []

    for job, data in jobs:

        # Work-mode filtering
        if work_mode is not None:
            matches_requested_mode = (
                job.work_mode == work_mode
            )

            is_permitted_unknown = (
                include_unknown_work_mode
                and job.work_mode is None
            )

            if not (
                matches_requested_mode
                or is_permitted_unknown
            ):
                continue

        # Job source filtering
        if source and job.source != source:
            continue

        # Job title filtering
        if (
            title_text
            and title_text not in job.title.casefold()
        ):
            continue

        # Location-text filtering
        if (
            location_text
            and location_text
            not in (job.location or "").casefold()
        ):
            continue

        selected.append((job, data))

    return selected



def has_relevance_evidence(match: MatchResult) -> bool:
    """
    Day 13 technical-role evidence gate.

    A recognized matched skill OR a strong title match
    is necessary for recommendation eligibility.
    """

    return (
        bool(match.matched_skills)
        or match.breakdown.get("title", 0.0) >= 70.0
    )


def explanation_for(
    job: Job,
    match: MatchResult,
    semantic_score: float | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Explain positive evidence and remaining uncertainties."""

    reasons: list[str] = []

    if match.matched_skills:
        skills = ", ".join(match.matched_skills[:5])
        reasons.append(
            "The job mentions skills found in the candidate "
            f"profile: {skills}."
        )

    if match.breakdown.get("title", 0.0) >= 70:
        reasons.append(
            "The job title has strong alignment with "
            "previous roles or verified skills."
        )

    if (
        match.breakdown.get("experience", 0.0) == 100.0
        and not any(
            "Experience comparison has insufficient data" in warning
            for warning in match.warnings
        )
    ):
        reasons.append(
            "The recorded experience satisfies an extracted "
            "years-of-experience requirement."
        )

    if semantic_score is not None and semantic_score >= 50:
        reasons.append(
            "The candidate and job texts have a positive "
            "semantic similarity signal."
        )

    cautions = list(match.warnings)

    if match.missing_skills:
        cautions.append(
            "Job mentions technologies not found in the "
            "candidate profile: "
            + ", ".join(match.missing_skills[:8])
            + ". These are not necessarily mandatory."
        )

    cautions.append(
        "Hiring-country, visa and work-authorization "
        "eligibility have not been independently verified."
    )

    # Remove duplicate warnings while preserving their order.
    unique_cautions = list(dict.fromkeys(cautions))

    return tuple(reasons), tuple(unique_cautions)


def rank_recommendations(
    candidate: CandidateInput,
    jobs: Sequence[JobPair],
    *,
    preferences: MatchPreferences,
    similarities: Mapping[int, float] | None = None,
    mode: RankingMode = "hybrid",
    min_score: float = 50.0,
) -> RankingOutcome:
    """Score all supplied jobs, gate relevance, and sort."""

    if mode not in {"rules", "hybrid"}:
        raise ValueError("Unsupported ranking mode")

    if not 0 <= min_score <= 100:
        raise ValueError("min_score must be between 0 and 100")

    similarities = similarities or {}

    ranked: list[RankedRecommendation] = []
    below_threshold = 0
    insufficient_evidence = 0

    for job, job_input in jobs:
        rule_match = match_job(
            candidate,
            job_input,
            preferences,
        )

        if mode == "hybrid":
            score, semantic_score = hybrid_score(
                rule_match.score,
                similarities.get(job.id),
            )
        else:
            score = rule_match.score
            semantic_score = None

        if score < min_score:
            below_threshold += 1
            continue

        if not has_relevance_evidence(rule_match):
            insufficient_evidence += 1
            continue

        reasons, cautions = explanation_for(
            job,
            rule_match,
            semantic_score,
        )

        ranked.append(
            RankedRecommendation(
                job=job,
                match=rule_match,
                score=score,
                semantic_score=semantic_score,
                reasons=reasons,
                cautions=cautions,
            )
        )

    # Deterministic ranking, including tied scores.
    ranked.sort(
        key=lambda item: (
            -item.score,
            item.job.id,
        )
    )

    return RankingOutcome(
        items=tuple(ranked),
        below_threshold=below_threshold,
        insufficient_evidence=insufficient_evidence,
    )

"""Offline ranking quality metrics for Day 13."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class RankingMetrics:
    k: int
    precision_at_k: float
    recall_at_k: float
    reciprocal_rank_at_k: float
    relevant_in_top_k: int
    labeled_relevant: int


def evaluate_ranking(
    ranked_job_ids: Sequence[int],
    relevant_job_ids: Collection[int],
    *,
    k: int = 5,
) -> RankingMetrics:
    """
    Evaluate a ranked list using human-provided relevance labels.

    Precision@K: proportion of K positions containing
    relevant jobs.

    Recall@K: proportion of all labeled relevant jobs
    retrieved in the first K positions.

    Reciprocal rank: 1 / position of first relevant job.
    """

    if k < 1:
        raise ValueError("k must be >= 1")

    if len(set(ranked_job_ids)) != len(ranked_job_ids):
        raise ValueError("Ranking contains duplicate job IDs")

    relevant = set(relevant_job_ids)
    top = list(ranked_job_ids[:k])

    hits = [
        job_id
        for job_id in top
        if job_id in relevant
    ]

    reciprocal_rank = 0.0

    for position, job_id in enumerate(top, start=1):
        if job_id in relevant:
            reciprocal_rank = 1.0 / position
            break

    return RankingMetrics(
        k=k,
        precision_at_k=round(len(hits) / k, 4),
        recall_at_k=round(
            len(hits) / len(relevant),
            4,
        ) if relevant else 0.0,
        reciprocal_rank_at_k=round(
            reciprocal_rank,
            4,
        ),
        relevant_in_top_k=len(hits),
        labeled_relevant=len(relevant),
    )
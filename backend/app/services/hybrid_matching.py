
"""Combine Day 11 rule-based scores with semantic similarity."""


def hybrid_score(
    rule_score: float,
    cosine_similarity: float | None,
) -> tuple[float, float | None]:
    """
    Return (hybrid_score, semantic_score).

    When a semantic embedding is unavailable, preserve
    the existing rule-based score instead of penalizing
    the candidate for missing embedding data.
    """

    if cosine_similarity is None:
        return round(rule_score, 2), None

    semantic_score = round(
        max(
            0.0,
            min(
                100.0,
                cosine_similarity * 100,
            ),
        ),
        2,
    )

    combined = round(
        0.70 * rule_score
        + 0.30 * semantic_score,
        2,
    )

    return combined, semantic_score

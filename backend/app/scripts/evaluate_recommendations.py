
"""Evaluate labeled recommendation results without a database."""

import argparse
import json
from pathlib import Path

from app.services.recommendation_metrics import evaluate_ranking


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate recommendation ranking quality",
    )

    parser.add_argument(
        "--labels",
        type=Path,
        required=True,
        help="JSON file with ranked and relevant job IDs",
    )

    parser.add_argument(
        "--k",
        type=int,
        default=5,
    )

    args = parser.parse_args()

    try:
        data = json.loads(
            args.labels.read_text(encoding="utf-8")
        )

        ranked = data["ranked_job_ids"]
        relevant = data["relevant_job_ids"]

        if (
            not isinstance(ranked, list)
            or not isinstance(relevant, list)
            or any(
                type(item) is not int
                for item in ranked + relevant
            )
        ):
            raise ValueError(
                "Both ID fields must be integer lists"
            )

        result = evaluate_ranking(
            ranked,
            relevant,
            k=args.k,
        )

    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))

    print(
        json.dumps(
            {
                "k": result.k,
                "precision_at_k": result.precision_at_k,
                "recall_at_k": result.recall_at_k,
                "reciprocal_rank_at_k": (
                    result.reciprocal_rank_at_k
                ),
                "relevant_in_top_k": (
                    result.relevant_in_top_k
                ),
                "labeled_relevant": result.labeled_relevant,
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
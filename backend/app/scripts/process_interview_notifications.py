"""Release due interview notifications into the in-app inbox."""

import argparse
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.services.interview_scheduling import publish_due_notifications

UTC = timezone.utc  # noqa: UP017


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process due in-app interview reminders once."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
    )
    args = parser.parse_args()

    if not 1 <= args.limit <= 500:
        parser.error("--limit must be between 1 and 500")

    with SessionLocal() as db:
        count = publish_due_notifications(
            db,
            now=datetime.now(UTC),
            limit=args.limit,
        )

    print(f"Made {count} interview reminder(s) available in-app.")


if __name__ == "__main__":
    main()
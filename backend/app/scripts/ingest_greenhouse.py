
"""CLI to fetch Greenhouse jobs and import them into Supabase."""

import argparse
import sys

import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.job_ingestion import (
    JobIngestionError,
    ingest_jobs,
)
from app.services.job_sources.greenhouse import (
    GreenhouseSource,
    JobSourceError,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import a public Greenhouse job board"
    )

    parser.add_argument(
        "--board",
        required=True,
        help="Greenhouse board token, not a URL",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Save changes; default is dry-run",
    )

    args = parser.parse_args(argv)

    try:
        # No arbitrary URL is accepted by the adapter.
        # Redirects are disabled.
        with httpx.Client(
            timeout=settings.job_source_timeout_seconds,
            follow_redirects=False,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "AIJobAgent/0.1 "
                    "(development job-board integration)"
                ),
            },
        ) as client:
            result = GreenhouseSource(client).fetch(
                args.board
            )

        with SessionLocal() as db:
            summary = ingest_jobs(
                db,
                result.jobs,
                apply=args.apply,
            )

    except (JobSourceError, JobIngestionError) as exc:
        print(
            f"Job import failed: {exc}",
            file=sys.stderr,
        )
        return 1

    mode = "APPLIED" if summary.applied else "DRY RUN"

    print(f"Mode: {mode}")
    print(f"Board: {result.board_token}")
    print(f"Company: {result.company_name}")
    print(f"Source records: {result.source_count}")
    print(f"Invalid/prospect records: {result.skipped_count}")
    print(f"Normalized jobs: {summary.fetched}")
    print(f"Would create / created: {summary.created}")
    print(f"Would update / updated: {summary.updated}")
    print(f"Unchanged: {summary.unchanged}")
    print(f"Source conflicts skipped: {summary.skipped}")

    if not summary.applied:
        print(
            "No data was saved. "
            "Use --apply to write to the database."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
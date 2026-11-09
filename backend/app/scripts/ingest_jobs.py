
"""Unified job importer for Greenhouse and Lever."""

import argparse
import sys

import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.job_ingestion import (
    JobIngestionError,
    ingest_jobs,
)
from app.services.job_sources import (
    GreenhouseSource,
    JobSourceError,
    LeverSource,
)


def main(argv: list[str] | None = None) -> int:

    parser = argparse.ArgumentParser(
        description="Import jobs from supported providers"
    )

    parser.add_argument(
        "--greenhouse-board",
        action="append",
        default=[],
        help="Greenhouse board token; may be repeated",
    )

    parser.add_argument(
        "--lever-site",
        action="append",
        default=[],
        help="Lever site identifier; may be repeated",
    )

    parser.add_argument(
        "--lever-company-name",
        action="append",
        default=[],
        help="Company name corresponding to each Lever site",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit changes; otherwise dry-run",
    )

    args = parser.parse_args(argv)

    
    if any(
        site.casefold() == "leverdemo"
        for site in args.lever_site
    ):
        parser.error(
            "The Lever Demo board contains demonstration "
            "listings and must not be imported into "
            "the live matching dataset."
        )


    if not args.greenhouse_board and not args.lever_site:
        parser.error(
            "Specify at least one job source"
        )

    if len(args.lever_site) != len(
        args.lever_company_name
    ):
        parser.error(
            "Each Lever site requires one company name"
        )

    all_jobs = []
    source_results = []

    try:

        with httpx.Client(
            timeout=settings.job_source_timeout_seconds,
            follow_redirects=False,
            headers={
                "Accept": "application/json",
                "User-Agent": "AIJobAgent/0.1",
            },
        ) as client:

            # Greenhouse boards
            greenhouse = GreenhouseSource(client)

            for board in args.greenhouse_board:

                result = greenhouse.fetch(board)

                source_results.append(result)
                all_jobs.extend(result.jobs)

            # Lever sites
            lever = LeverSource(client)

            for site, company in zip(
                args.lever_site,
                args.lever_company_name,
                strict=True,
            ):

                result = lever.fetch(
                    site,
                    company_name=company,
                )

                source_results.append(result)
                all_jobs.extend(result.jobs)

        with SessionLocal() as db:

            summary = ingest_jobs(
                db,
                all_jobs,
                apply=args.apply,
            )

    except (JobSourceError, JobIngestionError) as exc:

        print(
            f"Import failed: {exc}",
            file=sys.stderr,
        )

        return 1

    mode = (
        "APPLIED"
        if summary.applied
        else "DRY RUN"
    )

    print(f"\nMode: {mode}")

    print("\nProvider results:")

    for result in source_results:

        print(
            f"\nProvider: {result.provider}"
        )

        print(
            f"Account: {result.account_identifier}"
        )

        print(
            f"Company: {result.company_name}"
        )

        print(
            f"Received: {result.source_count}"
        )

        print(
            f"Skipped by adapter: {result.skipped_count}"
        )

        print(
            f"Normalized: {len(result.jobs)}"
        )

    print("\nCombined ingestion results:")

    print(f"Fetched: {summary.fetched}")
    print(f"Created: {summary.created}")
    print(f"Updated: {summary.updated}")
    print(f"Unchanged: {summary.unchanged}")
    print(f"Skipped: {summary.skipped}")

    print(
        "Possible duplicates:",
        summary.possible_duplicates,
    )

    if not summary.applied:

        print(
            "\nDry-run completed. "
            "No changes were committed."
        )

        print(
            "Use --apply to save the changes."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
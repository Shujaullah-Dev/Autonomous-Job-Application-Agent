"""Unified job importer for every supported provider.

Examples:

    python -m app.scripts.ingest_jobs --defaults
    python -m app.scripts.ingest_jobs --defaults --apply
    python -m app.scripts.ingest_jobs --ashby-board "openai:OpenAI" --apply
    python -m app.scripts.ingest_jobs --feed remotive --feed arbeitnow

Each source is imported independently, so one unreachable board does not
discard the listings already collected from the others.
"""

import argparse

import httpx

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.job_ingestion import (
    JobIngestionError,
    SeenListings,
    deactivate_missing_jobs,
    ingest_jobs,
)
from app.services.job_sources import (
    AGGREGATOR_PROVIDERS,
    SOURCES,
    JobSourceError,
    SourceSpec,
    build_source,
    default_sources,
)

# Keep one run bounded: every source is newest-first, so the first records
# are the most useful ones.
DEFAULT_MAX_PER_SOURCE = 120


def parse_account(value: str) -> tuple[str, str | None]:
    """Read `identifier` or `identifier:Company Name` from one flag."""

    identifier, _, company = value.partition(":")

    return identifier.strip(), (company.strip() or None)


def collect_specs(args: argparse.Namespace) -> list[SourceSpec]:
    """Turn the command line into concrete sources to import."""

    specs: list[SourceSpec] = []

    if args.defaults:
        specs.extend(default_sources())

    for board in args.greenhouse_board:
        specs.append(SourceSpec("greenhouse", board.strip()))

    if len(args.lever_site) != len(args.lever_company_name):
        raise ValueError(
            "Each Lever site requires one company name"
        )

    for site, company in zip(
        args.lever_site,
        args.lever_company_name,
        strict=True,
    ):
        specs.append(
            SourceSpec("lever", site.strip(), company.strip())
        )

    for value in args.ashby_board:
        site, company = parse_account(value)
        specs.append(SourceSpec("ashby", site, company))

    for value in args.workable_site:
        site, company = parse_account(value)
        specs.append(SourceSpec("workable", site, company))

    for value in args.smartrecruiters_company:
        company_id, company = parse_account(value)
        specs.append(
            SourceSpec("smartrecruiters", company_id, company)
        )

    for provider in args.feed:
        specs.append(SourceSpec(provider, "latest"))

    # Keep the requested order but never import a source twice.
    unique: list[SourceSpec] = []
    seen: set[tuple[str, str]] = set()

    for spec in specs:
        key = (spec.provider, spec.identifier.casefold())

        if key in seen:
            continue

        seen.add(key)
        unique.append(spec)

    return unique


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import jobs from supported providers"
    )

    parser.add_argument(
        "--defaults",
        action="store_true",
        help=(
            "Import from the curated default set (Greenhouse, "
            "Lever, Ashby, Workable, SmartRecruiters and feeds)"
        ),
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
        "--ashby-board",
        action="append",
        default=[],
        help=(
            "Ashby board token, optionally as "
            "'token:Company Name'; may be repeated"
        ),
    )

    parser.add_argument(
        "--workable-site",
        action="append",
        default=[],
        help=(
            "Workable account subdomain, optionally as "
            "'site:Company Name'; may be repeated"
        ),
    )

    parser.add_argument(
        "--smartrecruiters-company",
        action="append",
        default=[],
        help=(
            "SmartRecruiters company identifier, optionally as "
            "'id:Company Name'; may be repeated"
        ),
    )

    parser.add_argument(
        "--feed",
        action="append",
        default=[],
        choices=list(AGGREGATOR_PROVIDERS),
        help="Public feed without company tokens; may be repeated",
    )

    parser.add_argument(
        "--max-per-source",
        type=int,
        default=DEFAULT_MAX_PER_SOURCE,
        help=(
            "Import at most this many listings per source "
            f"(default {DEFAULT_MAX_PER_SOURCE})"
        ),
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit changes; otherwise dry-run",
    )

    return parser


def main(argv: list[str] | None = None) -> int:

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.max_per_source < 1:
        parser.error("--max-per-source must be at least 1")

    try:
        specs = collect_specs(args)

    except ValueError as exc:
        parser.error(str(exc))

    if any(
        spec.provider == "lever"
        and spec.identifier.casefold() == "leverdemo"
        for spec in specs
    ):
        parser.error(
            "The Lever Demo board contains demonstration "
            "listings and must not be imported into "
            "the live matching dataset."
        )

    unknown = [
        spec.provider
        for spec in specs
        if spec.provider.casefold() not in SOURCES
    ]

    if unknown:
        parser.error(
            "Unsupported provider: "
            + ", ".join(sorted(set(unknown)))
        )

    if not specs:
        parser.error(
            "Specify at least one job source, for example --defaults"
        )

    totals = {
        "created": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped": 0,
        "duplicates": 0,
        "deactivated": 0,
    }

    seen = SeenListings()
    imported = 0
    failures: list[tuple[str, str]] = []
    mode = "APPLIED" if args.apply else "DRY RUN"

    print(f"Mode: {mode}")
    print(f"Sources: {len(specs)}\n")

    with httpx.Client(
        timeout=settings.job_source_timeout_seconds,
        follow_redirects=False,
        headers={
            "Accept": "application/json",
            "User-Agent": "AIJobAgent/0.1",
        },
    ) as client, SessionLocal() as db:

        for spec in specs:

            source = build_source(client, spec.provider)

            try:
                result = source.fetch(
                    spec.identifier,
                    company_name=spec.company_name,
                )

            except JobSourceError as exc:
                failures.append((spec.label, exc.reason))
                print(f"[failed]   {spec.label}: {exc.reason}")
                continue

            for item in result.jobs:
                seen.add(item)

            batch = result.jobs[: args.max_per_source]

            try:
                summary = ingest_jobs(
                    db,
                    batch,
                    apply=args.apply,
                )

            except (JobIngestionError, ValueError) as exc:
                db.rollback()

                reason = getattr(exc, "reason", None) or str(exc)
                failures.append((spec.label, reason))
                print(f"[failed]   {spec.label}: {reason}")
                continue

            imported += 1
            totals["created"] += summary.created
            totals["updated"] += summary.updated
            totals["unchanged"] += summary.unchanged
            totals["skipped"] += summary.skipped
            totals["duplicates"] += summary.possible_duplicates

            print(
                f"[ok]       {spec.label}: "
                f"received {result.source_count}, "
                f"normalized {len(result.jobs)}, "
                f"created {summary.created}, "
                f"updated {summary.updated}, "
                f"skipped {summary.skipped}"
            )

        if args.apply:
            closed = deactivate_missing_jobs(db, seen)
            totals["deactivated"] = closed
            print(
                f"[closed]   {closed} listings no provider "
                "returned any more"
            )

    print("\nCombined ingestion results:")
    print(
        "Created:",
        totals["created"],
        "| Updated:",
        totals["updated"],
        "| Unchanged:",
        totals["unchanged"],
        "| Skipped:",
        totals["skipped"],
        "| Possible duplicates:",
        totals["duplicates"],
        "| Closed:",
        totals["deactivated"],
    )
    print(f"Sources imported: {imported}/{len(specs)}")

    if failures:
        print("\nSources that could not be imported:")

        for label, reason in failures:
            print(f"  - {label}: {reason}")

    if not args.apply:
        print("\nDry-run completed. No changes were committed.")
        print("Use --apply to save the changes.")

    return 1 if imported == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())

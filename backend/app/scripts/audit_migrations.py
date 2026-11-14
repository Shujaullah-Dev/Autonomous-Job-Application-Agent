
"""Run the non-destructive Alembic history audit."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.services.migration_audit import audit_migrations

ROOT = Path(__file__).resolve().parents[3]

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit Alembic migration history safely."
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 when findings are present.",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable report.",
    )

    args = parser.parse_args(argv)
    report = audit_migrations(ROOT)

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print("Migration heads:", ", ".join(report.heads))
        print("Revisions inspected:", report.revision_count)
        print("Findings:", len(report.findings))

        for finding in report.findings:
            print(
                f"[{finding.code}] "
                f"{finding.revision}: {finding.table}"
            )
            print(f"  {finding.message}")

        print(
            "Fresh-schema static audit:",
            "PASS" if report.fresh_schema_safe else "BLOCKED",
        )

    if args.strict and not report.fresh_schema_safe:
        return 1

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
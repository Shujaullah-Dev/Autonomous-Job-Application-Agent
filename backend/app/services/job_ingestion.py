
"""Import normalized external jobs into the database."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.job import Job
from app.schemas.job import JobCreate

# Fields that may change when a listing is refreshed.
SYNC_FIELDS = (
    "title",
    "company_name",
    "location",
    "description",
    "employment_type",
    "work_mode",
    "salary_min",
    "salary_max",
    "salary_currency",
    "posted_at",
)


class JobIngestionError(RuntimeError):
    pass


@dataclass(frozen=True)
class IngestionSummary:
    fetched: int
    created: int
    updated: int
    unchanged: int
    skipped: int
    applied: bool


def ingest_jobs(
    db: Session,
    jobs: Sequence[JobCreate],
    *,
    apply: bool = False,
) -> IngestionSummary:
    """
    Insert new jobs and update known jobs from the same source.

    Default: dry-run. No database writes are committed.
    """

    urls = [str(item.job_url) for item in jobs]

    if len(urls) != len(set(urls)):
        raise ValueError(
            "The input contains duplicate job URLs"
        )

    try:
        existing: dict[str, Job] = {}

        # Use chunks to avoid excessively large SQL queries.
        for start in range(0, len(urls), 200):
            chunk = urls[start : start + 200]

            found = db.scalars(
                select(Job).where(
                    Job.job_url.in_(chunk)
                )
            ).all()

            existing.update(
                {
                    item.job_url: item
                    for item in found
                }
            )

        created = 0
        updated = 0
        unchanged = 0
        skipped = 0

        for item in jobs:
            data = item.model_dump()
            data["job_url"] = str(item.job_url)

            old = existing.get(data["job_url"])

            # New job
            if old is None:
                created += 1

                if apply:
                    db.add(Job(**data))

                continue

            # Do not overwrite a listing belonging
            # to another provider or manual source.
            if old.source != data["source"]:
                skipped += 1
                continue

            # Detect changed source fields.
            changes = {
                field: data[field]
                for field in SYNC_FIELDS
                if getattr(old, field) != data[field]
            }

            # An existing listing can become active again
            # if the provider publishes it again.
            if not old.is_active:
                changes["is_active"] = True

            if changes:
                updated += 1

                if apply:
                    for field, value in changes.items():
                        setattr(old, field, value)

            else:
                unchanged += 1

        if apply:
            db.commit()

        return IngestionSummary(
            fetched=len(jobs),
            created=created,
            updated=updated,
            unchanged=unchanged,
            skipped=skipped,
            applied=apply,
        )

    except SQLAlchemyError as exc:
        db.rollback()
        raise JobIngestionError(
            "database_error"
        ) from exc
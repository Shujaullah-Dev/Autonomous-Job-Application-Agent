"""Multi-source job ingestion with duplicate protection."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.job import Job
from app.schemas.job import JobCreate
from app.services.job_deduplication import (
    canonicalize_url,
    find_existing_by_identity,
    find_possible_duplicate,
    job_fingerprint,
)

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


@dataclass
class SeenListings:
    """Every listing this run observed, across all providers.

    Used to close roles that have disappeared: a stored job counts as still
    live when any provider still returns it, even if the provider it was
    originally imported from has removed it.
    """

    ids: set[tuple[str | None, str]] = field(default_factory=set)
    urls: set[str] = field(default_factory=set)
    fingerprints: set[str] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)

    def add(self, item: JobCreate) -> None:
        self.sources.add(item.source or "")

        if item.source_job_id:
            self.ids.add((item.source, item.source_job_id))

        try:
            self.urls.add(canonicalize_url(str(item.job_url)))

        except ValueError:
            pass

        self.fingerprints.add(
            job_fingerprint(
                item.company_name,
                item.title,
                item.location,
            )
        )

    def contains(self, job: Job) -> bool:
        if job.source_job_id and (
            job.source,
            job.source_job_id,
        ) in self.ids:
            return True

        if job.canonical_url and job.canonical_url in self.urls:
            return True

        if job.job_url:
            try:
                if canonicalize_url(job.job_url) in self.urls:
                    return True

            except ValueError:
                pass

        return (
            job_fingerprint(
                job.company_name,
                job.title,
                job.location,
            )
            in self.fingerprints
        )


def deactivate_missing_jobs(
    db: Session,
    seen: SeenListings,
) -> int:
    """Close listings from touched providers that no provider returned.

    Only providers that answered in this run are considered, so a board that
    failed or came back empty never hides roles. A job that reappears is
    reactivated by the next import automatically.
    """

    sources = {source for source in seen.sources if source}

    if not sources:
        return 0

    rows = db.scalars(
        select(Job).where(
            Job.is_active.is_(True),
            Job.source.in_(sources),
        )
    ).all()

    closed = 0

    for job in rows:
        if seen.contains(job):
            continue

        job.is_active = False
        closed += 1

    if closed:
        db.commit()

    return closed


@dataclass(frozen=True)
class IngestionSummary:
    fetched: int
    created: int
    updated: int
    unchanged: int
    skipped: int
    possible_duplicates: int
    applied: bool


def ingest_jobs(
    db: Session,
    jobs: Sequence[JobCreate],
    *,
    apply: bool = False,
) -> IngestionSummary:
    """Import jobs from multiple providers."""

    created = 0
    updated = 0
    unchanged = 0
    skipped = 0
    possible_duplicates = 0

    batch_urls = set()
    batch_ids = set()
    batch_fingerprints = set()

    try:
        for item in jobs:

            url = str(item.job_url)
            canonical = canonicalize_url(url)

            # Same canonical URL inside this import.
            if canonical in batch_urls:
                raise ValueError("Duplicate job URL in import batch")

            batch_urls.add(canonical)

            # Same provider identity inside this import.
            if item.source_job_id:
                identity = (
                    item.source,
                    item.source_job_id,
                )

                if identity in batch_ids:
                    skipped += 1
                    continue

                batch_ids.add(identity)

            existing = find_existing_by_identity(
                db,
                item,
            )

            data = item.model_dump()
            data["job_url"] = url
            data["canonical_url"] = canonical

            if existing:

                # Another provider already owns the listing.
                if existing.source != item.source:
                    skipped += 1
                    continue

                changes = {
                    field: data[field]
                    for field in SYNC_FIELDS
                    if getattr(existing, field) != data[field]
                }

                if existing.source_job_id != item.source_job_id:
                    changes["source_job_id"] = item.source_job_id

                if existing.canonical_url != canonical:
                    changes["canonical_url"] = canonical

                if not existing.is_active:
                    changes["is_active"] = True

                if changes:
                    updated += 1

                    if apply:
                        for field, value in changes.items():
                            setattr(existing, field, value)
                else:
                    unchanged += 1

                continue

            # Check for likely cross-source duplicates.
            possible = find_possible_duplicate(
                db,
                item,
            )

            if possible:
                possible_duplicates += 1
                skipped += 1
                continue

            # Avoid duplicates in the same import batch.
            fingerprint = (
                item.company_name.casefold().strip(),
                item.title.casefold().strip(),
                (item.location or "").casefold().strip(),
            )

            if fingerprint in batch_fingerprints:
                possible_duplicates += 1
                skipped += 1
                continue

            batch_fingerprints.add(fingerprint)

            created += 1

            if apply:
                db.add(
                    Job(**data)
                )

        if apply:
            db.commit()

        return IngestionSummary(
            fetched=len(jobs),
            created=created,
            updated=updated,
            unchanged=unchanged,
            skipped=skipped,
            possible_duplicates=possible_duplicates,
            applied=apply,
        )

    except SQLAlchemyError as exc:
        db.rollback()

        raise JobIngestionError(
            "database_error"
        ) from exc

    except Exception:
        if apply:
            db.rollback()

        raise
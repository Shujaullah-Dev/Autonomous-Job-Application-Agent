
"""URL normalization and job duplicate detection."""

import hashlib
import re
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job
from app.schemas.job import JobCreate

TRACKING_PARAMETERS = {
    "gclid",
    "fbclid",
    "ref",
    "source",
}


def canonicalize_url(value: str) -> str:
    """Remove tracking parameters and normalize URLs."""

    parts = urlsplit(value)

    scheme = parts.scheme.lower()

    if scheme not in {"http", "https"}:
        raise ValueError("Unsupported URL scheme")

    hostname = (parts.hostname or "").lower()

    if not hostname:
        raise ValueError("Invalid URL hostname")

    if parts.username or parts.password:
        raise ValueError("Credentials in job URLs are not allowed")

    port = parts.port

    netloc = hostname

    if port and not (
        (scheme == "https" and port == 443)
        or (scheme == "http" and port == 80)
    ):
        netloc = f"{hostname}:{port}"

    query = []

    for key, value in parse_qsl(
        parts.query,
        keep_blank_values=True,
    ):
        if key.lower().startswith("utm_"):
            continue

        if key.lower() in TRACKING_PARAMETERS:
            continue

        query.append((key, value))

    query.sort()

    path = re.sub(
        r"/+$",
        "",
        parts.path,
    ) or "/"

    return urlunsplit(
        (
            scheme,
            netloc,
            path,
            urlencode(query),
            "",
        )
    )


def normalize_text(value: str | None) -> str:
    """Normalize text for comparison."""

    if not value:
        return ""

    return " ".join(value.casefold().split())


def job_fingerprint(
    company_name: str,
    title: str,
    location: str | None,
) -> str:
    """Generate a deterministic similarity fingerprint."""

    normalized = "|".join(
        [
            normalize_text(company_name),
            normalize_text(title),
            normalize_text(location),
        ]
    )

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


def find_possible_duplicate(
    db: Session,
    job: JobCreate,
) -> Job | None:
    """
    Find a likely same-company, same-title,
    same-location listing.

    This is a review candidate, not proof of identity.
    """

    candidates = db.scalars(
        select(Job).where(
            Job.is_active.is_(True),
            Job.company_name.ilike(job.company_name),
            Job.title.ilike(job.title),
        ).limit(100)
    ).all()

    fingerprint = job_fingerprint(
        job.company_name,
        job.title,
        job.location,
    )

    for candidate in candidates:
        existing_fingerprint = job_fingerprint(
            candidate.company_name,
            candidate.title,
            candidate.location,
        )

        if existing_fingerprint == fingerprint:
            return candidate

    return None


def find_existing_by_identity(
    db: Session,
    job: JobCreate,
) -> Job | None:
    """Find a listing by provider ID or canonical URL."""

    source_id = job.source_job_id

    if source_id:
        existing = db.scalar(
            select(Job).where(
                Job.source == job.source,
                Job.source_job_id == source_id,
            )
        )

        if existing:
            return existing

    canonical = canonicalize_url(str(job.job_url))

    existing = db.scalar(
        select(Job).where(
            Job.canonical_url == canonical
        )
    )

    if existing is None:
        existing = db.scalar(
            select(Job).where(
                Job.job_url == str(job.job_url)
            )
        )

    return existing
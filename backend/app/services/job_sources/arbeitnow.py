"""Public Arbeitnow job board feed adapter."""

import logging

import httpx
from pydantic import ValidationError

from app.schemas.job import JobCreate
from app.services.job_sources.base import (
    JobSourceError,
    SourceFetchResult,
    clean_text,
    get_json,
    parse_datetime,
)
from app.services.job_sources.greenhouse import html_to_text

logger = logging.getLogger(__name__)

BASE_URL = "https://www.arbeitnow.com/api/job-board-api"

# The feed is paginated newest first, so a few pages are enough to stay
# current without re-reading every historic listing.
PAGE_SIZE = 100
MAX_PAGES = 5


class ArbeitnowSource:
    """Read Arbeitnow's public, Europe-heavy job feed."""

    def __init__(self, client: httpx.Client):
        self.client = client

    def fetch(
        self,
        account_identifier: str = "latest",
        *,
        company_name: str | None = None,
    ) -> SourceFetchResult:
        """Retrieve and normalize the newest pages of the feed."""

        records: list[dict] = []

        for page in range(1, MAX_PAGES + 1):
            data = get_json(
                self.client,
                BASE_URL,
                params={"page": page},
                not_found_reason="feed_not_found",
            )

            current = (
                data.get("data")
                if isinstance(data, dict)
                else None
            )

            if not isinstance(current, list):
                raise JobSourceError("invalid_jobs_payload")

            records.extend(
                item for item in current
                if isinstance(item, dict)
            )

            if len(current) < PAGE_SIZE:
                break

        jobs: list[JobCreate] = []
        skipped = 0
        seen_urls: set[str] = set()

        for record in records:
            title = clean_text(record.get("title"))
            employer = clean_text(record.get("company_name"))
            job_url = record.get("url")
            slug = clean_text(record.get("slug"))

            if (
                not title
                or not employer
                or not isinstance(job_url, str)
                or not job_url.startswith("https://")
                or job_url in seen_urls
            ):
                skipped += 1
                continue

            raw_description = record.get("description")

            description = (
                html_to_text(raw_description)
                if isinstance(raw_description, str)
                else ""
            )

            if not description.strip():
                skipped += 1
                continue

            job_types = record.get("job_types")
            employment_type = None

            if isinstance(job_types, list):
                labels = [
                    label for label in job_types
                    if isinstance(label, str) and label.strip()
                ]

                if labels:
                    employment_type = ", ".join(labels)[:50]

            try:
                job = JobCreate(
                    title=title[:255],
                    company_name=employer[:255],
                    location=clean_text(record.get("location")),
                    description=description[:40000],
                    job_url=job_url,
                    source="arbeitnow",
                    source_job_id=(
                        slug[:100] if slug else None
                    ),
                    employment_type=employment_type,
                    work_mode=(
                        "remote"
                        if record.get("remote") is True
                        else None
                    ),
                    posted_at=parse_datetime(
                        record.get("created_at")
                    ),
                )

            except ValidationError:
                skipped += 1
                continue

            seen_urls.add(job_url)
            jobs.append(job)

        logger.info(
            "Arbeitnow records=%d valid=%d skipped=%d",
            len(records),
            len(jobs),
            skipped,
        )

        return SourceFetchResult(
            provider="arbeitnow",
            account_identifier="latest",
            company_name="Arbeitnow",
            source_count=len(records),
            skipped_count=skipped,
            jobs=jobs,
        )

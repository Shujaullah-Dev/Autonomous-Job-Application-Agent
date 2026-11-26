"""Public Remote OK feed adapter."""

import logging

import httpx
from pydantic import ValidationError

from app.schemas.job import JobCreate
from app.services.job_sources.base import (
    JobSourceError,
    SourceFetchResult,
    annual_salary,
    clean_text,
    get_json,
    parse_datetime,
)
from app.services.job_sources.greenhouse import html_to_text

logger = logging.getLogger(__name__)

BASE_URL = "https://remoteok.com/api"

MAX_JOBS = 500


class RemoteOkSource:
    """Read Remote OK's public feed of current remote roles."""

    def __init__(self, client: httpx.Client):
        self.client = client

    def fetch(
        self,
        account_identifier: str = "all",
        *,
        company_name: str | None = None,
    ) -> SourceFetchResult:
        """Retrieve and normalize the public feed."""

        data = get_json(
            self.client,
            BASE_URL,
            not_found_reason="feed_not_found",
        )

        if not isinstance(data, list):
            raise JobSourceError("invalid_jobs_payload")

        if len(data) > MAX_JOBS:
            raise JobSourceError("feed_too_large")

        jobs: list[JobCreate] = []
        skipped = 0
        seen_ids: set[str] = set()
        seen_urls: set[str] = set()

        for record in data:
            # The first entry holds the API terms, not a listing.
            if not isinstance(record, dict):
                skipped += 1
                continue

            posting_id = record.get("id")
            title = clean_text(record.get("position"))
            employer = clean_text(record.get("company"))
            job_url = record.get("url")

            if not isinstance(posting_id, (str, int)):
                skipped += 1
                continue

            posting_id = str(posting_id)

            if (
                not title
                or not employer
                or not isinstance(job_url, str)
                or not job_url.startswith("https://")
                or posting_id in seen_ids
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

            tags = record.get("tags")
            content = description

            if isinstance(tags, list):
                labels = [
                    tag for tag in tags
                    if isinstance(tag, str) and tag.strip()
                ]

                if labels:
                    content = (
                        f"{description}\n\nTags: "
                        f"{', '.join(labels)}"
                    )

            salary_min, salary_max, currency = annual_salary(
                record.get("salary_min"),
                record.get("salary_max"),
                "USD",
                "annual",
            )

            try:
                job = JobCreate(
                    title=title[:255],
                    company_name=employer[:255],
                    location=clean_text(record.get("location")),
                    description=content[:40000],
                    job_url=job_url,
                    source="remoteok",
                    source_job_id=posting_id,
                    work_mode="remote",
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_currency=currency,
                    posted_at=parse_datetime(record.get("date")),
                )

            except ValidationError:
                skipped += 1
                continue

            seen_ids.add(posting_id)
            seen_urls.add(job_url)
            jobs.append(job)

        logger.info(
            "RemoteOK records=%d valid=%d skipped=%d",
            len(data),
            len(jobs),
            skipped,
        )

        return SourceFetchResult(
            provider="remoteok",
            account_identifier="remote",
            company_name="Remote OK",
            source_count=len(data),
            skipped_count=skipped,
            jobs=jobs,
        )

"""Public Remotive remote job feed adapter."""

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

BASE_URL = "https://remotive.com/api/remote-jobs"

MAX_JOBS = 1000
FETCH_LIMIT = 500


class RemotiveSource:
    """Read Remotive's public feed of current remote roles."""

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
            params={"limit": FETCH_LIMIT},
            not_found_reason="feed_not_found",
        )

        records = (
            data.get("jobs")
            if isinstance(data, dict)
            else None
        )

        if not isinstance(records, list):
            raise JobSourceError("invalid_jobs_payload")

        if len(records) > MAX_JOBS:
            raise JobSourceError("feed_too_large")

        jobs: list[JobCreate] = []
        skipped = 0
        seen_ids: set[str] = set()
        seen_urls: set[str] = set()

        for record in records:
            if not isinstance(record, dict):
                skipped += 1
                continue

            posting_id = record.get("id")
            title = clean_text(record.get("title"))
            employer = clean_text(record.get("company_name"))
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

            job_type = clean_text(record.get("job_type"))

            try:
                job = JobCreate(
                    title=title[:255],
                    company_name=employer[:255],
                    location=clean_text(
                        record.get("candidate_required_location")
                    ),
                    description=description[:40000],
                    job_url=job_url,
                    source="remotive",
                    source_job_id=posting_id,
                    employment_type=(
                        job_type[:50] if job_type else None
                    ),
                    work_mode="remote",
                    posted_at=parse_datetime(
                        record.get("publication_date")
                    ),
                )

            except ValidationError:
                skipped += 1
                continue

            seen_ids.add(posting_id)
            seen_urls.add(job_url)
            jobs.append(job)

        logger.info(
            "Remotive records=%d valid=%d skipped=%d",
            len(records),
            len(jobs),
            skipped,
        )

        return SourceFetchResult(
            provider="remotive",
            account_identifier="remote",
            company_name="Remotive",
            source_count=len(records),
            skipped_count=skipped,
            jobs=jobs,
        )

"""Public Jobicy remote job feed adapter."""

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

BASE_URL = "https://jobicy.com/api/v2/remote-jobs"

FETCH_COUNT = 100


class JobicySource:
    """Read Jobicy's public feed of current remote roles."""

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
            params={"count": FETCH_COUNT},
            not_found_reason="feed_not_found",
        )

        records = (
            data.get("jobs")
            if isinstance(data, dict)
            else None
        )

        if not isinstance(records, list):
            raise JobSourceError("invalid_jobs_payload")

        jobs: list[JobCreate] = []
        skipped = 0
        seen_ids: set[str] = set()
        seen_urls: set[str] = set()

        for record in records:
            if not isinstance(record, dict):
                skipped += 1
                continue

            posting_id = record.get("id")
            title = clean_text(record.get("jobTitle"))
            employer = clean_text(record.get("companyName"))
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

            raw_description = record.get("jobDescription")

            description = (
                html_to_text(raw_description)
                if isinstance(raw_description, str)
                else ""
            )

            if not description.strip():
                description = clean_text(record.get("jobExcerpt")) or ""

            if not description.strip():
                skipped += 1
                continue

            job_types = record.get("jobType")
            employment_type = None

            if isinstance(job_types, list):
                labels = [
                    label for label in job_types
                    if isinstance(label, str) and label.strip()
                ]

                if labels:
                    employment_type = ", ".join(labels)[:50]

            salary_min, salary_max, currency = annual_salary(
                record.get("salaryMin"),
                record.get("salaryMax"),
                record.get("salaryCurrency"),
                record.get("salaryPeriod"),
            )

            try:
                job = JobCreate(
                    title=title[:255],
                    company_name=employer[:255],
                    location=clean_text(record.get("jobGeo")),
                    description=description[:40000],
                    job_url=job_url,
                    source="jobicy",
                    source_job_id=posting_id,
                    employment_type=employment_type,
                    work_mode="remote",
                    salary_min=salary_min,
                    salary_max=salary_max,
                    salary_currency=currency,
                    posted_at=parse_datetime(
                        record.get("pubDate")
                    ),
                )

            except ValidationError:
                skipped += 1
                continue

            seen_ids.add(posting_id)
            seen_urls.add(job_url)
            jobs.append(job)

        logger.info(
            "Jobicy records=%d valid=%d skipped=%d",
            len(records),
            len(jobs),
            skipped,
        )

        return SourceFetchResult(
            provider="jobicy",
            account_identifier="remote",
            company_name="Jobicy",
            source_count=len(records),
            skipped_count=skipped,
            jobs=jobs,
        )

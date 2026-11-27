"""Public Himalayas remote job feed adapter."""

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

BASE_URL = "https://himalayas.app/jobs/api"

FETCH_LIMIT = 100


def describe_location(record: dict) -> str | None:
    """Summarise the countries a remote role accepts."""

    restrictions = record.get("locationRestrictions")

    if not isinstance(restrictions, list):
        return None

    countries = [
        clean_text(value)
        for value in restrictions
        if clean_text(value)
    ]

    if not countries:
        return None

    label = ", ".join(countries[:4])

    if len(countries) > 4:
        label = f"{label} and {len(countries) - 4} more"

    return label[:255]


class HimalayasSource:
    """Read Himalayas' public feed of current remote roles."""

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

        jobs: list[JobCreate] = []
        skipped = 0
        seen_ids: set[str] = set()
        seen_urls: set[str] = set()

        for record in records:
            if not isinstance(record, dict):
                skipped += 1
                continue

            title = clean_text(record.get("title"))
            employer = clean_text(record.get("companyName"))
            job_url = record.get("applicationLink") or record.get(
                "guid"
            )

            if (
                not title
                or not employer
                or not isinstance(job_url, str)
                or not job_url.startswith("https://")
                or job_url in seen_urls
            ):
                skipped += 1
                continue

            posting_id = clean_text(record.get("guid")) or job_url

            if posting_id in seen_ids:
                skipped += 1
                continue

            raw_description = record.get("description")

            description = (
                html_to_text(raw_description)
                if isinstance(raw_description, str)
                else ""
            )

            if not description.strip():
                description = clean_text(record.get("excerpt")) or ""

            if not description.strip():
                skipped += 1
                continue

            salary_min, salary_max, currency = annual_salary(
                record.get("minSalary"),
                record.get("maxSalary"),
                record.get("currency"),
                record.get("salaryPeriod"),
            )

            try:
                job = JobCreate(
                    title=title[:255],
                    company_name=employer[:255],
                    location=describe_location(record),
                    description=description[:40000],
                    job_url=job_url,
                    source="himalayas",
                    source_job_id=posting_id[:100],
                    employment_type=clean_text(
                        record.get("employmentType")
                    )[:50]
                    if clean_text(record.get("employmentType"))
                    else None,
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
            "Himalayas records=%d valid=%d skipped=%d",
            len(records),
            len(jobs),
            skipped,
        )

        return SourceFetchResult(
            provider="himalayas",
            account_identifier="remote",
            company_name="Himalayas",
            source_count=len(records),
            skipped_count=skipped,
            jobs=jobs,
        )

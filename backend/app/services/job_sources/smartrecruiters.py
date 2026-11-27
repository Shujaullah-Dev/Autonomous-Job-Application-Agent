"""Public SmartRecruiters postings API adapter."""

import logging
import re

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

BASE_URL = "https://api.smartrecruiters.com/v1/companies"

COMPANY_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_-]{0,62}\Z"
)

PAGE_SIZE = 100

# The list endpoint carries no job description, so each posting needs a
# second request. The cap keeps one import run bounded and polite.
MAX_DETAILED_POSTINGS = 40


def describe_location(record: dict) -> str | None:
    """Read SmartRecruiters' structured location object."""

    location = record.get("location")

    if not isinstance(location, dict):
        return None

    full = clean_text(location.get("fullLocation"))

    if full:
        return full[:255]

    parts = [
        clean_text(location.get("city")),
        clean_text(location.get("region")),
        clean_text(location.get("country")),
    ]

    label = ", ".join(part for part in parts if part)

    return label[:255] or None


def describe_work_mode(record: dict) -> str | None:
    """Read the remote/hybrid flags on the posting location."""

    location = record.get("location")

    if not isinstance(location, dict):
        return None

    if location.get("remote") is True:
        return "remote"

    if location.get("hybrid") is True:
        return "hybrid"

    return None


class SmartRecruitersSource:
    """Read the public postings of one SmartRecruiters company."""

    def __init__(self, client: httpx.Client):
        self.client = client

    def _description(self, company: str, posting_id: str) -> str:
        """Fetch and flatten the job advertisement of one posting."""

        detail = get_json(
            self.client,
            f"{BASE_URL}/{company}/postings/{posting_id}",
        )

        job_ad = detail.get("jobAd") if isinstance(detail, dict) else None
        sections = (
            job_ad.get("sections")
            if isinstance(job_ad, dict)
            else None
        )

        parts: list[str] = []

        if isinstance(sections, dict):
            for section in sections.values():
                if not isinstance(section, dict):
                    continue

                text = section.get("text")

                if isinstance(text, str):
                    parts.append(html_to_text(text))

        return "\n\n".join(
            part for part in parts if part.strip()
        )

    def fetch(
        self,
        account_identifier: str,
        *,
        company_name: str | None = None,
    ) -> SourceFetchResult:
        """Retrieve and normalize a SmartRecruiters company."""

        company = account_identifier

        if not COMPANY_PATTERN.fullmatch(company):
            raise JobSourceError("invalid_company_identifier")

        data = get_json(
            self.client,
            f"{BASE_URL}/{company}/postings",
            params={"limit": PAGE_SIZE, "offset": 0},
            not_found_reason="company_not_found",
        )

        if not isinstance(data, dict):
            raise JobSourceError("invalid_jobs_payload")

        records = data.get("content")

        if not isinstance(records, list):
            raise JobSourceError("invalid_jobs_payload")

        jobs: list[JobCreate] = []
        skipped = 0
        described = 0
        seen_urls: set[str] = set()

        for record in records:
            if described >= MAX_DETAILED_POSTINGS:
                break

            if not isinstance(record, dict):
                skipped += 1
                continue

            posting_id = record.get("id")
            title = clean_text(record.get("name"))

            if not isinstance(posting_id, (str, int)) or not title:
                skipped += 1
                continue

            posting_id = str(posting_id)

            job_url = (
                f"https://jobs.smartrecruiters.com/{company}/{posting_id}"
            )

            if job_url in seen_urls:
                skipped += 1
                continue

            described += 1

            try:
                description = self._description(company, posting_id)

            except JobSourceError:
                skipped += 1
                continue

            if not description.strip():
                skipped += 1
                continue

            employer = record.get("company")

            employer_name = (
                clean_text(employer.get("name"))
                if isinstance(employer, dict)
                else None
            )

            name = clean_text(company_name) or employer_name or company

            if len(name) > 255:
                raise JobSourceError("invalid_company_name")

            employment = record.get("typeOfEmployment")
            employment_label = (
                clean_text(employment.get("label"))
                if isinstance(employment, dict)
                else None
            )

            try:
                job = JobCreate(
                    title=title,
                    company_name=name,
                    location=describe_location(record),
                    description=description[:40000],
                    job_url=job_url,
                    source=f"smartrecruiters:{company.lower()}",
                    source_job_id=posting_id,
                    employment_type=(
                        employment_label[:50]
                        if employment_label
                        else None
                    ),
                    work_mode=describe_work_mode(record),
                    posted_at=parse_datetime(
                        record.get("releasedDate")
                    ),
                )

            except ValidationError:
                skipped += 1
                continue

            seen_urls.add(job_url)
            jobs.append(job)

        employer_name = (
            jobs[0].company_name
            if jobs
            else clean_text(company_name) or company
        )

        logger.info(
            "SmartRecruiters company=%s listings=%d valid=%d skipped=%d",
            company,
            len(records),
            len(jobs),
            skipped,
        )

        return SourceFetchResult(
            provider="smartrecruiters",
            account_identifier=company,
            company_name=employer_name,
            source_count=len(records),
            skipped_count=skipped,
            jobs=jobs,
        )

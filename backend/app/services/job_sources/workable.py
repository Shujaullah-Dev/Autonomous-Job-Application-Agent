"""Public Workable widget API adapter."""

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

BASE_URL = "https://apply.workable.com/api/v1/widget/accounts"

SITE_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_-]{0,62}\Z"
)

MAX_BOARD_JOBS = 2000


def describe_location(record: dict) -> str | None:
    """Use the first structured location, else the account fields."""

    locations = record.get("locations")

    if isinstance(locations, list):
        for entry in locations:
            if not isinstance(entry, dict) or entry.get("hidden"):
                continue

            parts = [
                clean_text(entry.get("city")),
                clean_text(entry.get("region")),
                clean_text(entry.get("country")),
            ]

            label = ", ".join(
                part for part in parts if part
            )

            if label:
                return label[:255]

    parts = [
        clean_text(record.get("city")),
        clean_text(record.get("state")),
        clean_text(record.get("country")),
    ]

    label = ", ".join(part for part in parts if part)

    return label[:255] or None


class WorkableSource:
    """Read the public listings of one Workable account."""

    def __init__(self, client: httpx.Client):
        self.client = client

    def fetch(
        self,
        account_identifier: str,
        *,
        company_name: str | None = None,
    ) -> SourceFetchResult:
        """Retrieve and normalize a Workable account."""

        site = account_identifier

        if not SITE_PATTERN.fullmatch(site):
            raise JobSourceError("invalid_site_identifier")

        data = get_json(
            self.client,
            f"{BASE_URL}/{site}",
            params={"details": "true"},
            not_found_reason="board_not_found",
        )

        if not isinstance(data, dict):
            raise JobSourceError("invalid_board_payload")

        records = data.get("jobs")

        if not isinstance(records, list):
            raise JobSourceError("invalid_jobs_payload")

        if len(records) > MAX_BOARD_JOBS:
            raise JobSourceError("board_too_large")

        name = (
            clean_text(company_name)
            or clean_text(data.get("name"))
            or site.replace("-", " ").title()
        )

        if len(name) > 255:
            raise JobSourceError("invalid_company_name")

        jobs: list[JobCreate] = []
        skipped = 0
        seen_ids: set[str] = set()
        seen_urls: set[str] = set()

        for record in records:
            if not isinstance(record, dict):
                skipped += 1
                continue

            title = clean_text(record.get("title"))
            shortcode = record.get("shortcode")
            job_url = record.get("url")

            if not isinstance(shortcode, (str, int)):
                skipped += 1
                continue

            shortcode = str(shortcode)

            if (
                not title
                or not isinstance(job_url, str)
                or not job_url.startswith("https://")
                or shortcode in seen_ids
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

            try:
                job = JobCreate(
                    title=title,
                    company_name=name,
                    location=describe_location(record),
                    description=description[:40000],
                    job_url=job_url,
                    source=f"workable:{site.lower()}",
                    source_job_id=shortcode,
                    employment_type=clean_text(
                        record.get("employment_type")
                    )[:50]
                    if clean_text(record.get("employment_type"))
                    else None,
                    work_mode=(
                        "remote"
                        if record.get("telecommuting") is True
                        else None
                    ),
                    posted_at=parse_datetime(
                        record.get("published_on")
                    ),
                )

            except ValidationError:
                skipped += 1
                continue

            seen_ids.add(shortcode)
            seen_urls.add(job_url)
            jobs.append(job)

        logger.info(
            "Workable account=%s listings=%d valid=%d skipped=%d",
            site,
            len(records),
            len(jobs),
            skipped,
        )

        return SourceFetchResult(
            provider="workable",
            account_identifier=site,
            company_name=name,
            source_count=len(records),
            skipped_count=skipped,
            jobs=jobs,
        )

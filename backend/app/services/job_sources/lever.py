
"""Public Lever Postings API adapter."""

import logging
import re

import httpx
from pydantic import ValidationError

from app.schemas.job import JobCreate
from app.services.job_sources.base import SourceFetchResult
from app.services.job_sources.greenhouse import (
    JobSourceError,
    html_to_text,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.lever.co/v0/postings"

SITE_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_-]{0,62}\Z"
)

PAGE_SIZE = 100
MAX_PAGES = 10


def normalize_workplace_type(
    value: object,
) -> str | None:
    """Convert Lever workplace types into our schema."""

    if not isinstance(value, str):
        return None

    mapping = {
        "remote": "remote",
        "hybrid": "hybrid",
        "on-site": "onsite",
        "onsite": "onsite",
    }

    return mapping.get(value.casefold())


class LeverSource:
    """Fetch published jobs from a Lever company site."""

    def __init__(self, client: httpx.Client):
        self.client = client

    def _get_page(
        self,
        site: str,
        skip: int,
    ) -> list[dict]:
        url = f"{BASE_URL}/{site}"

        try:
            response = self.client.get(
                url,
                params={
                    "mode": "json",
                    "skip": skip,
                    "limit": PAGE_SIZE,
                },
            )

        except httpx.TimeoutException as exc:
            raise JobSourceError("timeout") from exc

        except httpx.RequestError as exc:
            raise JobSourceError(
                "network_error"
            ) from exc

        if response.status_code == 429:
            raise JobSourceError(
                "rate_limited", 429
            )

        if response.status_code == 404:
            raise JobSourceError(
                "site_not_found", 404
            )

        if response.status_code != 200:
            raise JobSourceError(
                "http_error",
                response.status_code,
            )

        try:
            data = response.json()

        except ValueError as exc:
            raise JobSourceError(
                "invalid_json"
            ) from exc

        if not isinstance(data, list):
            raise JobSourceError(
                "invalid_jobs_payload"
            )

        if not all(isinstance(item, dict) for item in data):
            raise JobSourceError(
                "invalid_jobs_payload"
            )

        return data

    def fetch(
        self,
        account_identifier: str,
        *,
        company_name: str | None = None,
    ) -> SourceFetchResult:

        site = account_identifier

        if not SITE_PATTERN.fullmatch(site):
            raise JobSourceError(
                "invalid_site_identifier"
            )

        if (
            not isinstance(company_name, str)
            or not company_name.strip()
            or len(company_name.strip()) > 255
        ):
            raise JobSourceError(
                "company_name_required"
            )

        company_name = company_name.strip()

        records: list[dict] = []

        # Lever uses offset pagination.
        for page in range(MAX_PAGES):
            skip = page * PAGE_SIZE

            current = self._get_page(
                site,
                skip,
            )

            records.extend(current)

            if len(current) < PAGE_SIZE:
                break

        jobs: list[JobCreate] = []
        skipped = 0
        seen_ids: set[str] = set()
        seen_urls: set[str] = set()

        for record in records:
            posting_id = record.get("id")
            title = record.get("text")

            categories = record.get("categories")

            if not isinstance(categories, dict):
                categories = {}

            location = categories.get("location")

            if not isinstance(location, str):
                location = None

            description = record.get(
                "descriptionPlain"
            )

            # Prefer Lever's plain-text field.
            if not isinstance(description, str):
                description = record.get("description")

                if isinstance(description, str):
                    description = html_to_text(
                        description
                    )
                else:
                    description = ""

            job_url = record.get("hostedUrl")

            if not isinstance(posting_id, (str, int)):
                skipped += 1
                continue

            posting_id = str(posting_id)

            if (
                not isinstance(title, str)
                or not isinstance(job_url, str)
                or not description.strip()
            ):
                skipped += 1
                continue

            if (
                not job_url.startswith("https://")
                or posting_id in seen_ids
                or job_url in seen_urls
            ):
                skipped += 1
                continue

            commitment = categories.get("commitment")

            if not isinstance(commitment, str):
                commitment = None

            workplace = normalize_workplace_type(
                record.get("workplaceType")
            )

            try:
                job = JobCreate(
                    title=title,
                    company_name=company_name,
                    location=location,
                    description=description[:40000],
                    job_url=job_url,
                    source=f"lever:{site.lower()}",
                    source_job_id=posting_id,
                    employment_type=(
                        commitment[:50]
                        if commitment
                        else None
                    ),
                    work_mode=workplace,
                )

            except ValidationError:
                skipped += 1
                continue

            seen_ids.add(posting_id)
            seen_urls.add(job_url)

            jobs.append(job)

        logger.info(
            "Lever site=%s records=%d valid=%d skipped=%d",
            site,
            len(records),
            len(jobs),
            skipped,
        )

        return SourceFetchResult(
            provider="lever",
            account_identifier=site,
            company_name=company_name,
            source_count=len(records),
            skipped_count=skipped,
            jobs=jobs,
        )

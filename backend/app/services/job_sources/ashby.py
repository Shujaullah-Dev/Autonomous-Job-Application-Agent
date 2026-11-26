"""Public Ashby job board API adapter."""

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

BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"

BOARD_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_-]{0,62}\Z"
)

MAX_BOARD_JOBS = 2000

WORK_MODE = {
    "remote": "remote",
    "hybrid": "hybrid",
    "onsite": "onsite",
    "on-site": "onsite",
    "on site": "onsite",
}

EMPLOYMENT_TYPE = {
    "fulltime": "Full-time",
    "parttime": "Part-time",
    "intern": "Internship",
    "contract": "Contract",
    "temporary": "Temporary",
}


def normalize_workplace_type(
    value: object,
    *,
    is_remote: bool = False,
) -> str | None:
    """Map Ashby workplace types onto the job schema."""

    if isinstance(value, str):
        mode = WORK_MODE.get(value.casefold().strip())

        if mode:
            return mode

    return "remote" if is_remote else None


class AshbySource:
    """Read the public job board of one Ashby customer."""

    def __init__(self, client: httpx.Client):
        self.client = client

    def fetch(
        self,
        account_identifier: str,
        *,
        company_name: str | None = None,
    ) -> SourceFetchResult:
        """Retrieve and normalize a single Ashby board."""

        board = account_identifier

        if not BOARD_PATTERN.fullmatch(board):
            raise JobSourceError("invalid_board_token")

        # Ashby does not publish the employer display name on this endpoint,
        # so the caller supplies it; the token is a readable fallback.
        name = clean_text(company_name) or board.replace(
            "-", " "
        ).replace("_", " ").title()

        if len(name) > 255:
            raise JobSourceError("invalid_company_name")

        data = get_json(
            self.client,
            f"{BASE_URL}/{board}",
            params={"includeCompensation": "true"},
            not_found_reason="board_not_found",
        )

        records = (
            data.get("jobs")
            if isinstance(data, dict)
            else None
        )

        if not isinstance(records, list):
            raise JobSourceError("invalid_jobs_payload")

        if len(records) > MAX_BOARD_JOBS:
            raise JobSourceError("board_too_large")

        jobs: list[JobCreate] = []
        skipped = 0
        seen_ids: set[str] = set()
        seen_urls: set[str] = set()

        for record in records:
            if not isinstance(record, dict):
                skipped += 1
                continue

            # Unlisted postings are drafts or internal requisitions.
            if record.get("isListed") is False:
                skipped += 1
                continue

            posting_id = record.get("id")
            title = clean_text(record.get("title"))
            job_url = record.get("jobUrl")

            if not isinstance(posting_id, (str, int)):
                skipped += 1
                continue

            posting_id = str(posting_id)

            if (
                not title
                or not isinstance(job_url, str)
                or not job_url.startswith("https://")
                or posting_id in seen_ids
                or job_url in seen_urls
            ):
                skipped += 1
                continue

            raw_description = record.get("descriptionHtml")

            description = (
                html_to_text(raw_description)
                if isinstance(raw_description, str)
                else ""
            )

            if not description.strip():
                skipped += 1
                continue

            employment = record.get("employmentType")

            employment_type = (
                EMPLOYMENT_TYPE.get(
                    employment.casefold().strip()
                )
                if isinstance(employment, str)
                else None
            )

            try:
                job = JobCreate(
                    title=title,
                    company_name=name,
                    location=clean_text(record.get("location")),
                    description=description[:40000],
                    job_url=job_url,
                    source=f"ashby:{board.lower()}",
                    source_job_id=posting_id,
                    employment_type=employment_type,
                    work_mode=normalize_workplace_type(
                        record.get("workplaceType"),
                        is_remote=record.get("isRemote") is True,
                    ),
                    posted_at=parse_datetime(
                        record.get("publishedAt")
                    ),
                )

            except ValidationError:
                skipped += 1
                continue

            seen_ids.add(posting_id)
            seen_urls.add(job_url)
            jobs.append(job)

        logger.info(
            "Ashby board=%s listings=%d valid=%d skipped=%d",
            board,
            len(records),
            len(jobs),
            skipped,
        )

        return SourceFetchResult(
            provider="ashby",
            account_identifier=board,
            company_name=name,
            source_count=len(records),
            skipped_count=skipped,
            jobs=jobs,
        )

"""Read public job listings from one Greenhouse board."""

import html
import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser

import httpx
from pydantic import ValidationError

from app.schemas.job import JobCreate
from app.services.job_sources.base import (
    SourceFetchResult,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

# Pattern allows standard Greenhouse board tokens
BOARD_TOKEN_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_-]{0,62}\Z"
)

MAX_BOARD_JOBS = 2000


class JobSourceError(RuntimeError):
    def __init__(
        self,
        reason: str,
        status_code: int | None = None,
    ):
        self.reason = reason
        self.status_code = status_code
        super().__init__(reason)


@dataclass(frozen=True)
class GreenhouseFetchResult:
    board_token: str
    company_name: str
    source_count: int
    skipped_count: int
    jobs: list[JobCreate]


class _HTMLToText(HTMLParser):
    """Convert basic HTML descriptions into safe plain text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag in {"script", "style"}:
            self.ignored_depth += 1

        if tag in {
            "br", "p", "div", "li",
            "h1", "h2", "h3", "h4",
        }:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if (
            tag in {"script", "style"}
            and self.ignored_depth > 0
        ):
            self.ignored_depth -= 1

        if tag in {
            "p", "div", "li",
            "h1", "h2", "h3", "h4",
        }:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.ignored_depth == 0:
            self.parts.append(data)


def html_to_text(value: str) -> str:
    """Decode HTML entities and remove markup."""

    clean = html.unescape(html.unescape(value))

    parser = _HTMLToText()
    parser.feed(clean)

    text = "".join(parser.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*\n+", "\n", text)

    return text.strip()


class GreenhouseSource:
    """Adapter for the public Greenhouse Job Board API."""

    def __init__(self, client: httpx.Client):
        self.client = client

    def _get_json(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
    ):
        try:
            response = self.client.get(
                url,
                params=params,
            )

        except httpx.TimeoutException as exc:
            raise JobSourceError("timeout") from exc

        except httpx.RequestError as exc:
            raise JobSourceError("network_error") from exc

        if response.status_code == 429:
            raise JobSourceError(
                "rate_limited", 429
            )

        if response.status_code == 404:
            raise JobSourceError(
                "board_not_found", 404
            )

        if response.status_code != 200:
            raise JobSourceError(
                "http_error",
                response.status_code,
            )

        try:
            return response.json()

        except ValueError as exc:
            raise JobSourceError(
                "invalid_json"
            ) from exc

    def fetch(
        self,
        account_identifier: str,
        *,
        company_name: str | None = None,
    ) -> SourceFetchResult:
        """Retrieve and normalize published board jobs."""

        if not BOARD_TOKEN_PATTERN.fullmatch(
            account_identifier
        ):
            raise JobSourceError(
                "invalid_board_token"
            )

        url = f"{BASE_URL}/{account_identifier}"

        # Get the company's verified board name if not supplied
        board_data = self._get_json(url)

        if not isinstance(board_data, dict):
            raise JobSourceError(
                "invalid_board_payload"
            )

        verified_company_name = board_data.get("name")

        if (
            not isinstance(verified_company_name, str)
            or not verified_company_name.strip()
            or len(verified_company_name.strip()) > 255
        ):
            raise JobSourceError(
                "invalid_board_name"
            )
        
        # Keep the verified company name from the API
        company_name = verified_company_name.strip()

        # Retrieve the full published job descriptions.
        listing = self._get_json(
            f"{url}/jobs",
            params={"content": "true"},
        )

        if (
            not isinstance(listing, dict)
            or not isinstance(
                listing.get("jobs"), list
            )
        ):
            raise JobSourceError(
                "invalid_jobs_payload"
            )

        records = listing["jobs"]

        if len(records) > MAX_BOARD_JOBS:
            raise JobSourceError(
                "board_too_large"
            )

        jobs: list[JobCreate] = []
        skipped = 0
        seen_urls: set[str] = set()

        for record in records:
            if not isinstance(record, dict):
                skipped += 1
                continue

            # A prospect post is not a specific vacancy.
            if (
                "internal_job_id" in record
                and record["internal_job_id"] is None
            ):
                skipped += 1
                continue

            location_data = record.get("location")

            location = (
                location_data.get("name")
                if isinstance(location_data, dict)
                else None
            )

            if not isinstance(location, str):
                location = None

            content = record.get("content")

            description = (
                html_to_text(content)
                if isinstance(content, str)
                else ""
            )

            try:
                job = JobCreate(
                    title=record.get("title"),
                    company_name=company_name,
                    location=location,
                    description=description[:40000],
                    job_url=record.get(
                        "absolute_url"
                    ),
                    source=(
                        "greenhouse:"
                        f"{account_identifier.lower()}"
                    ),
                    source_job_id=str(record.get("id")),
                    work_mode=(
                        "remote"
                        if location
                        and location.casefold().strip()
                        == "remote"
                        else None
                    ),
                )

            except ValidationError:
                skipped += 1
                continue

            normalized_url = str(job.job_url)

            if normalized_url in seen_urls:
                skipped += 1
                continue

            seen_urls.add(normalized_url)
            jobs.append(job)

        logger.info(
            "Greenhouse account=%s listings=%d "
            "valid=%d skipped=%d",
            account_identifier,
            len(records),
            len(jobs),
            skipped,
        )

        return SourceFetchResult(
            provider="greenhouse",
            account_identifier=account_identifier,
            company_name=company_name,
            source_count=len(records),
            skipped_count=skipped,
            jobs=jobs,
        )
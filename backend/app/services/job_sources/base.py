"""Common contract and shared helpers for external job providers."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import httpx

from app.schemas.job import JobCreate


class JobSourceError(RuntimeError):
    """A provider could not be read; the reason is safe to log."""

    def __init__(
        self,
        reason: str,
        status_code: int | None = None,
    ):
        self.reason = reason
        self.status_code = status_code
        super().__init__(reason)


@dataclass(frozen=True)
class SourceFetchResult:
    provider: str
    account_identifier: str
    company_name: str
    source_count: int
    skipped_count: int
    jobs: list[JobCreate]


class JobSource(Protocol):
    """Contract that every job provider must implement."""

    def fetch(
        self,
        account_identifier: str,
        *,
        company_name: str | None = None,
    ) -> SourceFetchResult:
        """Fetch and normalize published job listings."""
        ...


def get_json(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, str | int] | None = None,
    not_found_reason: str = "not_found",
):
    """GET a JSON document, mapping transport problems to JobSourceError."""

    try:
        response = client.get(url, params=params)

    except httpx.TimeoutException as exc:
        raise JobSourceError("timeout") from exc

    except httpx.RequestError as exc:
        raise JobSourceError("network_error") from exc

    if response.status_code == 429:
        raise JobSourceError("rate_limited", 429)

    if response.status_code == 404:
        raise JobSourceError(not_found_reason, 404)

    if response.status_code != 200:
        raise JobSourceError("http_error", response.status_code)

    try:
        return response.json()

    except ValueError as exc:
        raise JobSourceError("invalid_json") from exc


def parse_datetime(value: object) -> datetime | None:
    """Parse ISO strings and unix timestamps; unknown values become None."""

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(
                float(value),
                tz=UTC,
            )
        except (OverflowError, OSError, ValueError):
            return None

    if not isinstance(value, str):
        return None

    text = value.strip()

    if not text:
        return None

    if text.isdigit():
        return parse_datetime(int(text))

    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )

    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed


def clean_text(value: object) -> str | None:
    """Collapse whitespace in a short provider value."""

    if not isinstance(value, str):
        return None

    text = " ".join(value.split())

    return text or None


def annual_salary(
    minimum: object,
    maximum: object,
    currency: object,
    period: object,
) -> tuple[int | None, int | None, str | None]:
    """Return a validated annual salary range, or nothing at all."""

    if not isinstance(currency, str):
        return None, None, None

    code = currency.strip().upper()

    if len(code) != 3 or not code.isalpha():
        return None, None, None

    if period is not None:
        if not isinstance(period, str):
            return None, None, None

        if period.strip().casefold() not in {
            "year",
            "yearly",
            "annual",
            "annually",
            "per year",
        }:
            return None, None, None

    def amount(value: object) -> int | None:
        if isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            number = int(value)
        elif isinstance(value, str):
            digits = value.strip().replace(",", "")

            if not digits.isdigit():
                return None

            number = int(digits)
        else:
            return None

        return number if number > 0 else None

    low = amount(minimum)
    high = amount(maximum)

    if low is None and high is None:
        return None, None, None

    if low is not None and high is not None and high < low:
        low, high = high, low

    return low, high, code

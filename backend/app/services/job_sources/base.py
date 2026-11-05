
"""Common contract for external job providers."""

from dataclasses import dataclass
from typing import Protocol

from app.schemas.job import JobCreate


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

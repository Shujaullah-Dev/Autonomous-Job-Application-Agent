"""Common structural contract for external job sources."""

from typing import Protocol, TypeVar

ResultT = TypeVar("ResultT", covariant=True)


class JobSource(Protocol[ResultT]):
    def fetch(self, board_token: str) -> ResultT:
        """Fetch jobs from a configured source."""
        ...

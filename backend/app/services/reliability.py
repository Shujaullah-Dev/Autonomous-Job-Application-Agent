
"""Bounded retries for idempotent, read-only database queries."""

import time
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

T = TypeVar("T")

# PostgreSQL transient connection / transaction errors.
RETRYABLE_SQLSTATES = {
    "08000",  # Connection exception
    "08003",  # Connection does not exist
    "08006",  # Connection failure
    "40001",  # Serialization failure
    "40P01",  # Deadlock detected
    "57P01",  # Administrator shutdown
}


def is_retryable(exc: DBAPIError) -> bool:
    """Do not retry arbitrary SQL errors."""

    code = (
        getattr(exc.orig, "sqlstate", None)
        or getattr(exc.orig, "pgcode", None)
    )

    return bool(
        exc.connection_invalidated
        or code in RETRYABLE_SQLSTATES
    )


def read_with_retry(
    db: Session,
    operation: Callable[[], T],
    *,
    max_attempts: int = 3,
    delay_seconds: float = 0.05,
    sleeper: Callable[[float], None] = time.sleep,
) -> T:
    """
    Run ONLY a read-only database operation.

    On database failures, roll back before retrying.
    Never use for submissions, inserts, commits or
    other operations with uncertain side effects.
    """

    if not 1 <= max_attempts <= 5:
        raise ValueError("max_attempts must be 1..5")

    if not 0 <= delay_seconds <= 1:
        raise ValueError("Invalid retry delay")

    for attempt in range(max_attempts):
        try:
            return operation()

        except DBAPIError as exc:
            db.rollback()

            if (
                not is_retryable(exc)
                or attempt == max_attempts - 1
            ):
                raise

            # Small bounded exponential backoff.
            sleeper(delay_seconds * (2**attempt))

    raise RuntimeError("Unreachable retry state")


"""Safe retry utility tests."""

from unittest.mock import MagicMock

import pytest
from app.services.reliability import read_with_retry
from sqlalchemy.exc import OperationalError


def db_error(*, transient: bool):
    return OperationalError(
        "SELECT 1",
        {},
        Exception("simulated error"),
        connection_invalidated=transient,
    )


def test_transient_error_retries_read_only_operation():
    db = MagicMock()
    attempts = 0
    delays = []

    def read():
        nonlocal attempts
        attempts += 1

        if attempts == 1:
            raise db_error(transient=True)

        return 42

    result = read_with_retry(
        db,
        read,
        sleeper=delays.append,
    )

    assert result == 42
    assert attempts == 2
    assert db.rollback.call_count == 1
    assert delays == [0.05]


def test_permanent_error_does_not_retry():
    db = MagicMock()
    attempts = 0

    def read():
        nonlocal attempts
        attempts += 1
        raise db_error(transient=False)

    with pytest.raises(OperationalError):
        read_with_retry(
            db,
            read,
            sleeper=lambda _: None,
        )

    assert attempts == 1


def test_retry_is_bounded():
    db = MagicMock()
    attempts = 0

    def failing_read():
        nonlocal attempts
        attempts += 1
        raise db_error(transient=True)

    with pytest.raises(OperationalError):
        read_with_retry(
            db,
            failing_read,
            max_attempts=3,
            sleeper=lambda _: None,
        )

    assert attempts == 3
    assert db.rollback.call_count == 3


def test_invalid_attempts_rejected():
    with pytest.raises(ValueError):
        read_with_retry(
            MagicMock(),
            lambda: 1,
            max_attempts=0,
        )

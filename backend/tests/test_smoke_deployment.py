"""Offline tests for the local deployment smoke checker."""

import json
from io import BytesIO
from urllib.error import URLError

import pytest
from app.scripts.smoke_deployment import (
    smoke_check,
    validate_local_base_url,
)


def test_smoke_check_passes():
    called = []

    def fake_open(url, timeout):
        called.append(url)

        if url.endswith("/health/db"):
            payload = {
                "status": "ok",
                "database": "connected",
            }
        else:
            payload = {"status": "ok"}

        return BytesIO(json.dumps(payload).encode())

    paths = smoke_check(
        "http://127.0.0.1:8000",
        opener=fake_open,
    )

    assert paths == ["/health", "/health/db"]
    assert len(called) == 2


def test_can_skip_database_check():
    def fake_open(url, timeout):
        return BytesIO(b'{"status":"ok"}')

    paths = smoke_check(
        "http://localhost:8000",
        check_database=False,
        opener=fake_open,
    )

    assert paths == ["/health"]


@pytest.mark.parametrize(
    "base_url",
    [
        "https://example.com",
        "http://example.com:8000",
        "http://127.0.0.1:8000/admin",
        "http://user:password@localhost:8000",
        "ftp://localhost:8000",
    ],
)
def test_nonlocal_or_invalid_targets_rejected(base_url):
    with pytest.raises(ValueError):
        validate_local_base_url(base_url)


def test_database_outage_fails_cleanly():
    def fake_open(url, timeout):
        if url.endswith("/health/db"):
            raise URLError("simulated database outage")

        return BytesIO(b'{"status":"ok"}')

    with pytest.raises(
        RuntimeError,
        match="/health/db",
    ):
        smoke_check(
            "http://127.0.0.1:8000",
            opener=fake_open,
        )


def test_unexpected_health_payload_fails():
    def fake_open(url, timeout):
        return BytesIO(b'{"status":"error"}')

    with pytest.raises(RuntimeError):
        smoke_check(
            "http://127.0.0.1:8000",
            opener=fake_open,
        )
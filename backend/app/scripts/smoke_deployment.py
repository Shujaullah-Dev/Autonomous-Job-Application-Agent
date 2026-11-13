"""Smoke-test a local AI Job Agent deployment."""

import argparse
import json
import sys
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen


def validate_local_base_url(value: str) -> str:
    """Allow checks against localhost only."""

    parsed = urlsplit(value)

    if parsed.scheme != "http":
        raise ValueError("Smoke-test URL must use http")

    if parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError(
            "Smoke-test target must be localhost"
        )

    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Credentials are not allowed in the URL")

    if parsed.path not in {"", "/"}:
        raise ValueError("Use a base URL without a path")

    if parsed.query or parsed.fragment:
        raise ValueError("Query strings are not allowed")

    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Invalid port")

    return value.rstrip("/")


def smoke_check(
    base_url: str,
    *,
    check_database: bool = True,
    opener=urlopen,
) -> list[str]:
    """Check liveness, then optionally database connectivity."""

    base = validate_local_base_url(base_url)

    paths = ["/health"]

    if check_database:
        paths.append("/health/db")

    for path in paths:
        try:
            with opener(
                f"{base}{path}",
                timeout=5,
            ) as response:
                payload = json.loads(
                    response.read().decode("utf-8")
                )

        except (URLError, OSError, ValueError) as exc:
            raise RuntimeError(
                f"Smoke check failed at {path}"
            ) from exc

        if payload.get("status") != "ok":
            raise RuntimeError(
                f"Unexpected health response at {path}"
            )

        if path == "/health/db":
            if payload.get("database") != "connected":
                raise RuntimeError(
                    "Database health response is not connected"
                )

    return paths


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check a local FastAPI deployment."
    )

    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
    )

    parser.add_argument(
        "--skip-database",
        action="store_true",
        help="Check the API process without querying Supabase.",
    )

    args = parser.parse_args()

    try:
        checked = smoke_check(
            args.base_url,
            check_database=not args.skip_database,
        )

    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    for path in checked:
        print(f"PASS {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
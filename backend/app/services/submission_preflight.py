
"""Validate application readiness for manual handoff."""

import ipaddress
import re
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import (
    Application,
    ApplicationDraftRevision,
)
from app.models.job import Job


@dataclass(frozen=True)
class PreflightCheck:
    code: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    candidate_id: uuid.UUID
    application_id: uuid.UUID
    application_status: str
    revision_number: int
    provider_hint: str
    can_handoff: bool
    destination_url: str | None
    checks: tuple[PreflightCheck, ...]
    warnings: tuple[str, ...]


def safe_external_url(value: str) -> bool:
    """
    Validate a URL for a MANUAL browser handoff.

    This function does not open, fetch or resolve the URL.
    """

    if not isinstance(value, str):
        return False

    if not value or value != value.strip():
        return False

    if any(
        ord(char) < 32 or ord(char) == 127 or char.isspace()
        for char in value
    ):
        return False

    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        return False

    if parsed.scheme.lower() != "https":
        return False

    if not parsed.netloc or not host:
        return False

    if parsed.username is not None or parsed.password is not None:
        return False

    if port not in {None, 443}:
        return False

    if not re.fullmatch(r"[a-z0-9.-]+", host):
        return False

    if ".." in host or host.startswith(".") or host.endswith("."):
        return False

    if "." not in host:
        return False

    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        # No IP literals, including public IP literals.
        return False

    blocked_domains = {
        "localhost",
        "local",
        "internal",
        "test",
        "example",
        "invalid",
        "onion",
        "example.com",
        "example.org",
        "example.net",
    }

    if any(
        host == domain or host.endswith("." + domain)
        for domain in blocked_domains
    ):
        return False

    return True


def identify_provider(source: str | None) -> str:
    """
    Informational provider hint only.

    This does not mean automated submission is supported.
    """

    value = (source or "").casefold()

    if value.startswith("greenhouse:"):
        return "greenhouse"

    if value.startswith("lever:"):
        return "lever"

    return "external"


def evaluate_submission_preflight(
    db: Session,
    application: Application,
) -> PreflightReport:
    """Check a tracked application before manual handoff."""

    checks: list[PreflightCheck] = []
    warnings: list[str] = []

    def add_check(
        code: str,
        passed: bool,
        detail: str,
    ) -> None:
        checks.append(
            PreflightCheck(
                code=code,
                passed=passed,
                detail=detail,
            )
        )

    add_check(
        "application_ready",
        application.status == "ready",
        "Application must be in ready status.",
    )

    job = db.get(Job, application.job_id)

    active = job is not None and job.is_active is True

    add_check(
        "job_active",
        active,
        "The current job record must exist and be active.",
    )

    source = job.source if job else None

    is_demo = bool(
        job
        and (
            (job.source or "").casefold() == "lever:leverdemo"
            or "fictional job created solely"
            in (job.description or "").casefold()
        )
    )

    add_check(
        "not_demo_listing",
        not is_demo,
        "Demonstration or fictional jobs cannot be handed off.",
    )

    unchanged = bool(
        job
        and job.title == application.job_title
        and job.company_name == application.company_name
        and job.job_url == application.job_url
    )

    add_check(
        "job_snapshot_unchanged",
        unchanged,
        "The job title, employer and URL must match "
        "the tracked application.",
    )

    url_ok = safe_external_url(application.job_url)

    add_check(
        "safe_destination",
        url_ok,
        "The destination must be a valid public HTTPS "
        "hostname without embedded credentials.",
    )

    latest = db.scalar(
        select(ApplicationDraftRevision)
        .where(
            ApplicationDraftRevision.application_id
            == application.id,
            ApplicationDraftRevision.revision_number
            == application.current_revision,
        )
    )

    draft_ok = bool(
        latest
        and latest.cover_letter.strip()
        and isinstance(latest.resume_snapshot, dict)
        and latest.resume_snapshot.get("candidate_name")
    )

    add_check(
        "saved_draft_exists",
        draft_ok,
        "The current draft revision and resume snapshot "
        "must be available.",
    )

    if job and job.work_mode is None:
        warnings.append(
            "Work mode is unknown. Do not assume "
            "the position is remote."
        )

    warnings.append(
        "Country eligibility, visa requirements and "
        "work authorization have not been verified."
    )

    warnings.append(
        "The employer may require additional questions "
        "or supporting documents."
    )

    warnings.append(
        "This handoff does not submit an application "
        "or confirm that the employer received one."
    )

    can_handoff = all(check.passed for check in checks)

    return PreflightReport(
        candidate_id=application.candidate_id,
        application_id=application.id,
        application_status=application.status,
        revision_number=application.current_revision,
        provider_hint=identify_provider(source),
        can_handoff=can_handoff,
        destination_url=(
            application.job_url if can_handoff else None
        ),
        checks=tuple(checks),
        warnings=tuple(warnings),
    )
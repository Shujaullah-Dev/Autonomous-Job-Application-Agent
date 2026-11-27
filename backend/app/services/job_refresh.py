"""Keep job listings fresh, on a schedule or on request.

The refresh reuses the provider adapters and the ingestion service, so a
scheduled run, an API-triggered run and the command-line importer all behave
the same way. Only one refresh runs at a time; a second request is refused
instead of competing for the same provider APIs and database rows.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.job_ingestion import (
    JobIngestionError,
    SeenListings,
    deactivate_missing_jobs,
    ingest_jobs,
)
from app.services.job_sources import (
    JobSourceError,
    SourceSpec,
    build_source,
    default_sources,
)

logger = logging.getLogger(__name__)

REFRESH_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "AIJobAgent/0.1",
}


@dataclass
class SourceFailure:
    source: str
    reason: str


@dataclass
class RefreshReport:
    """Progress and the final tally of one refresh."""

    trigger: str
    started_at: datetime
    finished_at: datetime | None = None
    running: bool = True
    created: int = 0
    updated: int = 0
    skipped: int = 0
    deactivated: int = 0
    possible_duplicates: int = 0
    sources_total: int = 0
    sources_ok: int = 0
    failures: list[SourceFailure] = field(default_factory=list)
    message: str | None = None


_lock = threading.Lock()
_current: RefreshReport | None = None
_thread: threading.Thread | None = None
_last_finished: float | None = None
_scheduler_thread: threading.Thread | None = None
_scheduler_stop = threading.Event()


def _utcnow() -> datetime:
    return datetime.now(UTC)


def run_refresh(
    db: Session,
    *,
    specs: list[SourceSpec] | None = None,
    max_per_source: int | None = None,
    trigger: str = "manual",
    report: RefreshReport | None = None,
    client: httpx.Client | None = None,
) -> RefreshReport:
    """Fetch every source and ingest what it returns.

    A failing source is recorded on the report instead of aborting the run,
    exactly like the command-line importer.
    """

    specs = specs if specs is not None else default_sources()
    limit = max_per_source or settings.job_refresh_max_per_source
    report = report or RefreshReport(
        trigger=trigger,
        started_at=_utcnow(),
        sources_total=len(specs),
    )
    report.sources_total = len(specs)

    seen = SeenListings()
    owns_client = client is None
    http = client or httpx.Client(
        timeout=settings.job_source_timeout_seconds,
        follow_redirects=False,
        headers=REFRESH_HEADERS,
    )

    try:
        for spec in specs:
            source = build_source(http, spec.provider)

            try:
                result = source.fetch(
                    spec.identifier,
                    company_name=spec.company_name,
                )

            except JobSourceError as exc:
                report.failures.append(
                    SourceFailure(spec.label, exc.reason)
                )
                logger.info(
                    "Job refresh: %s failed (%s)",
                    spec.label,
                    exc.reason,
                )
                continue

            except Exception as exc:  # noqa: BLE001 - one source must not stop a run
                report.failures.append(
                    SourceFailure(spec.label, type(exc).__name__)
                )
                logger.exception("Job refresh: %s raised", spec.label)
                continue

            # The full response counts as seen, even when this run imports
            # only part of it, so truncation never closes live roles.
            for item in result.jobs:
                seen.add(item)

            try:
                summary = ingest_jobs(
                    db,
                    result.jobs[:limit],
                    apply=True,
                )

            except (JobIngestionError, ValueError) as exc:
                db.rollback()
                report.failures.append(
                    SourceFailure(
                        spec.label,
                        getattr(exc, "reason", None) or str(exc),
                    )
                )
                continue

            report.sources_ok += 1
            report.created += summary.created
            report.updated += summary.updated
            report.skipped += summary.skipped
            report.possible_duplicates += (
                summary.possible_duplicates
            )

    finally:
        if owns_client:
            http.close()

    try:
        report.deactivated = deactivate_missing_jobs(db, seen)

    except Exception:  # noqa: BLE001 - closing stale roles must not lose the run
        db.rollback()
        logger.exception("Job refresh: could not close missing listings")
        report.failures.append(
            SourceFailure("missing listings", "deactivation_failed")
        )

    report.finished_at = _utcnow()
    report.running = False

    return report


def _worker(
    report: RefreshReport,
    max_per_source: int | None,
) -> None:
    global _last_finished

    try:
        with SessionLocal() as db:
            run_refresh(
                db,
                max_per_source=max_per_source,
                trigger=report.trigger,
                report=report,
            )

    except Exception as exc:  # noqa: BLE001 - keep the thread alive
        logger.exception("Job refresh failed")
        report.message = f"Refresh failed: {type(exc).__name__}"
        report.finished_at = _utcnow()
        report.running = False

    finally:
        _last_finished = time.monotonic()


def _snapshot() -> dict:
    report = _current

    enabled = settings.job_refresh_enabled

    if report is None:
        return {
            "running": False,
            "trigger": None,
            "started_at": None,
            "finished_at": None,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "deactivated": 0,
            "possible_duplicates": 0,
            "sources_total": 0,
            "sources_ok": 0,
            "failures": [],
            "enabled": enabled,
            "interval_hours": settings.job_refresh_interval_hours,
            "message": None,
        }

    return {
        "running": report.running,
        "trigger": report.trigger,
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "created": report.created,
        "updated": report.updated,
        "skipped": report.skipped,
        "deactivated": report.deactivated,
        "possible_duplicates": report.possible_duplicates,
        "sources_total": report.sources_total,
        "sources_ok": report.sources_ok,
        "failures": [
            {"source": failure.source, "reason": failure.reason}
            for failure in report.failures
        ],
        "enabled": enabled,
        "interval_hours": settings.job_refresh_interval_hours,
        "message": report.message,
    }


def refresh_status() -> dict:
    """Return the latest refresh state, running or finished."""

    with _lock:
        return _snapshot()


def start_refresh(
    trigger: str = "manual",
    *,
    max_per_source: int | None = None,
) -> tuple[bool, str, dict]:
    """Start a refresh in a background thread.

    Returns ``(started, reason, status)``. The API answers 202 for a started
    run and 409 with the current status otherwise.
    """

    global _current, _thread

    with _lock:
        if _thread is not None and _thread.is_alive():
            return False, "already_running", _snapshot()

        if (
            trigger == "manual"
            and _last_finished is not None
            and time.monotonic() - _last_finished
            < settings.job_refresh_min_interval_seconds
        ):
            return False, "cooldown", _snapshot()

        report = RefreshReport(
            trigger=trigger,
            started_at=_utcnow(),
            sources_total=len(default_sources()),
        )
        _current = report
        _thread = threading.Thread(
            target=_worker,
            args=(report, max_per_source),
            name="job-refresh",
            daemon=True,
        )
        thread = _thread

    thread.start()

    return True, "started", refresh_status()


def _scheduler_loop() -> None:
    interval = max(
        300.0,
        settings.job_refresh_interval_hours * 3600.0,
    )

    if settings.job_refresh_on_startup:
        start_refresh("startup")

    while not _scheduler_stop.wait(interval):
        start_refresh("schedule")


def start_scheduler() -> None:
    """Start the periodic refresh thread when it is enabled."""

    global _scheduler_thread

    if not settings.job_refresh_enabled:
        return

    if (
        _scheduler_thread is not None
        and _scheduler_thread.is_alive()
    ):
        return

    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(
        target=_scheduler_loop,
        name="job-refresh-scheduler",
        daemon=True,
    )
    _scheduler_thread.start()

    logger.info(
        "Job refresh scheduled every %s hours",
        settings.job_refresh_interval_hours,
    )


def stop_scheduler() -> None:
    """Ask the periodic refresh thread to exit."""

    _scheduler_stop.set()

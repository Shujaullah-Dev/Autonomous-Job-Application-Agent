"""On-demand and scheduled job refresh."""

import threading
from datetime import UTC, datetime

import httpx
import pytest
from app.main import app
from app.models.job import Job
from app.services import job_refresh as refresh_module
from app.services.job_refresh import (
    RefreshReport,
    refresh_status,
    run_refresh,
)
from app.services.job_sources import SourceSpec
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Job.__table__.create(engine)

    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def ashby_handler(request):
    if "/job-board/demo" in str(request.url):
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": "ashby-1",
                        "title": "Backend Engineer",
                        "location": "Berlin",
                        "isListed": True,
                        "workplaceType": "Hybrid",
                        "publishedAt": "2026-11-20T10:00:00+00:00",
                        "jobUrl": (
                            "https://jobs.ashbyhq.com/demo/ashby-1"
                        ),
                        "descriptionHtml": "<p>Build APIs.</p>",
                    }
                ]
            },
        )

    return httpx.Response(404)


def test_run_refresh_imports_and_reports_failures(db):
    specs = [
        SourceSpec("ashby", "demo", "Demo Inc"),
        SourceSpec("ashby", "missing", "Missing Inc"),
    ]

    with httpx.Client(
        transport=httpx.MockTransport(ashby_handler)
    ) as client:
        report = run_refresh(
            db,
            specs=specs,
            max_per_source=10,
            client=client,
        )

    assert report.running is False
    assert report.sources_total == 2
    assert report.sources_ok == 1
    assert report.created == 1
    assert report.finished_at is not None

    assert len(report.failures) == 1
    assert "Missing Inc" in report.failures[0].source
    assert report.failures[0].reason == "board_not_found"

    stored = db.scalars(select(Job)).all()

    assert len(stored) == 1
    assert stored[0].source == "ashby:demo"


def test_run_refresh_reuses_an_existing_report(db):
    report = RefreshReport(
        trigger="schedule",
        started_at=datetime.now(UTC),
    )

    with httpx.Client(
        transport=httpx.MockTransport(ashby_handler)
    ) as client:
        finished = run_refresh(
            db,
            specs=[SourceSpec("ashby", "demo", "Demo Inc")],
            report=report,
            client=client,
        )

    assert finished is report
    assert finished.trigger == "schedule"
    assert finished.created == 1


def test_run_refresh_closes_listings_the_provider_dropped(db):
    with httpx.Client(
        transport=httpx.MockTransport(ashby_handler)
    ) as client:
        run_refresh(
            db,
            specs=[SourceSpec("ashby", "demo", "Demo Inc")],
            client=client,
        )

    gone = Job(
        title="Old Role",
        company_name="Demo Inc",
        description="Closed last week.",
        job_url="https://jobs.ashbyhq.com/demo/gone",
        canonical_url="https://jobs.ashbyhq.com/demo/gone",
        source="ashby:demo",
        source_job_id="gone",
        is_active=True,
    )
    db.add(gone)
    db.commit()

    with httpx.Client(
        transport=httpx.MockTransport(ashby_handler)
    ) as client:
        report = run_refresh(
            db,
            specs=[SourceSpec("ashby", "demo", "Demo Inc")],
            client=client,
        )

    db.refresh(gone)

    assert report.deactivated == 1
    assert gone.is_active is False

    still_listed = db.scalar(
        select(Job).where(Job.source_job_id == "ashby-1")
    )

    assert still_listed is not None
    assert still_listed.is_active is True


def test_run_refresh_keeps_roles_listed_by_another_provider(db):
    # A role imported from Ashby that Remotive also publishes must stay open.
    shared = Job(
        title="Backend Engineer",
        company_name="Demo Inc",
        location="Berlin",
        description="Build APIs.",
        job_url="https://remotive.com/remote-jobs/demo/1",
        canonical_url="https://remotive.com/remote-jobs/demo/1",
        source="ashby:demo",
        source_job_id="retired-id",
        is_active=True,
    )
    db.add(shared)
    db.commit()

    with httpx.Client(
        transport=httpx.MockTransport(ashby_handler)
    ) as client:
        report = run_refresh(
            db,
            specs=[SourceSpec("ashby", "demo", "Demo Inc")],
            client=client,
        )

    db.refresh(shared)

    assert report.deactivated == 0
    assert shared.is_active is True


def test_run_refresh_leaves_roles_of_a_failed_source_alone(db):
    orphan = Job(
        title="Platform Engineer",
        company_name="Missing Inc",
        description="Kept until the board answers again.",
        job_url="https://jobs.ashbyhq.com/missing/1",
        canonical_url="https://jobs.ashbyhq.com/missing/1",
        source="ashby:missing",
        source_job_id="missing-1",
        is_active=True,
    )
    db.add(orphan)
    db.commit()

    with httpx.Client(
        transport=httpx.MockTransport(ashby_handler)
    ) as client:
        report = run_refresh(
            db,
            specs=[SourceSpec("ashby", "missing", "Missing Inc")],
            client=client,
        )

    db.refresh(orphan)

    assert report.sources_ok == 0
    assert report.deactivated == 0
    assert orphan.is_active is True


def test_status_is_idle_before_any_run():
    refresh_module._current = None

    status = refresh_status()

    assert status["running"] is False
    assert status["created"] == 0
    assert status["failures"] == []
    assert status["sources_total"] == 0


def test_only_one_refresh_runs_at_a_time(monkeypatch):
    release = threading.Event()
    started = threading.Event()

    def fake_worker(report, max_per_source):
        started.set()
        release.wait(5)
        report.running = False
        report.finished_at = datetime.now(UTC)

    monkeypatch.setattr(refresh_module, "_worker", fake_worker)
    monkeypatch.setattr(refresh_module, "_thread", None)
    monkeypatch.setattr(refresh_module, "_current", None)
    monkeypatch.setattr(refresh_module, "_last_finished", None)

    try:
        first, reason, _ = refresh_module.start_refresh("manual")

        assert first is True
        assert reason == "started"
        assert started.wait(5)

        second, second_reason, status = refresh_module.start_refresh(
            "schedule"
        )

        assert second is False
        assert second_reason == "already_running"
        assert status["running"] is True

    finally:
        release.set()

        thread = refresh_module._thread

        if thread is not None:
            thread.join(5)

        refresh_module._thread = None
        refresh_module._current = None
        refresh_module._last_finished = None


def test_refresh_status_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/v1/jobs/refresh/status")

    assert response.status_code == 200

    body = response.json()

    assert body["running"] is False
    assert body["failures"] == []
    assert isinstance(body["enabled"], bool)


def test_refresh_endpoint_requires_an_account_or_dev_key():
    with TestClient(app) as client:
        response = client.post("/api/v1/jobs/refresh")

    assert response.status_code in {401, 403}

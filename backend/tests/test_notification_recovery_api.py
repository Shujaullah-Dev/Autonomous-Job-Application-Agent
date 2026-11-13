
"""Readiness and notification recovery API tests."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.application import Application
from app.models.candidate import CandidateProfile
from app.models.interview import Interview, InterviewNotification
from app.models.job import Job
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

UTC = timezone.utc  # noqa: UP017

HEADERS = {"X-Dev-Job-Key": "test-secret"}


def recovery_url(candidate_id):
    return (
        f"/api/v1/candidates/{candidate_id}"
        "/notification-recovery"
    )


@pytest.fixture
def recovery_client(monkeypatch):
    monkeypatch.setattr(
        settings, "app_env", "development"
    )
    monkeypatch.setattr(
        settings, "dev_job_write_key", "test-secret"
    )

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    candidate_id = uuid.uuid4()

    with Session(engine) as db:
        candidate = CandidateProfile(
            id=candidate_id,
            full_name="Day 21 API Tester",
            email="day21@example.test",
        )

        job = Job(
            title="Backend Developer",
            company_name="Test Company",
            description="Python API development",
            job_url="https://company.test/jobs/day21",
            source="greenhouse:testcompany",
            is_active=True,
        )

        db.add_all([candidate, job])
        db.flush()

        application = Application(
            candidate_id=candidate_id,
            job_id=job.id,
            workflow_id=uuid.uuid4(),
            job_title=job.title,
            company_name=job.company_name,
            job_url=job.job_url,
            status="interview",
            current_revision=1,
        )
        db.add(application)
        db.flush()

        now = datetime.now(UTC)

        interview = Interview(
            application_id=application.id,
            title="Recovery Test Interview",
            starts_at=now + timedelta(hours=2),
            ends_at=now + timedelta(hours=3),
            mode="video",
            status="scheduled",
            version=1,
        )
        db.add(interview)
        db.flush()

        # Deliberately simulate a reminder missed by the
        # Day 20 processor. This is SQLite test data only.
        notification = InterviewNotification(
            interview_id=interview.id,
            minutes_before=60,
            due_at=now - timedelta(minutes=1),
            state="scheduled",
        )
        db.add(notification)
        db.commit()

        notification_id = notification.id

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            yield client, candidate_id, notification_id, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_readiness_reports_connected(recovery_client):
    client, _, _, _ = recovery_client

    response = client.get(
        "/api/v1/ops/readiness",
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["database"] == "connected"


def test_preview_does_not_change_state(recovery_client):
    client, candidate_id, notification_id, engine = (
        recovery_client
    )

    response = client.get(
        recovery_url(candidate_id) + "/preview",
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["dry_run"] is True
    assert data["released"] == 1
    assert data["cancelled"] == 0
    assert data["run_id"] is None

    with Session(engine) as db:
        notification = db.get(
            InterviewNotification,
            notification_id,
        )
        assert notification.state == "scheduled"


def test_apply_recovers_missed_notification(recovery_client):
    client, candidate_id, notification_id, engine = (
        recovery_client
    )

    response = client.post(
        recovery_url(candidate_id) + "/apply",
        json={"confirm": True, "limit": 100},
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["dry_run"] is False
    assert data["released"] == 1
    assert data["cancelled"] == 0
    assert data["run_id"] is not None

    with Session(engine) as db:
        notification = db.get(
            InterviewNotification,
            notification_id,
        )

        assert notification.state == "available"
        assert notification.available_at is not None


def test_repeated_apply_is_idempotent(recovery_client):
    client, candidate_id, _, _ = recovery_client

    endpoint = recovery_url(candidate_id) + "/apply"
    body = {"confirm": True}

    first = client.post(
        endpoint,
        json=body,
        headers=HEADERS,
    )

    second = client.post(
        endpoint,
        json=body,
        headers=HEADERS,
    )

    assert first.status_code == 200
    assert second.status_code == 200

    assert first.json()["released"] == 1
    assert second.json()["released"] == 0
    assert second.json()["run_id"] is None


def test_recovery_history(recovery_client):
    client, candidate_id, _, _ = recovery_client

    client.post(
        recovery_url(candidate_id) + "/apply",
        json={"confirm": True},
        headers=HEADERS,
    )

    response = client.get(
        recovery_url(candidate_id) + "/runs",
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["released"] == 1


def test_missing_confirmation_is_rejected(recovery_client):
    client, candidate_id, _, _ = recovery_client

    response = client.post(
        recovery_url(candidate_id) + "/apply",
        json={"limit": 100},
        headers=HEADERS,
    )

    assert response.status_code == 422


def test_false_confirmation_is_rejected(recovery_client):
    client, candidate_id, _, _ = recovery_client

    response = client.post(
        recovery_url(candidate_id) + "/apply",
        json={"confirm": False},
        headers=HEADERS,
    )

    assert response.status_code == 422


def test_invalid_limit_is_rejected(recovery_client):
    client, candidate_id, _, _ = recovery_client

    response = client.get(
        recovery_url(candidate_id) + "/preview",
        params={"limit": 0},
        headers=HEADERS,
    )

    assert response.status_code == 422


def test_unknown_candidate_returns_404(recovery_client):
    client, _, _, _ = recovery_client

    response = client.get(
        recovery_url(uuid.uuid4()) + "/preview",
        headers=HEADERS,
    )

    assert response.status_code == 404


def test_development_key_required(recovery_client):
    client, candidate_id, _, _ = recovery_client

    response = client.get(
        recovery_url(candidate_id) + "/preview",
    )

    assert response.status_code == 403


def test_production_access_disabled(
    recovery_client,
    monkeypatch,
):
    client, candidate_id, _, _ = recovery_client

    monkeypatch.setattr(
        settings, "app_env", "production"
    )

    response = client.post(
        recovery_url(candidate_id) + "/apply",
        json={"confirm": True},
        headers=HEADERS,
    )

    assert response.status_code == 403


def test_readiness_failure_returns_503(
    recovery_client,
):
    client, _, _, _ = recovery_client

    # Override the DB dependency only for this request.
    broken = MagicMock()
    from sqlalchemy.exc import SQLAlchemyError

    broken.execute.side_effect = SQLAlchemyError(
        "Simulated database outage"
    )

    original_override = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = lambda: broken

    try:
        response = client.get(
            "/api/v1/ops/readiness",
            headers=HEADERS,
        )
    finally:
        app.dependency_overrides[get_db] = original_override

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Database is not ready"
    )

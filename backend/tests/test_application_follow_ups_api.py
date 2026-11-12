
"""Follow-up API integration tests."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.application_follow_up import ApplicationFollowUp
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.services.application_tracking import (
    change_application_status,
    create_tracked_application,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

UTC = timezone.utc  # noqa: UP017

HEADERS = {"X-Dev-Job-Key": "test-secret"}


def follow_up_url(candidate_id, application_id):
    return (
        f"/api/v1/candidates/{candidate_id}"
        f"/applications/{application_id}/follow-ups"
    )


def due_date(days=2):
    return (
        datetime.now(UTC) + timedelta(days=days)
    ).isoformat()


def payload(days=2):
    return {
        "kind": "status_check",
        "due_at": due_date(days),
        "note": "Check the employer application portal",
    }


@pytest.fixture
def follow_up_client(monkeypatch):
    monkeypatch.setattr(
        settings,
        "app_env",
        "development",
    )
    monkeypatch.setattr(
        settings,
        "dev_job_write_key",
        "test-secret",
    )

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)
    candidate_id = uuid.uuid4()

    with Session(engine) as db:
        db.add(
            CandidateProfile(
                id=candidate_id,
                full_name="API Follow-up Tester",
                email="followup-api@example.test",
            )
        )

        job = Job(
            title="Python Developer",
            company_name="Test Employer",
            description="Python backend development",
            job_url="https://company.test/jobs/day19",
            source="greenhouse:example",
            is_active=True,
        )

        db.add(job)
        db.commit()

        application = create_tracked_application(
            db,
            candidate_id=candidate_id,
            workflow_id=uuid.uuid4(),
            job_id=job.id,
            job_title=job.title,
            company_name=job.company_name,
            job_url=job.job_url,
            cover_letter="Dear Hiring Team, I am interested.",
            resume_snapshot={
                "candidate_name": "API Follow-up Tester",
                "candidate_email": "followup-api@example.test",
                "relevant_skills": ["Python"],
                "experiences": [],
                "educations": [],
            },
        )

        application_id = application.id

        change_application_status(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            new_status="ready",
            confirm_reviewed=True,
        )

        change_application_status(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            new_status="submitted",
            confirm_external_submission=True,
        )

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            yield client, candidate_id, application_id, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def create_reminder(client, candidate_id, application_id):
    response = client.post(
        follow_up_url(candidate_id, application_id),
        json=payload(),
        headers=HEADERS,
    )

    assert response.status_code == 201
    return response.json()


def test_scheduling_creates_pending_task(follow_up_client):
    client, candidate_id, application_id, _ = (
        follow_up_client
    )

    data = create_reminder(
        client, candidate_id, application_id
    )

    assert data["state"] == "pending"
    assert data["kind"] == "status_check"
    assert data["history"][0]["event_type"] == "created"


def test_application_follow_up_list(follow_up_client):
    client, candidate_id, application_id, _ = (
        follow_up_client
    )

    create_reminder(client, candidate_id, application_id)

    response = client.get(
        follow_up_url(candidate_id, application_id),
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert len(response.json()["items"]) == 1


def test_monitoring_summary(follow_up_client):
    client, candidate_id, application_id, _ = (
        follow_up_client
    )

    create_reminder(client, candidate_id, application_id)

    response = client.get(
        f"/api/v1/candidates/{candidate_id}"
        "/application-monitoring",
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_applications"] == 1
    assert data["applications_by_status"]["submitted"] == 1
    assert data["pending_follow_ups"] == 1
    assert data["due_next_7_days"] == 1
    assert data["overdue_follow_ups"] == 0


def test_next_seven_days_filter(follow_up_client):
    client, candidate_id, application_id, _ = (
        follow_up_client
    )

    create_reminder(client, candidate_id, application_id)

    response = client.get(
        f"/api/v1/candidates/{candidate_id}/follow-ups",
        params={"window": "next_7_days"},
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_completion_records_history(follow_up_client):
    client, candidate_id, application_id, _ = (
        follow_up_client
    )

    task = create_reminder(
        client, candidate_id, application_id
    )

    response = client.post(
        follow_up_url(candidate_id, application_id)
        + f"/{task['id']}/resolve",
        json={
            "action": "complete",
            "resolution_note": (
                "Checked status manually; still pending"
            ),
        },
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["state"] == "completed"
    assert data["resolved_at"] is not None
    assert [item["event_type"] for item in data["history"]] == [
        "created",
        "completed",
    ]


def test_double_resolution_rejected(follow_up_client):
    client, candidate_id, application_id, _ = (
        follow_up_client
    )

    task = create_reminder(
        client, candidate_id, application_id
    )

    endpoint = (
        follow_up_url(candidate_id, application_id)
        + f"/{task['id']}/resolve"
    )

    first = client.post(
        endpoint,
        json={"action": "dismiss"},
        headers=HEADERS,
    )

    second = client.post(
        endpoint,
        json={"action": "complete"},
        headers=HEADERS,
    )

    assert first.status_code == 200
    assert second.status_code == 409


def test_duplicate_schedule_rejected(follow_up_client):
    client, candidate_id, application_id, _ = (
        follow_up_client
    )

    endpoint = follow_up_url(
        candidate_id, application_id
    )

    request_body = payload()

    first = client.post(
        endpoint,
        json=request_body,
        headers=HEADERS,
    )

    second = client.post(
        endpoint,
        json=request_body,
        headers=HEADERS,
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_missing_timezone_rejected(follow_up_client):
    client, candidate_id, application_id, _ = (
        follow_up_client
    )

    response = client.post(
        follow_up_url(candidate_id, application_id),
        json={
            "kind": "status_check",
            "due_at": "2026-12-01T09:00:00",
        },
        headers=HEADERS,
    )

    assert response.status_code == 422


def test_terminal_application_auto_closes_task(
    follow_up_client,
):
    client, candidate_id, application_id, engine = (
        follow_up_client
    )

    task = create_reminder(
        client, candidate_id, application_id
    )

    with Session(engine) as db:
        change_application_status(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            new_status="rejected",
        )

    response = client.get(
        f"/api/v1/candidates/{candidate_id}/follow-ups",
        params={"state": "dismissed"},
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1

    with Session(engine) as db:
        follow_up = db.get(
            ApplicationFollowUp,
            uuid.UUID(task["id"]),
        )

        assert follow_up.state == "dismissed"


def test_other_candidate_cannot_resolve(
    follow_up_client,
):
    client, candidate_id, application_id, _ = (
        follow_up_client
    )

    task = create_reminder(
        client, candidate_id, application_id
    )

    response = client.post(
        follow_up_url(
            uuid.uuid4(),
            application_id,
        ) + f"/{task['id']}/resolve",
        json={"action": "complete"},
        headers=HEADERS,
    )

    assert response.status_code == 404


def test_development_key_required(follow_up_client):
    client, candidate_id, application_id, _ = (
        follow_up_client
    )

    response = client.post(
        follow_up_url(candidate_id, application_id),
        json=payload(),
    )

    assert response.status_code == 403


def test_production_access_disabled(
    follow_up_client,
    monkeypatch,
):
    client, candidate_id, _, _ = follow_up_client

    monkeypatch.setattr(
        settings,
        "app_env",
        "production",
    )

    response = client.get(
        f"/api/v1/candidates/{candidate_id}"
        "/application-monitoring",
        headers=HEADERS,
    )

    assert response.status_code == 403

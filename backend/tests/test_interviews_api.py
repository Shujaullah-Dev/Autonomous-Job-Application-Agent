"""FastAPI interview and notification integration tests."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.application import Application
from app.models.candidate import CandidateProfile
from app.models.interview import InterviewNotification
from app.models.job import Job
from app.services.application_tracking import (
    change_application_status,
    create_tracked_application,
)
from app.services.interview_calendar import escape_ical, fold_line
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

UTC = timezone.utc  # noqa: UP017

HEADERS = {"X-Dev-Job-Key": "test-secret"}


def interview_url(candidate_id, application_id):
    return (
        f"/api/v1/candidates/{candidate_id}"
        f"/applications/{application_id}/interviews"
    )


def candidate_url(candidate_id):
    return f"/api/v1/candidates/{candidate_id}"


def request_body():
    start = datetime.now(UTC) + timedelta(days=2)
    return {
        "title": "Technical Interview",
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=1)).isoformat(),
        "mode": "video",
        "location_or_link": "https://meet.example.org/abc",
        "notes": "Discuss Python and backend engineering",
        "reminder_minutes": [1440, 60],
    }


@pytest.fixture
def interview_client(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
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
        db.add(
            CandidateProfile(
                id=candidate_id,
                full_name="Interview API Tester",
                email="interview-api@example.test",
            )
        )

        job = Job(
            title="Python Backend Developer",
            company_name="Example Employer",
            description="Python and FastAPI",
            job_url="https://company.test/jobs/day20",
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
                "candidate_name": "Interview API Tester",
                "candidate_email": "interview-api@example.test",
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
        change_application_status(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            new_status="interview",
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


def create_event(client, candidate_id, application_id):
    response = client.post(
        interview_url(candidate_id, application_id),
        json=request_body(),
        headers=HEADERS,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_interview(interview_client):
    client, candidate_id, application_id, _ = interview_client
    result = create_event(client, candidate_id, application_id)

    assert result["status"] == "scheduled"
    assert result["version"] == 1
    assert len(result["reminders"]) == 2


def test_interview_list(interview_client):
    client, candidate_id, application_id, _ = interview_client
    create_event(client, candidate_id, application_id)

    response = client.get(
        candidate_url(candidate_id) + "/interviews",
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_naive_time_rejected(interview_client):
    client, candidate_id, application_id, _ = interview_client
    body = request_body()
    body["starts_at"] = "2030-01-01T10:00:00"

    response = client.post(
        interview_url(candidate_id, application_id),
        json=body,
        headers=HEADERS,
    )

    assert response.status_code == 422


def test_requires_interview_application_status(interview_client):
    client, candidate_id, application_id, engine = interview_client

    with Session(engine) as db:
        application = db.get(Application, application_id)
        application.status = "submitted"
        db.commit()

    response = client.post(
        interview_url(candidate_id, application_id),
        json=request_body(),
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_reschedule_and_reject_stale_version(interview_client):
    client, candidate_id, application_id, _ = interview_client
    interview = create_event(client, candidate_id, application_id)

    start = datetime.now(UTC) + timedelta(days=4)
    endpoint = (
        candidate_url(candidate_id)
        + f"/interviews/{interview['id']}"
    )

    payload = {
        "expected_version": 1,
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(hours=1)).isoformat(),
        "reminder_minutes": [60],
    }

    response = client.patch(
        endpoint, json=payload, headers=HEADERS
    )

    assert response.status_code == 200
    assert response.json()["version"] == 2

    stale = client.patch(
        endpoint, json=payload, headers=HEADERS
    )
    assert stale.status_code == 409


def test_overlapping_interview_rejected(interview_client):
    client, candidate_id, application_id, _ = interview_client
    original_body = request_body()

    first = client.post(
        interview_url(candidate_id, application_id),
        json=original_body,
        headers=HEADERS,
    )
    assert first.status_code == 201

    start = datetime.fromisoformat(
        original_body["starts_at"]
    ) + timedelta(minutes=30)

    second_body = request_body()
    second_body["starts_at"] = start.isoformat()
    second_body["ends_at"] = (
        start + timedelta(hours=1)
    ).isoformat()

    second = client.post(
        interview_url(candidate_id, application_id),
        json=second_body,
        headers=HEADERS,
    )

    assert second.status_code == 409


def test_calendar_download(interview_client):
    client, candidate_id, application_id, _ = interview_client
    interview = create_event(client, candidate_id, application_id)

    response = client.get(
        candidate_url(candidate_id)
        + f"/interviews/{interview['id']}/calendar.ics",
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert "text/calendar" in response.headers["content-type"]
    assert "BEGIN:VCALENDAR\r\n" in response.text
    assert "BEGIN:VEVENT\r\n" in response.text
    assert f"UID:{interview['id']}@" in response.text
    assert "DTSTART:" in response.text
    assert "END:VCALENDAR" in response.text


def test_ical_escaping_and_utf8_folding():
    text = "Interview\nBEGIN:VEVENT;details"
    escaped = escape_ical(text)

    assert "\\nBEGIN:VEVENT" in escaped
    assert "\\;" in escaped

    folded = fold_line(
        "SUMMARY:" + "Résumé " * 30
    )

    assert all(
        len(line.encode("utf-8")) <= 75
        for line in folded.split("\r\n")
    )


def test_refresh_and_read_notification(interview_client):
    client, candidate_id, application_id, engine = interview_client
    interview = create_event(client, candidate_id, application_id)

    with Session(engine) as db:
        reminder = db.scalar(
            select(InterviewNotification).where(
                InterviewNotification.interview_id
                == uuid.UUID(interview["id"]),
                InterviewNotification.minutes_before == 60,
            )
        )

        # Simulate an already-due reminder in the test database.
        reminder.due_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()

    prefix = candidate_url(candidate_id)

    refreshed = client.post(
        prefix + "/interview-notifications/refresh",
        headers=HEADERS,
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["released"] == 1

    inbox = client.get(
        prefix + "/interview-notifications",
        headers=HEADERS,
    )
    assert inbox.status_code == 200
    assert inbox.json()["total"] == 1

    notification_id = inbox.json()["items"][0]["id"]

    read = client.post(
        prefix
        + f"/interview-notifications/{notification_id}/read",
        headers=HEADERS,
    )
    assert read.status_code == 200
    assert read.json()["state"] == "read"

    empty = client.get(
        prefix + "/interview-notifications",
        headers=HEADERS,
    )
    assert empty.json()["total"] == 0


def test_cancel_stops_reminders(interview_client):
    client, candidate_id, application_id, _ = interview_client
    interview = create_event(client, candidate_id, application_id)

    response = client.post(
        candidate_url(candidate_id)
        + f"/interviews/{interview['id']}/action",
        json={"action": "cancel", "expected_version": 1},
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert all(
        reminder["state"] == "cancelled"
        for reminder in response.json()["reminders"]
    )


def test_cross_candidate_access_rejected(interview_client):
    client, candidate_id, application_id, _ = interview_client
    interview = create_event(client, candidate_id, application_id)

    response = client.get(
        candidate_url(uuid.uuid4())
        + f"/interviews/{interview['id']}",
        headers=HEADERS,
    )

    assert response.status_code == 404


def test_development_key_required(interview_client):
    client, candidate_id, _, _ = interview_client

    response = client.get(
        candidate_url(candidate_id) + "/interviews"
    )

    assert response.status_code == 403


def test_production_access_disabled(interview_client, monkeypatch):
    client, candidate_id, _, _ = interview_client

    monkeypatch.setattr(settings, "app_env", "production")

    response = client.get(
        candidate_url(candidate_id) + "/interviews",
        headers=HEADERS,
    )

    assert response.status_code == 403
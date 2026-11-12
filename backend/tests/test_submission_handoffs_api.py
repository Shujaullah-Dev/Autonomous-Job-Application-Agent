"""Manual handoff API integration tests."""

import uuid

import pytest
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.application import Application
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.models.submission_handoff import SubmissionHandoff
from app.services.application_tracking import (
    change_application_status,
    create_tracked_application,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

HEADERS = {"X-Dev-Job-Key": "test-secret"}


def url(candidate_id, application_id):
    return (
        f"/api/v1/candidates/{candidate_id}"
        f"/applications/{application_id}"
    )


def confirmation(revision=1):
    return {
        "expected_revision": revision,
        "confirm_reviewed": True,
        "confirm_manual_handoff": True,
    }


@pytest.fixture
def handoff_client(monkeypatch):
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
        candidate = CandidateProfile(
            id=candidate_id,
            full_name="Alex Morgan",
            email="handoff@example.test",
        )

        job = Job(
            title="Python Backend Developer",
            company_name="Acme",
            description="Build Python and FastAPI services.",
            job_url="https://jobs.lever.co/acme/job123",
            source="lever:acme",
            work_mode=None,
            is_active=True,
        )

        db.add_all([candidate, job])
        db.commit()

        job_id = job.id

        application = create_tracked_application(
            db,
            candidate_id=candidate_id,
            workflow_id=uuid.uuid4(),
            job_id=job_id,
            job_title=job.title,
            company_name=job.company_name,
            job_url=job.job_url,
            cover_letter=(
                "Dear Hiring Team, I am interested "
                "in the Python Backend Developer role."
            ),
            resume_snapshot={
                "candidate_name": "Alex Morgan",
                "candidate_email": "handoff@example.test",
                "relevant_skills": ["Python", "FastAPI"],
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

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            yield (
                client,
                candidate_id,
                application_id,
                job_id,
                engine,
            )
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_preflight_passes_for_ready_application(handoff_client):
    client, candidate_id, application_id, _, _ = handoff_client

    response = client.get(
        url(candidate_id, application_id)
        + "/submission-preflight",
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["application_status"] == "ready"
    assert data["can_handoff"] is True
    assert data["provider_hint"] == "lever"
    assert data["revision_number"] == 1
    assert data["destination_url"] is not None


def test_handoff_creates_one_record(handoff_client):
    client, candidate_id, application_id, _, engine = (
        handoff_client
    )

    response = client.post(
        url(candidate_id, application_id)
        + "/manual-handoff",
        json=confirmation(),
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "prepared"
    assert data["newly_created"] is True
    assert "No external page was opened" in data["message"]

    with Session(engine) as db:
        count = db.scalar(
            select(func.count(SubmissionHandoff.id))
        )
        assert count == 1


def test_duplicate_handoff_is_idempotent(handoff_client):
    client, candidate_id, application_id, _, engine = (
        handoff_client
    )

    endpoint = (
        url(candidate_id, application_id)
        + "/manual-handoff"
    )

    first = client.post(
        endpoint,
        json=confirmation(),
        headers=HEADERS,
    )

    second = client.post(
        endpoint,
        json=confirmation(),
        headers=HEADERS,
    )

    assert first.status_code == 200
    assert second.status_code == 200

    assert first.json()["handoff_id"] == (
        second.json()["handoff_id"]
    )
    assert second.json()["newly_created"] is False

    with Session(engine) as db:
        count = db.scalar(
            select(func.count(SubmissionHandoff.id))
        )
        assert count == 1


def test_handoff_does_not_mark_submitted(handoff_client):
    client, candidate_id, application_id, _, engine = (
        handoff_client
    )

    response = client.post(
        url(candidate_id, application_id)
        + "/manual-handoff",
        json=confirmation(),
        headers=HEADERS,
    )

    assert response.status_code == 200

    with Session(engine) as db:
        application = db.get(
            Application,
            application_id,
        )

        assert application.status == "ready"
        assert application.submitted_at is None


def test_saved_handoff_can_be_read(handoff_client):
    client, candidate_id, application_id, _, _ = (
        handoff_client
    )

    endpoint = (
        url(candidate_id, application_id)
        + "/manual-handoff"
    )

    created = client.post(
        endpoint,
        json=confirmation(),
        headers=HEADERS,
    )

    retrieved = client.get(
        endpoint,
        headers=HEADERS,
    )

    assert retrieved.status_code == 200
    assert retrieved.json()["handoff_id"] == (
        created.json()["handoff_id"]
    )


def test_unprepared_handoff_returns_404(handoff_client):
    client, candidate_id, application_id, _, _ = (
        handoff_client
    )

    response = client.get(
        url(candidate_id, application_id)
        + "/manual-handoff",
        headers=HEADERS,
    )

    assert response.status_code == 404


def test_stale_revision_is_rejected(handoff_client):
    client, candidate_id, application_id, _, _ = (
        handoff_client
    )

    response = client.post(
        url(candidate_id, application_id)
        + "/manual-handoff",
        json=confirmation(revision=99),
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_missing_confirmation_is_rejected(handoff_client):
    client, candidate_id, application_id, _, _ = (
        handoff_client
    )

    response = client.post(
        url(candidate_id, application_id)
        + "/manual-handoff",
        json={
            "expected_revision": 1,
            "confirm_reviewed": True,
            "confirm_manual_handoff": False,
        },
        headers=HEADERS,
    )

    assert response.status_code == 422


def test_draft_status_blocks_handoff(handoff_client):
    client, candidate_id, application_id, _, engine = (
        handoff_client
    )

    with Session(engine) as db:
        application = db.get(Application, application_id)
        application.status = "draft"
        db.commit()

    response = client.post(
        url(candidate_id, application_id)
        + "/manual-handoff",
        json=confirmation(),
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_inactive_job_blocks_handoff(handoff_client):
    client, candidate_id, application_id, job_id, engine = (
        handoff_client
    )

    with Session(engine) as db:
        job = db.get(Job, job_id)
        job.is_active = False
        db.commit()

    response = client.post(
        url(candidate_id, application_id)
        + "/manual-handoff",
        json=confirmation(),
        headers=HEADERS,
    )

    assert response.status_code == 409

    with Session(engine) as db:
        count = db.scalar(
            select(func.count(SubmissionHandoff.id))
        )
        assert count == 0


def test_changed_job_blocks_handoff(handoff_client):
    client, candidate_id, application_id, job_id, engine = (
        handoff_client
    )

    with Session(engine) as db:
        job = db.get(Job, job_id)
        job.title = "New Job Title"
        db.commit()

    response = client.post(
        url(candidate_id, application_id)
        + "/manual-handoff",
        json=confirmation(),
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_another_candidate_cannot_access_handoff(
    handoff_client,
):
    client, _, application_id, _, _ = handoff_client

    response = client.get(
        url(uuid.uuid4(), application_id)
        + "/submission-preflight",
        headers=HEADERS,
    )

    assert response.status_code == 404


def test_development_key_is_required(handoff_client):
    client, candidate_id, application_id, _, _ = (
        handoff_client
    )

    response = client.get(
        url(candidate_id, application_id)
        + "/submission-preflight",
    )

    assert response.status_code == 403


def test_production_access_is_disabled(
    handoff_client,
    monkeypatch,
):
    client, candidate_id, application_id, _, _ = (
        handoff_client
    )

    monkeypatch.setattr(
        settings,
        "app_env",
        "production",
    )

    response = client.post(
        url(candidate_id, application_id)
        + "/manual-handoff",
        json=confirmation(),
        headers=HEADERS,
    )

    assert response.status_code == 403
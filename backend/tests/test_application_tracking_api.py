
"""Application tracking API integration tests."""

import uuid

import app.api.routes.job_workflows as workflow_routes
import pytest
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.application import Application
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.models.skill import CandidateSkill
from app.services.job_workflow_graph import build_job_workflow
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

HEADERS = {"X-Dev-Job-Key": "test-secret"}


def workflow_url(candidate_id):
    return f"/api/v1/candidates/{candidate_id}/workflows"


def application_url(candidate_id, application_id):
    return (
        f"/api/v1/candidates/{candidate_id}"
        f"/applications/{application_id}"
    )


@pytest.fixture
def tracking_client(monkeypatch):
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
                full_name="Alex Morgan",
                email="day17@example.test",
                location="Islamabad",
                years_experience=0,
            )
        )

        for name in ["Python", "FastAPI"]:
            db.add(
                CandidateSkill(
                    candidate_id=candidate_id,
                    name=name,
                    proficiency_level="unassessed",
                )
            )

        job = Job(
            title="Python Backend Developer",
            company_name="Example Technologies",
            description="Build Python and FastAPI APIs.",
            job_url="https://company.test/jobs/day17",
            source="greenhouse:example",
            location="Islamabad, Pakistan",
            is_active=True,
        )

        db.add(job)
        db.commit()

        job_id = job.id

    def provider(state):
        return [
            {
                "job_id": job_id,
                "title": "Python Backend Developer",
                "score": 78.0,
                "work_mode": None,
                "reasons": [
                    "Python and FastAPI match the profile."
                ],
                "cautions": [
                    "Hiring eligibility is unverified."
                ],
            }
        ]

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db

    monkeypatch.setattr(
        workflow_routes,
        "_graph",
        build_job_workflow(provider),
    )

    try:
        with TestClient(app) as client:
            yield client, candidate_id, job_id, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def start_workflow(client, candidate_id):
    response = client.post(
        workflow_url(candidate_id),
        json={},
        headers=HEADERS,
    )

    assert response.status_code == 201
    return response.json()["workflow_id"]


def approve_workflow(
    client,
    candidate_id,
    workflow_id,
    job_id,
):
    response = client.post(
        f"{workflow_url(candidate_id)}/{workflow_id}/review",
        json={
            "decision": "approve",
            "approved_job_ids": [job_id],
        },
        headers=HEADERS,
    )

    assert response.status_code == 200


def create_record(client, candidate_id, job_id):
    workflow_id = start_workflow(
        client,
        candidate_id,
    )

    approve_workflow(
        client,
        candidate_id,
        workflow_id,
        job_id,
    )

    response = client.post(
        (
            f"{workflow_url(candidate_id)}/{workflow_id}"
            f"/tracked-applications/{job_id}"
        ),
        headers=HEADERS,
    )

    assert response.status_code == 201
    return response.json()


def test_create_persistent_application(tracking_client):
    client, candidate_id, job_id, engine = tracking_client

    data = create_record(
        client,
        candidate_id,
        job_id,
    )

    assert data["status"] == "draft"
    assert data["current_revision"] == 1
    assert len(data["revisions"]) == 1
    assert len(data["history"]) == 1

    with Session(engine) as db:
        assert db.get(
            Application,
            uuid.UUID(data["id"]),
        ) is not None


def test_list_and_read_application(tracking_client):
    client, candidate_id, job_id, _ = tracking_client
    created = create_record(client, candidate_id, job_id)

    listing = client.get(
        f"/api/v1/candidates/{candidate_id}/applications",
        headers=HEADERS,
    )

    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    detail = client.get(
        application_url(candidate_id, created["id"]),
        headers=HEADERS,
    )

    assert detail.status_code == 200
    assert detail.json()["id"] == created["id"]


def test_duplicate_application_rejected(tracking_client):
    client, candidate_id, job_id, _ = tracking_client

    first = create_record(client, candidate_id, job_id)

    response = client.post(
        (
            f"{workflow_url(candidate_id)}"
            f"/{first['workflow_id']}"
            f"/tracked-applications/{job_id}"
        ),
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_unapproved_workflow_rejected(tracking_client):
    client, candidate_id, job_id, _ = tracking_client

    workflow_id = start_workflow(client, candidate_id)

    response = client.post(
        (
            f"{workflow_url(candidate_id)}/{workflow_id}"
            f"/tracked-applications/{job_id}"
        ),
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_edit_creates_second_revision(tracking_client):
    client, candidate_id, job_id, _ = tracking_client
    created = create_record(client, candidate_id, job_id)

    response = client.patch(
        (
            application_url(candidate_id, created["id"])
            + "/draft"
        ),
        json={
            "expected_revision": 1,
            "cover_letter": (
                "Dear Hiring Team, I have reviewed this "
                "application and would like to be considered."
            ),
        },
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["current_revision"] == 2
    assert len(data["revisions"]) == 2
    assert data["latest_draft"]["source"] == (
        "candidate_edit"
    )


def test_stale_edit_rejected(tracking_client):
    client, candidate_id, job_id, _ = tracking_client
    created = create_record(client, candidate_id, job_id)

    response = client.patch(
        (
            application_url(candidate_id, created["id"])
            + "/draft"
        ),
        json={
            "expected_revision": 99,
            "cover_letter": (
                "This is a sufficiently long draft edit."
            ),
        },
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_ready_requires_review_confirmation(tracking_client):
    client, candidate_id, job_id, _ = tracking_client
    created = create_record(client, candidate_id, job_id)

    response = client.post(
        (
            application_url(candidate_id, created["id"])
            + "/status"
        ),
        json={"new_status": "ready"},
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_submitted_requires_external_confirmation(
    tracking_client,
):
    client, candidate_id, job_id, _ = tracking_client
    created = create_record(client, candidate_id, job_id)

    status_url = (
        application_url(candidate_id, created["id"])
        + "/status"
    )

    ready = client.post(
        status_url,
        json={
            "new_status": "ready",
            "confirm_reviewed": True,
        },
        headers=HEADERS,
    )

    assert ready.status_code == 200

    invalid = client.post(
        status_url,
        json={"new_status": "submitted"},
        headers=HEADERS,
    )

    assert invalid.status_code == 409

    submitted = client.post(
        status_url,
        json={
            "new_status": "submitted",
            "confirm_external_submission": True,
            "note": "Reported external submission",
        },
        headers=HEADERS,
    )

    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"
    assert submitted.json()["submitted_at"] is not None


def test_invalid_status_transition(tracking_client):
    client, candidate_id, job_id, _ = tracking_client
    created = create_record(client, candidate_id, job_id)

    response = client.post(
        (
            application_url(candidate_id, created["id"])
            + "/status"
        ),
        json={"new_status": "offered"},
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_history_survives_graph_memory_reset(
    tracking_client,
    monkeypatch,
):
    client, candidate_id, job_id, _ = tracking_client
    created = create_record(client, candidate_id, job_id)

    # Simulates losing the Day 15 in-memory graph state.
    monkeypatch.setattr(
        workflow_routes,
        "_graph",
        build_job_workflow(lambda state: []),
    )

    response = client.get(
        application_url(candidate_id, created["id"]),
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert len(response.json()["history"]) == 1
    assert len(response.json()["revisions"]) == 1


def test_other_candidate_cannot_read_application(
    tracking_client,
):
    client, candidate_id, job_id, _ = tracking_client
    created = create_record(client, candidate_id, job_id)

    response = client.get(
        application_url(
            uuid.uuid4(),
            created["id"],
        ),
        headers=HEADERS,
    )

    assert response.status_code == 404


def test_development_key_required(tracking_client):
    client, candidate_id, _, _ = tracking_client

    response = client.get(
        f"/api/v1/candidates/{candidate_id}/applications"
    )

    assert response.status_code == 403


def test_production_access_disabled(
    tracking_client,
    monkeypatch,
):
    client, candidate_id, _, _ = tracking_client

    monkeypatch.setattr(
        settings,
        "app_env",
        "production",
    )

    response = client.get(
        f"/api/v1/candidates/{candidate_id}/applications",
        headers=HEADERS,
    )

    assert response.status_code == 403


def test_invalid_revision_payload(tracking_client):
    client, candidate_id, job_id, _ = tracking_client
    created = create_record(client, candidate_id, job_id)

    response = client.patch(
        (
            application_url(candidate_id, created["id"])
            + "/draft"
        ),
        json={
            "expected_revision": 0,
            "cover_letter": "Too short",
        },
        headers=HEADERS,
    )

    assert response.status_code == 422

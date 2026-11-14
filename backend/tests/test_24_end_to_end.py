
"""end-to-end approval-to-handoff regression tests."""

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
from app.services.application_tracking import create_tracked_application
from app.services.job_workflow_graph import build_job_workflow
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

HEADERS = {"X-Dev-Job-Key": "day24-test-key"}

@pytest.fixture
def e2e_client(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(
        settings, "dev_job_write_key", "day24-test-key"
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
                full_name="Day 24 Candidate",
                email="day24@example.test",
                location="Islamabad",
                years_experience=2,
            )
        )

        for name in ("Python", "FastAPI"):
            db.add(
                CandidateSkill(
                    candidate_id=candidate_id,
                    name=name,
                    proficiency_level="intermediate",
                )
            )

        job = Job(
            title="Python Backend Developer",
            company_name="Acme Engineering",
            description=(
                "Build Python and FastAPI applications."
            ),
            job_url="https://jobs.lever.co/acme/role123",
            source="lever:acme",
            location="Islamabad, Pakistan",
            work_mode="hybrid",
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
                "score": 82.0,
                "work_mode": "hybrid",
                "reasons": ["Python and FastAPI are recorded."],
                "cautions": [
                    "Country eligibility is not verified."
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
            yield (
                client,
                candidate_id,
                job_id,
                engine,
            )
    finally:
        app.dependency_overrides.clear()
        engine.dispose()

def workflow_url(candidate_id):
    return f"/api/v1/candidates/{candidate_id}/workflows"

def application_url(candidate_id, application_id):
    return (
        f"/api/v1/candidates/{candidate_id}"
        f"/applications/{application_id}"
    )

def test_complete_approval_to_handoff_flow(e2e_client):
    client, candidate_id, job_id, engine = e2e_client

    # 1. Begin the Day 15 shortlist workflow.
    start = client.post(
        workflow_url(candidate_id),
        json={},
        headers=HEADERS,
    )
    assert start.status_code == 201, start.text

    workflow_id = start.json()["workflow_id"]
    assert start.json()["status"] == "pending_review"

    # 2. Approve the recommended job.
    review = client.post(
        f"{workflow_url(candidate_id)}/{workflow_id}/review",
        json={
            "decision": "approve",
            "approved_job_ids": [job_id],
        },
        headers=HEADERS,
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "approved"

    # 3. Persist a deterministic application draft.
    tracked = client.post(
        (
            f"{workflow_url(candidate_id)}/{workflow_id}"
            f"/tracked-applications/{job_id}"
        ),
        headers=HEADERS,
    )
    assert tracked.status_code == 201, tracked.text

    data = tracked.json()
    application_id = data["id"]

    assert data["status"] == "draft"
    assert data["current_revision"] == 1
    assert len(data["revisions"]) == 1

    # 4. Check preflight before reviewing the draft.
    prefix = application_url(
        candidate_id, application_id
    )

    preflight = client.get(
        prefix + "/submission-preflight",
        headers=HEADERS,
    )
    assert preflight.status_code == 200
    assert preflight.json()["can_handoff"] is False

    # 5. Confirm review of the saved draft.
    ready = client.post(
        prefix + "/status",
        json={
            "new_status": "ready",
            "confirm_reviewed": True,
            "note": "Synthetic test draft reviewed",
        },
        headers=HEADERS,
    )
    assert ready.status_code == 200, ready.text
    assert ready.json()["status"] == "ready"

    # 6. Run preflight again.
    preflight = client.get(
        prefix + "/submission-preflight",
        headers=HEADERS,
    )
    assert preflight.status_code == 200

    report = preflight.json()
    assert report["can_handoff"] is True
    assert all(
        item["passed"]
        for item in report["checks"]
    )

    # 7. Prepare a manual handoff.
    handoff_body = {
        "expected_revision": 1,
        "confirm_reviewed": True,
        "confirm_manual_handoff": True,
    }

    handoff = client.post(
        prefix + "/manual-handoff",
        json=handoff_body,
        headers=HEADERS,
    )
    assert handoff.status_code == 200, handoff.text

    first = handoff.json()
    assert first["status"] == "prepared"
    assert first["newly_created"] is True

    # 8. Repeat handoff to verify idempotency.
    repeated = client.post(
        prefix + "/manual-handoff",
        json=handoff_body,
        headers=HEADERS,
    )
    assert repeated.status_code == 200

    second = repeated.json()
    assert second["handoff_id"] == first["handoff_id"]
    assert second["newly_created"] is False

    # 9. Ensure no false submission occurred.
    detail = client.get(prefix, headers=HEADERS)
    assert detail.status_code == 200
    assert detail.json()["status"] == "ready"
    assert detail.json()["submitted_at"] is None

    with Session(engine) as db:
        application = db.get(
            Application,
            uuid.UUID(application_id),
        )

        assert application.status == "ready"
        assert application.submitted_at is None


def test_handoff_cannot_be_accessed_through_other_candidate(
    e2e_client,
):
    client, candidate_id, job_id, engine = e2e_client

    with Session(engine) as db:
        application = create_tracked_application(
            db,
            candidate_id=candidate_id,
            workflow_id=uuid.uuid4(),
            job_id=job_id,
            job_title="Python Backend Developer",
            company_name="Acme Engineering",
            job_url="https://jobs.lever.co/acme/role123",
            cover_letter=(
                "Dear Hiring Team, I am interested in "
                "the advertised backend development role."
            ),
            resume_snapshot={
                "candidate_name": "Day 24 Candidate",
                "candidate_email": "day24@example.test",
                "relevant_skills": ["Python", "FastAPI"],
                "experiences": [],
                "educations": [],
            },
        )

        application_id = application.id

    # Correct candidate ID can access the application's
    # preflight report.
    allowed = client.get(
        application_url(candidate_id, application_id)
        + "/submission-preflight",
        headers=HEADERS,
    )

    assert allowed.status_code == 200

    # A different candidate ID cannot access that same record.
    blocked = client.get(
        application_url(uuid.uuid4(), application_id)
        + "/submission-preflight",
        headers=HEADERS,
    )

    assert blocked.status_code == 404


def test_protected_workflow_requires_development_key(
    e2e_client,
):
    client, candidate_id, _, _ = e2e_client

    response = client.post(
        workflow_url(candidate_id),
        json={},
    )

    assert response.status_code == 403
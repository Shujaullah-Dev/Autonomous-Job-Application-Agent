
"""Day 16 application materials API integration tests."""

import uuid
from datetime import date

import app.api.routes.application_materials as draft_routes
import app.api.routes.job_workflows as workflow_routes
import pytest
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.candidate import CandidateProfile
from app.models.education import Education
from app.models.experience import WorkExperience
from app.models.job import Job
from app.models.skill import CandidateSkill
from app.services.job_workflow_graph import build_job_workflow
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

HEADERS = {"X-Dev-Job-Key": "test-secret"}


def workflow_url(candidate_id):
    return f"/api/v1/candidates/{candidate_id}/workflows"


def draft_url(candidate_id, workflow_id, job_id):
    return (
        f"{workflow_url(candidate_id)}/{workflow_id}"
        f"/application-drafts/{job_id}"
    )


@pytest.fixture
def draft_client(monkeypatch):
    monkeypatch.setattr(
        settings, "app_env", "development"
    )
    monkeypatch.setattr(
        settings, "dev_job_write_key", "test-secret"
    )
    monkeypatch.setattr(
        settings,
        "application_drafts_ai_enabled",
        False,
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
                email="alex@example.test",
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

        db.add(
            WorkExperience(
                candidate_id=candidate_id,
                company_name="Example Company",
                job_title="AI Intern",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 8, 1),
                is_current=False,
            )
        )

        db.add(
            Education(
                candidate_id=candidate_id,
                institution="Example University",
                degree="BS Artificial Intelligence",
                start_date=date(2022, 1, 1),
                end_date=date(2026, 1, 1),
            )
        )

        job = Job(
            title="Python Backend Developer",
            company_name="Example Technologies",
            description=(
                "Build Python and FastAPI applications."
            ),
            job_url="https://company.test/jobs/backend",
            source="greenhouse:example",
            location="Islamabad, Pakistan",
            work_mode=None,
            is_active=True,
        )

        db.add(job)
        db.commit()

        job_id = job.id

    def sample_provider(state):
        return [
            {
                "job_id": job_id,
                "title": "Python Backend Developer",
                "score": 78.5,
                "work_mode": None,
                "reasons": [
                    "Python and FastAPI match the profile."
                ],
                "cautions": [
                    "Work authorization is unverified."
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
        build_job_workflow(sample_provider),
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


def approve_workflow(client, candidate_id, workflow_id, job_id):
    response = client.post(
        f"{workflow_url(candidate_id)}/{workflow_id}/review",
        json={
            "decision": "approve",
            "approved_job_ids": [job_id],
        },
        headers=HEADERS,
    )

    assert response.status_code == 200
    return response.json()


def test_draft_generated_for_approved_job(draft_client):
    client, candidate_id, job_id, _ = draft_client

    workflow_id = start_workflow(client, candidate_id)
    approve_workflow(client, candidate_id, workflow_id, job_id)

    response = client.post(
        draft_url(candidate_id, workflow_id, job_id),
        json={"use_ai": False},
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "draft"
    assert data["generation_mode"] == "deterministic"
    assert data["llm_used"] is False

    assert "Alex Morgan" in data["cover_letter"]
    assert "Python Backend Developer" in data["cover_letter"]

    assert data["tailored_resume"]["relevant_skills"] == [
        "FastAPI",
        "Python",
    ]

    assert "No application" in data["message"]


def test_work_history_and_education_are_preserved(draft_client):
    client, candidate_id, job_id, _ = draft_client

    workflow_id = start_workflow(client, candidate_id)
    approve_workflow(client, candidate_id, workflow_id, job_id)

    response = client.post(
        draft_url(candidate_id, workflow_id, job_id),
        json={},
        headers=HEADERS,
    )

    resume = response.json()["tailored_resume"]

    assert any(
        "AI Intern" in item
        for item in resume["experiences"]
    )

    assert any(
        "BS Artificial Intelligence" in item
        for item in resume["educations"]
    )


def test_cannot_generate_without_approval(draft_client):
    client, candidate_id, job_id, _ = draft_client

    workflow_id = start_workflow(client, candidate_id)

    response = client.post(
        draft_url(candidate_id, workflow_id, job_id),
        json={},
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_rejected_workflow_cannot_generate(draft_client):
    client, candidate_id, job_id, _ = draft_client

    workflow_id = start_workflow(client, candidate_id)

    client.post(
        f"{workflow_url(candidate_id)}/{workflow_id}/review",
        json={
            "decision": "reject",
            "approved_job_ids": [],
        },
        headers=HEADERS,
    )

    response = client.post(
        draft_url(candidate_id, workflow_id, job_id),
        json={},
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_unapproved_job_id_is_rejected(draft_client):
    client, candidate_id, job_id, _ = draft_client

    workflow_id = start_workflow(client, candidate_id)
    approve_workflow(client, candidate_id, workflow_id, job_id)

    response = client.post(
        draft_url(candidate_id, workflow_id, 99999),
        json={},
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_inactive_job_is_rejected(draft_client):
    client, candidate_id, job_id, engine = draft_client

    workflow_id = start_workflow(client, candidate_id)
    approve_workflow(client, candidate_id, workflow_id, job_id)

    with Session(engine) as db:
        job = db.get(Job, job_id)
        job.is_active = False
        db.commit()

    response = client.post(
        draft_url(candidate_id, workflow_id, job_id),
        json={},
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_changed_job_title_requires_new_review(draft_client):
    client, candidate_id, job_id, engine = draft_client

    workflow_id = start_workflow(client, candidate_id)
    approve_workflow(client, candidate_id, workflow_id, job_id)

    with Session(engine) as db:
        job = db.get(Job, job_id)
        job.title = "Different Job Position"
        db.commit()

    response = client.post(
        draft_url(candidate_id, workflow_id, job_id),
        json={},
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_other_candidate_cannot_use_workflow(draft_client):
    client, candidate_id, job_id, _ = draft_client

    workflow_id = start_workflow(client, candidate_id)
    approve_workflow(client, candidate_id, workflow_id, job_id)

    response = client.post(
        draft_url(uuid.uuid4(), workflow_id, job_id),
        json={},
        headers=HEADERS,
    )

    assert response.status_code == 404


def test_ai_disabled_uses_fallback(draft_client):
    client, candidate_id, job_id, _ = draft_client

    workflow_id = start_workflow(client, candidate_id)
    approve_workflow(client, candidate_id, workflow_id, job_id)

    response = client.post(
        draft_url(candidate_id, workflow_id, job_id),
        json={"use_ai": True},
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["generation_mode"] == "fallback"
    assert data["llm_used"] is False
    assert data["warnings"]


def test_invalid_ai_response_uses_fallback(
    draft_client,
    monkeypatch,
):
    client, candidate_id, job_id, _ = draft_client

    workflow_id = start_workflow(client, candidate_id)
    approve_workflow(client, candidate_id, workflow_id, job_id)

    monkeypatch.setattr(
        settings,
        "application_drafts_ai_enabled",
        True,
    )
    monkeypatch.setattr(
        settings,
        "groq_api_key",
        "test-only-key",
    )

    fake_model = RunnableLambda(
        lambda prompt: AIMessage(
            content='{"invented_skill": "Rust"}'
        )
    )

    monkeypatch.setattr(
        draft_routes,
        "ChatGroq",
        lambda **kwargs: fake_model,
    )

    response = client.post(
        draft_url(candidate_id, workflow_id, job_id),
        json={"use_ai": True},
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["generation_mode"] == "fallback"
    assert data["llm_used"] is False
    assert "Rust" not in data["cover_letter"]


def test_development_key_required(draft_client):
    client, candidate_id, job_id, _ = draft_client

    workflow_id = start_workflow(client, candidate_id)
    approve_workflow(client, candidate_id, workflow_id, job_id)

    response = client.post(
        draft_url(candidate_id, workflow_id, job_id),
        json={},
    )

    assert response.status_code == 403


def test_production_access_disabled(
    draft_client,
    monkeypatch,
):
    client, candidate_id, job_id, _ = draft_client

    workflow_id = start_workflow(client, candidate_id)
    approve_workflow(client, candidate_id, workflow_id, job_id)

    monkeypatch.setattr(
        settings,
        "app_env",
        "production",
    )

    response = client.post(
        draft_url(candidate_id, workflow_id, job_id),
        json={},
        headers=HEADERS,
    )

    assert response.status_code == 403


def test_invalid_job_id_is_rejected(draft_client):
    client, candidate_id, _, _ = draft_client

    response = client.post(
        draft_url(candidate_id, uuid.uuid4(), 0),
        json={},
        headers=HEADERS,
    )

    assert response.status_code == 422
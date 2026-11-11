
"""Day 14 LangChain explanation API tests."""

import json
import uuid

import app.api.routes.job_explanations as explanation_routes
import pytest
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.models.skill import CandidateSkill
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

HEADERS = {"X-Dev-Job-Key": "test-secret"}


def endpoint(candidate_id, job_id):
    return (
        f"/api/v1/candidates/{candidate_id}"
        f"/recommendations/{job_id}/explanation"
    )


@pytest.fixture
def explanation_client(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(
        settings, "dev_job_write_key", "test-secret"
    )
    monkeypatch.setattr(
        settings, "langchain_explanations_enabled", False
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
                full_name="Test Candidate",
                email="day14@example.test",
                location="Islamabad",
                years_experience=0,
            )
        )

        db.add(
            CandidateSkill(
                candidate_id=candidate_id,
                name="Python",
                proficiency_level="unassessed",
            )
        )

        db.add(
            CandidateSkill(
                candidate_id=candidate_id,
                name="FastAPI",
                proficiency_level="unassessed",
            )
        )

        relevant = Job(
            title="Python Backend Developer",
            company_name="Test Employer",
            description="Build Python and FastAPI APIs.",
            job_url="https://careers.company.test/jobs/100",
            source="greenhouse:testemployer",
            location="Islamabad, Pakistan",
            is_active=True,
        )

        irrelevant = Job(
            title="Sales Representative",
            company_name="Test Employer",
            description="Customer outreach and presentations.",
            job_url="https://careers.company.test/jobs/101",
            source="greenhouse:testemployer",
            location="New York",
            is_active=True,
        )

        demo = Job(
            title="Demo Developer",
            company_name="Lever Demo",
            description="Python",
            job_url="https://jobs.lever.co/leverdemo/example",
            source="lever:leverdemo",
            is_active=True,
        )

        db.add_all([relevant, irrelevant, demo])
        db.commit()

        job_ids = {
            "relevant": relevant.id,
            "irrelevant": irrelevant.id,
            "demo": demo.id,
        }

    def override_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            yield client, candidate_id, job_ids, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_default_explanation_no_groq(explanation_client):
    client, candidate_id, job_ids, _ = explanation_client

    response = client.get(
        endpoint(candidate_id, job_ids["relevant"]),
        headers=HEADERS,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["scoring_mode"] == "rules"
    assert data["explanation_mode"] == "deterministic"
    assert data["llm_used"] is False
    assert data["model_name"] is None
    assert data["reasons"]
    assert data["cautions"]


def test_ai_disabled_uses_fallback(explanation_client):
    client, candidate_id, job_ids, _ = explanation_client

    response = client.get(
        endpoint(candidate_id, job_ids["relevant"]),
        params={"use_ai": True},
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()
    assert data["explanation_mode"] == "fallback"
    assert data["llm_used"] is False
    assert data["warnings"]


def test_langchain_uses_only_existing_reasons(
    explanation_client,
    monkeypatch,
):
    client, candidate_id, job_ids, _ = explanation_client

    baseline = client.get(
        endpoint(candidate_id, job_ids["relevant"]),
        headers=HEADERS,
    ).json()

    reason_count = len(baseline["reasons"])
    caution_count = len(baseline["cautions"])

    output = json.dumps(
        {
            "reason_order": list(
                reversed(range(reason_count))
            ),
            "caution_order": list(
                reversed(range(caution_count))
            ),
        }
    )

    fake = RunnableLambda(
        lambda prompt: AIMessage(content=output)
    )

    monkeypatch.setattr(
        settings, "langchain_explanations_enabled", True
    )
    monkeypatch.setattr(
        settings, "groq_api_key", "test-only-key"
    )
    monkeypatch.setattr(
        explanation_routes,
        "ChatGroq",
        lambda **kwargs: fake,
    )

    response = client.get(
        endpoint(candidate_id, job_ids["relevant"]),
        params={"use_ai": True},
        headers=HEADERS,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["explanation_mode"] == "langchain_groq"
    assert data["llm_used"] is True

    assert data["reasons"] == list(
        reversed(baseline["reasons"])
    )
    assert data["cautions"] == list(
        reversed(baseline["cautions"])
    )


def test_invalid_model_response_falls_back(
    explanation_client,
    monkeypatch,
):
    client, candidate_id, job_ids, _ = explanation_client

    monkeypatch.setattr(
        settings, "langchain_explanations_enabled", True
    )
    monkeypatch.setattr(
        settings, "groq_api_key", "test-only-key"
    )
    monkeypatch.setattr(
        explanation_routes,
        "ChatGroq",
        lambda **kwargs: RunnableLambda(
            lambda prompt: AIMessage(
                content='{"invented_skill": "Rust"}'
            )
        ),
    )

    response = client.get(
        endpoint(candidate_id, job_ids["relevant"]),
        params={"use_ai": True},
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["explanation_mode"] == "fallback"
    assert response.json()["llm_used"] is False


def test_unrelated_job_is_not_recommended(explanation_client):
    client, candidate_id, job_ids, _ = explanation_client

    response = client.get(
        endpoint(candidate_id, job_ids["irrelevant"]),
        headers=HEADERS,
    )

    assert response.status_code == 404


def test_demo_job_is_excluded(explanation_client):
    client, candidate_id, job_ids, _ = explanation_client

    response = client.get(
        endpoint(candidate_id, job_ids["demo"]),
        headers=HEADERS,
    )

    assert response.status_code == 404


def test_candidate_not_found(explanation_client):
    client, _, job_ids, _ = explanation_client

    response = client.get(
        endpoint(uuid.uuid4(), job_ids["relevant"]),
        headers=HEADERS,
    )

    assert response.status_code == 404


def test_incomplete_candidate_profile(explanation_client):
    client, _, job_ids, engine = explanation_client

    empty_candidate = uuid.uuid4()

    with Session(engine) as db:
        db.add(
            CandidateProfile(
                id=empty_candidate,
                full_name="Empty Profile",
                email="empty-day14@example.test",
            )
        )
        db.commit()

    response = client.get(
        endpoint(empty_candidate, job_ids["relevant"]),
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_development_key_required(explanation_client):
    client, candidate_id, job_ids, _ = explanation_client

    response = client.get(
        endpoint(candidate_id, job_ids["relevant"])
    )

    assert response.status_code == 403


def test_production_access_disabled(
    explanation_client,
    monkeypatch,
):
    client, candidate_id, job_ids, _ = explanation_client

    monkeypatch.setattr(settings, "app_env", "production")

    response = client.get(
        endpoint(candidate_id, job_ids["relevant"]),
        headers=HEADERS,
    )

    assert response.status_code == 403


def test_invalid_job_id_rejected(explanation_client):
    client, candidate_id, _, _ = explanation_client

    response = client.get(
        endpoint(candidate_id, 0),
        headers=HEADERS,
    )

    assert response.status_code == 422
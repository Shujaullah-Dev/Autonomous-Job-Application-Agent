
import uuid
from datetime import date

import app.api.routes.job_matches as matching_routes
import pytest
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.candidate import CandidateProfile
from app.models.experience import WorkExperience
from app.models.job import Job
from app.models.skill import CandidateSkill
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def client_and_ids(monkeypatch):
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
            full_name="Test Candidate",
            email="hybrid@example.com",
            location="Islamabad",
            years_experience=3,
            professional_summary="Builds backend APIs",
        )

        db.add(candidate)

        db.add(
            CandidateSkill(
                candidate_id=candidate_id,
                name="Python",
                proficiency_level="advanced",
            )
        )

        db.add(
            WorkExperience(
                candidate_id=candidate_id,
                company_name="Previous Company",
                job_title="Backend Developer",
                start_date=date(2023, 1, 1),
                end_date=None,
                is_current=True,
            )
        )

        job = Job(
            title="Backend Engineer",
            company_name="Example Company",
            description=(
                "Build REST APIs using Python. "
                "Two years of experience preferred."
            ),
            location="Islamabad",
            job_url="https://fixtures.qa.test/jobs/200",
            work_mode="remote",
            is_active=True,
        )

        db.add(job)
        db.commit()

        job_id = job.id

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db

    # Mock model inference, not the matching engine.
    monkeypatch.setattr(
        matching_routes,
        "embed_texts",
        lambda texts: [[1.0] + [0.0] * 383],
    )

    try:
        with TestClient(app) as client:
            yield client, candidate_id, job_id, monkeypatch
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def endpoint(candidate_id):
    return (
        f"/api/v1/candidates/"
        f"{candidate_id}/hybrid-matches"
    )


HEADERS = {"X-Dev-Job-Key": "test-secret"}


def test_hybrid_api_returns_both_scores(
    client_and_ids,
):
    client, candidate_id, job_id, monkeypatch = client_and_ids

    def fake_search(db, *, job_ids, query_vector):
        assert job_id in job_ids
        assert len(query_vector) == 384
        return {job_id: 0.9}

    monkeypatch.setattr(
        matching_routes,
        "nearest_job_similarities",
        fake_search,
    )

    response = client.get(
        endpoint(candidate_id),
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()
    item = data["items"][0]

    assert data["embedded_jobs"] == 1
    assert item["semantic_score"] == 90.0
    assert item["hybrid_score"] == item["score"]
    assert 0 <= item["rule_score"] <= 100


def test_missing_embedding_uses_rule_score(
    client_and_ids,
):
    client, candidate_id, _, monkeypatch = client_and_ids

    monkeypatch.setattr(
        matching_routes,
        "nearest_job_similarities",
        lambda *args, **kwargs: {},
    )

    response = client.get(
        endpoint(candidate_id),
        headers=HEADERS,
    )

    assert response.status_code == 200

    item = response.json()["items"][0]

    assert item["semantic_score"] is None
    assert item["hybrid_score"] == item["rule_score"]
    assert item["warnings"]


def test_requires_development_key(
    client_and_ids,
):
    client, candidate_id, _, _ = client_and_ids

    response = client.get(
        endpoint(candidate_id)
    )

    assert response.status_code == 403


def test_unknown_candidate(
    client_and_ids,
):
    client, _, _, _ = client_and_ids

    response = client.get(
        endpoint(uuid.uuid4()),
        headers=HEADERS,
    )

    assert response.status_code == 404


def test_salary_currency_validation(
    client_and_ids,
):
    client, candidate_id, _, _ = client_and_ids

    response = client.get(
        endpoint(candidate_id),
        headers=HEADERS,
        params={"minimum_salary": 50000},
    )

    assert response.status_code == 422

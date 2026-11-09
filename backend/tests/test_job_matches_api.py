
import uuid
from datetime import date

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
def matching_client(monkeypatch):
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
                full_name="Test Candidate",
                email="matching@example.com",
                location="Islamabad",
                years_experience=3,
            )
        )

        db.add(
            CandidateSkill(
                candidate_id=candidate_id,
                name="Python",
                proficiency_level="advanced",
            )
        )

        db.add(
            CandidateSkill(
                candidate_id=candidate_id,
                name="FastAPI",
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

        db.add(
            Job(
                title="Backend Developer",
                company_name="Example Technologies",
                location="Islamabad",
                description=(
                    "Python and FastAPI. "
                    "Minimum 2 years of experience."
                ),
                job_url="https://fixtures.qa.test/jobs/1",
                work_mode="remote",
                is_active=True,
            )
        )

        db.add(
            Job(
                title="Graphic Designer",
                company_name="Design Company",
                location="Lahore",
                description=(
                    "Graphic design and visual branding."
                ),
                job_url="https://fixtures.qa.test/jobs/2",
                work_mode="onsite",
                is_active=True,
            )
        )

        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            yield client, candidate_id
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_matches_rank_relevant_job_first(
    matching_client,
):
    client, candidate_id = matching_client

    response = client.get(
        f"/api/v1/candidates/{candidate_id}/matches",
        headers={
            "X-Dev-Job-Key": "test-secret",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["evaluated_jobs"] == 2
    assert data["returned_jobs"] == 2

    first = data["items"][0]

    assert first["title"] == "Backend Developer"
    assert "Python" in first["matched_skills"]
    assert first["score"] >= data["items"][1]["score"]


def test_matching_requires_dev_key(
    matching_client,
):
    client, candidate_id = matching_client

    response = client.get(
        f"/api/v1/candidates/{candidate_id}/matches"
    )

    assert response.status_code == 403


def test_unknown_candidate_returns_404(
    matching_client,
):
    client, _ = matching_client

    response = client.get(
        f"/api/v1/candidates/{uuid.uuid4()}/matches",
        headers={
            "X-Dev-Job-Key": "test-secret",
        },
    )

    assert response.status_code == 404


def test_salary_requires_currency(
    matching_client,
):
    client, candidate_id = matching_client

    response = client.get(
        f"/api/v1/candidates/{candidate_id}/matches",
        headers={
            "X-Dev-Job-Key": "test-secret",
        },
        params={
            "minimum_salary": 50000,
        },
    )

    assert response.status_code == 422


def test_limit_and_score_filter(
    matching_client,
):
    client, candidate_id = matching_client

    response = client.get(
        f"/api/v1/candidates/{candidate_id}/matches",
        headers={
            "X-Dev-Job-Key": "test-secret",
        },
        params={
            "limit": 1,
            "min_score": 0,
        },
    )

    assert response.status_code == 200
    assert response.json()["returned_jobs"] == 1


def test_matching_disabled_in_production(
    matching_client,
    monkeypatch,
):
    client, candidate_id = matching_client

    monkeypatch.setattr(
        settings,
        "app_env",
        "production",
    )

    response = client.get(
        f"/api/v1/candidates/{candidate_id}/matches",
        headers={
            "X-Dev-Job-Key": "test-secret",
        },
    )

    assert response.status_code == 403

"""Recommendation API integration tests."""

import uuid
from datetime import date

import app.api.routes.job_recommendations as recommendation_routes
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
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

HEADERS = {"X-Dev-Job-Key": "test-secret"}


def endpoint(candidate_id):
    return f"/api/v1/candidates/{candidate_id}/recommendations"


@pytest.fixture
def recommendation_client(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
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
                email="day13@example.test",
                location="Islamabad",
                years_experience=0,
                professional_summary="Python and AI projects",
            )
        )

        for name in ["Python", "FastAPI", "PostgreSQL"]:
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
                company_name="Internship Company",
                job_title="AI Intern",
                start_date=date(2025, 6, 1),
                end_date=date(2025, 8, 1),
                is_current=False,
            )
        )

        db.add_all(
            [
                Job(
                    title="Python Backend Developer",
                    company_name="Example Employer",
                    description="Build Python and FastAPI APIs",
                    job_url="https://company.test/jobs/backend",
                    source="greenhouse:example",
                    location="Islamabad, Pakistan",
                    work_mode="remote",
                    is_active=True,
                ),
                Job(
                    title="Python Data Engineer",
                    company_name="Data Employer",
                    description="Use Python and PostgreSQL",
                    job_url="https://company.test/jobs/data",
                    source="lever:dataemployer",
                    location="Islamabad, Pakistan",
                    work_mode="remote",
                    is_active=True,
                ),
                Job(
                    title="Sales Representative",
                    company_name="Sales Employer",
                    description="Customer outreach and presentations",
                    job_url="https://company.test/jobs/sales",
                    source="greenhouse:example",
                    location="New York",
                    work_mode="remote",
                    is_active=True,
                ),
                Job(
                    title="Rust Developer",
                    company_name="Lever Demo",
                    description="Rust and Python applications",
                    job_url="https://jobs.lever.co/leverdemo/abc",
                    source="lever:leverdemo",
                    location="Remote",
                    work_mode="remote",
                    is_active=True,
                ),
            ]
        )

        db.commit()

    def override_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            yield client, candidate_id, engine, monkeypatch
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_rules_mode_filters_unrelated_and_demo_jobs(
    recommendation_client,
):
    client, candidate_id, _, _ = recommendation_client

    response = client.get(
        endpoint(candidate_id),
        params={"mode": "rules", "min_score": 0},
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["requested_mode"] == "rules"
    assert data["ranking_mode"] == "rules"
    assert data["evaluated_jobs"] == 3
    assert data["total_matches"] == 2

    titles = [item["title"] for item in data["items"]]

    assert "Python Backend Developer" in titles
    assert "Python Data Engineer" in titles
    assert "Sales Representative" not in titles
    assert "Rust Developer" not in titles


def test_recommendations_have_explanations(
    recommendation_client,
):
    client, candidate_id, _, _ = recommendation_client

    response = client.get(
        endpoint(candidate_id),
        params={"mode": "rules", "min_score": 0},
        headers=HEADERS,
    )

    assert response.status_code == 200

    for item in response.json()["items"]:
        assert item["matched_skills"]
        assert item["reasons"]
        assert item["cautions"]
        assert 0 <= item["score"] <= 100


def test_pagination_applies_after_ranking(
    recommendation_client,
):
    client, candidate_id, _, _ = recommendation_client

    first = client.get(
        endpoint(candidate_id),
        params={
            "mode": "rules",
            "min_score": 0,
            "limit": 1,
            "offset": 0,
        },
        headers=HEADERS,
    )

    second = client.get(
        endpoint(candidate_id),
        params={
            "mode": "rules",
            "min_score": 0,
            "limit": 1,
            "offset": 1,
        },
        headers=HEADERS,
    )

    first_data = first.json()
    second_data = second.json()

    assert first.status_code == 200
    assert second.status_code == 200

    assert first_data["total_matches"] == 2
    assert second_data["total_matches"] == 2

    assert first_data["has_more"] is True
    assert second_data["has_more"] is False

    assert first_data["items"][0]["job_id"] != (
        second_data["items"][0]["job_id"]
    )


def test_title_filter(
    recommendation_client,
):
    client, candidate_id, _, _ = recommendation_client

    response = client.get(
        endpoint(candidate_id),
        params={
            "mode": "rules",
            "min_score": 0,
            "title_contains": "Data",
        },
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["total_matches"] == 1
    assert response.json()["items"][0]["title"] == (
        "Python Data Engineer"
    )


def test_empty_results_are_allowed(
    recommendation_client,
):
    client, candidate_id, _, _ = recommendation_client

    response = client.get(
        endpoint(candidate_id),
        params={
            "mode": "rules",
            "title_contains": "Quantum Research",
        },
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total_matches"] == 0
    assert response.json()["has_more"] is False


def test_hybrid_mode_uses_vector_scores(
    recommendation_client,
):
    client, candidate_id, _, monkeypatch = recommendation_client

    monkeypatch.setattr(
        recommendation_routes,
        "embed_texts",
        lambda texts: [[1.0] + [0.0] * 383],
    )

    def fake_similarities(db, *, job_ids, query_vector):
        assert len(query_vector) == 384
        return {job_id: 0.75 for job_id in job_ids}

    monkeypatch.setattr(
        recommendation_routes,
        "nearest_job_similarities",
        fake_similarities,
    )

    response = client.get(
        endpoint(candidate_id),
        params={"mode": "hybrid", "min_score": 0},
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["ranking_mode"] == "hybrid"
    assert data["semantic_jobs"] == 3
    assert data["total_matches"] == 2
    assert all(
        item["semantic_score"] == 75.0
        for item in data["items"]
    )


def test_rules_mode_does_not_load_embedding_model(
    recommendation_client,
):
    client, candidate_id, _, monkeypatch = recommendation_client

    def should_not_run(*args, **kwargs):
        raise AssertionError("Embedding model must not run")

    monkeypatch.setattr(
        recommendation_routes,
        "embed_texts",
        should_not_run,
    )

    response = client.get(
        endpoint(candidate_id),
        params={"mode": "rules"},
        headers=HEADERS,
    )

    assert response.status_code == 200


def test_missing_profile_is_rejected(
    recommendation_client,
):
    client, _, engine, _ = recommendation_client

    empty_candidate_id = uuid.uuid4()

    with Session(engine) as db:
        db.add(
            CandidateProfile(
                id=empty_candidate_id,
                full_name="Empty Candidate",
                email="empty@example.test",
            )
        )
        db.commit()

    response = client.get(
        endpoint(empty_candidate_id),
        params={"mode": "rules"},
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_unknown_candidate_returns_404(
    recommendation_client,
):
    client, _, _, _ = recommendation_client

    response = client.get(
        endpoint(uuid.uuid4()),
        params={"mode": "rules"},
        headers=HEADERS,
    )

    assert response.status_code == 404


def test_development_key_required(
    recommendation_client,
):
    client, candidate_id, _, _ = recommendation_client

    response = client.get(
        endpoint(candidate_id),
        params={"mode": "rules"},
    )

    assert response.status_code == 403


def test_production_access_disabled(
    recommendation_client,
):
    client, candidate_id, _, monkeypatch = recommendation_client

    monkeypatch.setattr(
        settings,
        "app_env",
        "production",
    )

    response = client.get(
        endpoint(candidate_id),
        headers=HEADERS,
    )

    assert response.status_code == 403


def test_invalid_pagination_is_rejected(
    recommendation_client,
):
    client, candidate_id, _, _ = recommendation_client

    response = client.get(
        endpoint(candidate_id),
        params={
            "mode": "rules",
            "limit": 0,
        },
        headers=HEADERS,
    )

    assert response.status_code == 422


def test_partial_embeddings_fall_back_to_consistent_rules(
    recommendation_client,
):
    client, candidate_id, _, monkeypatch = recommendation_client

    monkeypatch.setattr(
        recommendation_routes,
        "embed_texts",
        lambda texts: [[1.0] + [0.0] * 383],
    )

    def partial_search(db, *, job_ids, query_vector):
        return {job_ids[0]: 0.90}

    monkeypatch.setattr(
        recommendation_routes,
        "nearest_job_similarities",
        partial_search,
    )

    response = client.get(
        endpoint(candidate_id),
        params={"mode": "hybrid", "min_score": 0},
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["requested_mode"] == "hybrid"
    assert data["ranking_mode"] == "rules"
    assert data["semantic_jobs"] == 1
    assert data["model_name"] is None

    assert all(
        item["semantic_score"] is None
        for item in data["items"]
    )


def test_strict_remote_excludes_unknown_jobs(
    recommendation_client,
):
    client, candidate_id, engine, _ = recommendation_client

    with Session(engine) as db:
        for job in db.scalars(select(Job)).all():
            job.work_mode = None
        db.commit()

    response = client.get(
        endpoint(candidate_id),
        params={
            "mode": "rules",
            "work_mode": "remote",
            "min_score": 0,
        },
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["evaluated_jobs"] == 3
    assert data["unknown_work_mode_jobs"] == 3
    assert data["filtered_jobs"] == 0
    assert data["filtered_out_jobs"] == 3
    assert data["items"] == []


def test_unknown_jobs_can_be_included_for_review(
    recommendation_client,
):
    client, candidate_id, engine, _ = recommendation_client

    with Session(engine) as db:
        for job in db.scalars(select(Job)).all():
            job.work_mode = None
        db.commit()

    response = client.get(
        endpoint(candidate_id),
        params={
            "mode": "rules",
            "work_mode": "remote",
            "include_unknown_work_mode": True,
            "min_score": 0,
        },
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["filtered_jobs"] == 3
    assert data["total_matches"] == 2
    assert all(
        item["work_mode"] is None
        for item in data["items"]
    )
    assert all(
        any(
            "Work mode is unknown" in caution
            for caution in item["cautions"]
        )
        for item in data["items"]
    )


def test_soft_remote_preference_keeps_unknown_jobs(
    recommendation_client,
):
    client, candidate_id, engine, _ = recommendation_client

    with Session(engine) as db:
        for job in db.scalars(select(Job)).all():
            job.work_mode = None
        db.commit()

    response = client.get(
        endpoint(candidate_id),
        params={
            "mode": "rules",
            "preferred_work_mode": "remote",
            "min_score": 0,
        },
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["filtered_jobs"] == 3


def test_include_unknown_without_filter_is_invalid(
    recommendation_client,
):
    client, candidate_id, _, _ = recommendation_client

    response = client.get(
        endpoint(candidate_id),
        params={
            "mode": "rules",
            "include_unknown_work_mode": True,
        },
        headers=HEADERS,
    )

    assert response.status_code == 422

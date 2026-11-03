
import pytest
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.job import Job
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        settings, "app_env", "development"
    )
    monkeypatch.setattr(
        settings, "dev_job_write_key", "test-secret"
    )

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Job.__table__.create(engine)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def sample_job(
    url="https://example.com/jobs/1",
    title="Backend Engineer",
    mode="remote",
):
    return {
        "title": title,
        "company_name": "Northstar",
        "location": "Remote",
        "description": "Python and FastAPI role",
        "job_url": url,
        "work_mode": mode,
        "salary_min": 50000,
        "salary_max": 90000,
        "salary_currency": "USD",
    }


def create_job(client, body):
    return client.post(
        "/api/v1/jobs",
        json=body,
        headers={"X-Dev-Job-Key": "test-secret"},
    )


def test_create_and_fetch_job(client):
    response = create_job(client, sample_job())

    assert response.status_code == 201

    job = response.json()

    assert job["salary_currency"] == "USD"

    detail = client.get(
        f"/api/v1/jobs/{job['id']}"
    )

    assert detail.status_code == 200
    assert detail.json()["title"] == "Backend Engineer"


def test_job_creation_requires_key(client):
    response = client.post(
        "/api/v1/jobs",
        json=sample_job(),
    )

    assert response.status_code == 403


def test_duplicate_url_returns_409(client):
    assert create_job(
        client, sample_job()
    ).status_code == 201

    assert create_job(
        client, sample_job()
    ).status_code == 409


def test_search_and_filter(client):
    create_job(client, sample_job())

    create_job(
        client,
        sample_job(
            url="https://example.com/jobs/2",
            title="Designer",
            mode="onsite",
        ),
    )

    response = client.get(
        "/api/v1/jobs",
        params={
            "q": "python",
            "work_mode": "remote",
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


def test_pagination(client):
    create_job(client, sample_job())

    create_job(
        client,
        sample_job(url="https://example.com/jobs/2"),
    )

    response = client.get(
        "/api/v1/jobs",
        params={"limit": 1, "offset": 1},
    )

    data = response.json()

    assert response.status_code == 200
    assert data["total"] == 2
    assert len(data["items"]) == 1


def test_invalid_salary_rejected(client):
    body = sample_job()
    body["salary_max"] = 1000

    response = create_job(client, body)

    assert response.status_code == 422


def test_salary_filter_requires_currency(client):
    response = client.get(
        "/api/v1/jobs",
        params={"minimum_salary": 60000},
    )

    assert response.status_code == 422


def test_salary_filter(client):
    create_job(client, sample_job())

    response = client.get(
        "/api/v1/jobs",
        params={
            "minimum_salary": 80000,
            "salary_currency": "USD",
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_missing_job_returns_404(client):
    response = client.get("/api/v1/jobs/99999")

    assert response.status_code == 404


def test_invalid_page_size(client):
    response = client.get(
        "/api/v1/jobs",
        params={"limit": 101},
    )

    assert response.status_code == 422


def test_search_wildcard_is_literal(client):
    create_job(client, sample_job())

    response = client.get(
        "/api/v1/jobs",
        params={"q": "%"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_writes_disabled_in_production(
    client, monkeypatch
):
    monkeypatch.setattr(
        settings, "app_env", "production"
    )

    response = create_job(client, sample_job())

    assert response.status_code == 403
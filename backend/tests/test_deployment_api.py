"""Tests for safe deployment diagnostics."""

from app.core.config import settings
from app.main import app
from fastapi.testclient import TestClient

HEADERS = {"X-Dev-Job-Key": "test-secret"}


def test_deployment_endpoint_is_safe(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(
        settings, "dev_job_write_key", "test-secret"
    )
    monkeypatch.setenv("CONTAINERIZED", "1")

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/ops/deployment",
            headers=HEADERS,
        )

    assert response.status_code == 200

    data = response.json()

    assert data["containerized"] is True
    assert data["database_backend"] in {
        "postgresql",
        "sqlite",
    }
    assert data["workflow_checkpoint"] == "process_memory"
    assert data["automatic_submission_enabled"] is False

    # Never expose credentials or connection strings.
    assert "database_url" not in data
    assert "groq_api_key" not in data
    assert "dev_job_write_key" not in data


def test_deployment_reports_local_mode(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(
        settings, "dev_job_write_key", "test-secret"
    )
    monkeypatch.delenv("CONTAINERIZED", raising=False)

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/ops/deployment",
            headers=HEADERS,
        )

    assert response.status_code == 200
    assert response.json()["containerized"] is False


def test_development_key_is_required(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(
        settings, "dev_job_write_key", "test-secret"
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/ops/deployment")

    assert response.status_code == 403


def test_wrong_development_key_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(
        settings, "dev_job_write_key", "test-secret"
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/ops/deployment",
            headers={"X-Dev-Job-Key": "wrong-key"},
        )

    assert response.status_code == 403


def test_production_mode_disables_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(
        settings, "dev_job_write_key", "test-secret"
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/ops/deployment",
            headers=HEADERS,
        )

    assert response.status_code == 403
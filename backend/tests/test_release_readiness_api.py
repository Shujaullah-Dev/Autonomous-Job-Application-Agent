
"""Security audit and readiness API tests."""

from app.api.routes.jobs import require_dev_write_key
from app.core.config import settings
from app.main import app
from app.services.security_audit import audit_candidate_routes
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

HEADERS = {"X-Dev-Job-Key": "day24-test-key"}

def test_security_auditor_detects_unguarded_routes():
    sample = FastAPI()

    @sample.get("/api/v1/candidates/{candidate_id}")
    def read_candidate(candidate_id: str):
        return {"candidate_id": candidate_id}

    @sample.get(
        "/api/v1/candidates/{candidate_id}/protected",
        dependencies=[Depends(require_dev_write_key)],
    )
    def protected_candidate(candidate_id: str):
        return {"candidate_id": candidate_id}

    report = audit_candidate_routes(sample)

    assert report.candidate_route_count == 2
    assert report.dev_key_guarded_count == 1
    assert len(report.routes_without_dev_key) == 1
    assert report.production_user_auth_verified is False

def test_migration_audit_endpoint(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(
        settings,
        "dev_job_write_key",
        "day24-test-key",
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/ops/migration-audit",
            headers=HEADERS,
        )

    assert response.status_code == 200

    data = response.json()

    assert data["revision_count"] > 0
    assert isinstance(data["heads"], list)
    assert isinstance(data["findings"], list)

def test_release_readiness_reports_current_blockers(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(
        settings,
        "dev_job_write_key",
        "day24-test-key",
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/ops/release-readiness",
            headers=HEADERS,
        )

    assert response.status_code == 200

    data = response.json()

    assert data["ready_for_public_deployment"] is False
    assert data["production_user_auth_verified"] is False
    assert data["candidate_route_count"] > 0
    assert data["blockers"]

def test_release_report_excludes_credentials(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(
        settings,
        "dev_job_write_key",
        "day24-test-key",
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/ops/release-readiness",
            headers=HEADERS,
        )

    assert response.status_code == 200

    data = response.json()

    for field in (
        "database_url",
        "groq_api_key",
        "dev_job_write_key",
    ):
        assert field not in data

    assert "day24-test-key" not in response.text

def test_release_audit_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(
        settings,
        "dev_job_write_key",
        "day24-test-key",
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/ops/release-readiness",
        )

    assert response.status_code == 403

def test_incorrect_key_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(
        settings,
        "dev_job_write_key",
        "day24-test-key",
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/ops/migration-audit",
            headers={"X-Dev-Job-Key": "incorrect"},
        )

    assert response.status_code == 403

def test_production_mode_rejects_audit(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(
        settings,
        "dev_job_write_key",
        "day24-test-key",
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/ops/release-readiness",
            headers=HEADERS,
        )

    assert response.status_code == 403


def test_auditor_detects_included_router_routes():
    from app.api.routes.jobs import require_dev_write_key
    from app.services.security_audit import (
        audit_candidate_routes,
    )
    from fastapi import APIRouter, Depends, FastAPI

    sample = FastAPI()

    public_router = APIRouter(
        prefix="/api/v1/candidates",
    )

    protected_router = APIRouter(
        prefix="/api/v1/candidates",
        dependencies=[Depends(require_dev_write_key)],
    )

    @public_router.get("/{candidate_id}")
    def get_candidate(candidate_id: str):
        return {"id": candidate_id}

    @protected_router.get(
        "/{candidate_id}/applications"
    )
    def get_applications(candidate_id: str):
        return {"candidate_id": candidate_id}

    sample.include_router(public_router)
    sample.include_router(protected_router)

    report = audit_candidate_routes(sample)

    assert report.candidate_route_count == 2
    assert report.dev_key_guarded_count == 1

    assert len(report.routes_without_dev_key) == 1

    assert any(
        "/api/v1/candidates/{candidate_id}" in path
        for path in report.routes_without_dev_key
    )

    assert report.production_user_auth_verified is False

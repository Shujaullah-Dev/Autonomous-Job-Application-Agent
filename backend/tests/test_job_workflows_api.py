
"""Workflow API tests."""

import uuid

import app.api.routes.job_workflows as workflow_routes
import pytest
from app.core.config import settings
from app.main import app
from app.services.job_workflow_graph import build_job_workflow
from fastapi.testclient import TestClient

HEADERS = {"X-Dev-Job-Key": "test-secret"}


def candidate_url(candidate_id):
    return f"/api/v1/candidates/{candidate_id}/workflows"


def sample_provider(state):
    return [
        {
            "job_id": 10,
            "title": "Python Developer",
            "score": 82.0,
            "work_mode": None,
            "reasons": ["Python skill matches."],
            "cautions": ["Remote eligibility unverified."],
        },
        {
            "job_id": 20,
            "title": "AI Engineer",
            "score": 76.0,
            "work_mode": "remote",
            "reasons": ["AI skills match."],
            "cautions": ["Country eligibility unverified."],
        },
    ]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        settings, "app_env", "development"
    )
    monkeypatch.setattr(
        settings, "dev_job_write_key", "test-secret"
    )

    # Each test receives fresh checkpoint memory.
    monkeypatch.setattr(
        workflow_routes,
        "_graph",
        build_job_workflow(sample_provider),
    )

    with TestClient(app) as test_client:
        yield test_client


def test_start_pauses_for_review(client):
    candidate_id = uuid.uuid4()

    response = client.post(
        candidate_url(candidate_id),
        json={},
        headers=HEADERS,
    )

    assert response.status_code == 201
    data = response.json()

    assert data["status"] == "pending_review"
    assert data["awaiting_review"] is True
    assert len(data["shortlist"]) == 2
    assert data["approved_job_ids"] == []


def test_get_existing_workflow(client):
    candidate_id = uuid.uuid4()

    started = client.post(
        candidate_url(candidate_id),
        json={},
        headers=HEADERS,
    ).json()

    workflow_id = started["workflow_id"]

    response = client.get(
        f"{candidate_url(candidate_id)}/{workflow_id}",
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["workflow_id"] == workflow_id
    assert response.json()["status"] == "pending_review"


def test_approve_selected_job(client):
    candidate_id = uuid.uuid4()

    started = client.post(
        candidate_url(candidate_id),
        json={},
        headers=HEADERS,
    ).json()

    workflow_id = started["workflow_id"]

    response = client.post(
        (
            f"{candidate_url(candidate_id)}"
            f"/{workflow_id}/review"
        ),
        json={
            "decision": "approve",
            "approved_job_ids": [10],
        },
        headers=HEADERS,
    )

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "approved"
    assert data["approved_job_ids"] == [10]
    assert data["awaiting_review"] is False


def test_reject_shortlist(client):
    candidate_id = uuid.uuid4()

    started = client.post(
        candidate_url(candidate_id),
        json={},
        headers=HEADERS,
    ).json()

    response = client.post(
        (
            f"{candidate_url(candidate_id)}"
            f"/{started['workflow_id']}/review"
        ),
        json={
            "decision": "reject",
            "approved_job_ids": [],
        },
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_cannot_approve_unknown_job(client):
    candidate_id = uuid.uuid4()

    started = client.post(
        candidate_url(candidate_id),
        json={},
        headers=HEADERS,
    ).json()

    response = client.post(
        (
            f"{candidate_url(candidate_id)}"
            f"/{started['workflow_id']}/review"
        ),
        json={
            "decision": "approve",
            "approved_job_ids": [999],
        },
        headers=HEADERS,
    )

    assert response.status_code == 409


def test_cannot_review_twice(client):
    candidate_id = uuid.uuid4()

    started = client.post(
        candidate_url(candidate_id),
        json={},
        headers=HEADERS,
    ).json()

    url = (
        f"{candidate_url(candidate_id)}"
        f"/{started['workflow_id']}/review"
    )

    payload = {
        "decision": "approve",
        "approved_job_ids": [10],
    }

    first = client.post(
        url,
        json=payload,
        headers=HEADERS,
    )

    second = client.post(
        url,
        json=payload,
        headers=HEADERS,
    )

    assert first.status_code == 200
    assert second.status_code == 409


def test_candidate_cannot_access_different_workflow(client):
    first_candidate = uuid.uuid4()
    second_candidate = uuid.uuid4()

    started = client.post(
        candidate_url(first_candidate),
        json={},
        headers=HEADERS,
    ).json()

    response = client.get(
        (
            f"{candidate_url(second_candidate)}"
            f"/{started['workflow_id']}"
        ),
        headers=HEADERS,
    )

    assert response.status_code == 404


def test_development_key_required(client):
    candidate_id = uuid.uuid4()

    response = client.post(
        candidate_url(candidate_id),
        json={},
    )

    assert response.status_code == 403


def test_invalid_approval_payload(client):
    candidate_id = uuid.uuid4()

    started = client.post(
        candidate_url(candidate_id),
        json={},
        headers=HEADERS,
    ).json()

    response = client.post(
        (
            f"{candidate_url(candidate_id)}"
            f"/{started['workflow_id']}/review"
        ),
        json={
            "decision": "approve",
            "approved_job_ids": [True],
        },
        headers=HEADERS,
    )

    assert response.status_code == 422


def test_invalid_unknown_work_mode_option(client):
    candidate_id = uuid.uuid4()

    response = client.post(
        candidate_url(candidate_id),
        json={
            "include_unknown_work_mode": True
        },
        headers=HEADERS,
    )

    assert response.status_code == 422


def test_production_access_disabled(client, monkeypatch):
    monkeypatch.setattr(
        settings, "app_env", "production"
    )

    response = client.post(
        candidate_url(uuid.uuid4()),
        json={},
        headers=HEADERS,
    )

    assert response.status_code == 403


def test_no_matches_path(client, monkeypatch):
    monkeypatch.setattr(
        workflow_routes,
        "_graph",
        build_job_workflow(lambda state: []),
    )

    response = client.post(
        candidate_url(uuid.uuid4()),
        json={},
        headers=HEADERS,
    )

    assert response.status_code == 201
    assert response.json()["status"] == "no_matches"
    assert response.json()["awaiting_review"] is False

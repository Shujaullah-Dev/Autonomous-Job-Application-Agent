"""Identity and candidate ownership.

Verified Supabase access tokens are required for private candidate data.
The shared development key only gates local development and never proves
ownership.
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from app.core import auth
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models.candidate import CandidateProfile
from app.models.skill import CandidateSkill
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

SECRET = "unit-test-jwt-secret-that-is-long-enough-for-hs256"
ISSUER = "https://example.supabase.co/auth/v1"
AUDIENCE = "authenticated"
USER_ID = "11111111-1111-4111-8111-111111111111"
OTHER_USER_ID = "22222222-2222-4222-8222-222222222222"


def access_token(
    subject: str = USER_ID,
    email: str = "owner@example.com",
    *,
    secret: str = SECRET,
    audience: str = AUDIENCE,
    issuer: str = ISSUER,
    expires_in: int = 600,
) -> str:
    issued_at = datetime.now(timezone.utc)  # noqa: UP017

    return jwt.encode(
        {
            "sub": subject,
            "email": email,
            "aud": audience,
            "iss": issuer,
            "iat": issued_at,
            "exp": issued_at + timedelta(seconds=expires_in),
            "role": "authenticated",
        },
        secret,
        algorithm="HS256",
    )


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    CandidateProfile.__table__.create(engine)
    CandidateSkill.__table__.create(engine)

    yield engine

    engine.dispose()


@pytest.fixture
def candidate_id(engine):
    candidate_id = uuid.uuid4()

    with Session(engine) as db:
        db.add(
            CandidateProfile(
                id=candidate_id,
                full_name="Owned Candidate",
                email="owner@example.com",
                owner_id=USER_ID,
            )
        )
        db.commit()

    return candidate_id


@pytest.fixture
def client(monkeypatch, engine):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "dev_job_write_key", "test-secret")
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_jwks_url", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    monkeypatch.setattr(settings, "supabase_jwt_issuer", ISSUER)
    monkeypatch.setattr(settings, "supabase_jwt_audience", AUDIENCE)
    monkeypatch.setattr(settings, "langgraph_checkpoint_url", "")
    auth._jwks_cache.clear()

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        auth._jwks_cache.clear()


def skills_url(candidate_id: uuid.UUID) -> str:
    return f"/api/v1/candidates/{candidate_id}/skills"


def test_missing_token_is_rejected_in_production(client, candidate_id, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")

    response = client.get(skills_url(candidate_id))

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_expired_token_is_rejected(client, candidate_id):
    response = client.get(
        skills_url(candidate_id),
        headers=bearer(access_token(expires_in=-60)),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Access token has expired"


def test_token_signed_with_another_secret_is_rejected(client, candidate_id):
    response = client.get(
        skills_url(candidate_id),
        headers=bearer(access_token(secret="not-the-configured-secret")),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Access token is invalid"


def test_wrong_audience_is_rejected(client, candidate_id):
    response = client.get(
        skills_url(candidate_id),
        headers=bearer(access_token(audience="another-audience")),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Access token audience is invalid"


def test_wrong_issuer_is_rejected(client, candidate_id):
    response = client.get(
        skills_url(candidate_id),
        headers=bearer(access_token(issuer="https://attacker.example/auth/v1")),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Access token issuer is invalid"


def test_malformed_authorization_header_is_rejected(client, candidate_id):
    response = client.get(
        skills_url(candidate_id),
        headers={"Authorization": f"Token {access_token()}"},
    )

    assert response.status_code == 401


def test_owner_can_read_own_candidate(client, candidate_id):
    response = client.get(skills_url(candidate_id), headers=bearer(access_token()))

    assert response.status_code == 200
    assert response.json() == []


def test_other_account_gets_privacy_preserving_404(client, candidate_id):
    response = client.get(
        skills_url(candidate_id),
        headers=bearer(
            access_token(subject=OTHER_USER_ID, email="other@example.com")
        ),
    )

    assert response.status_code == 404


def test_other_account_cannot_mutate_owned_profile(client, candidate_id):
    response = client.patch(
        f"/api/v1/candidates/{candidate_id}",
        json={"location": "Elsewhere"},
        headers=bearer(
            access_token(subject=OTHER_USER_ID, email="other@example.com")
        ),
    )

    assert response.status_code == 404


def test_owner_can_mutate_own_profile(client, candidate_id):
    response = client.patch(
        f"/api/v1/candidates/{candidate_id}",
        json={"location": "Islamabad"},
        headers=bearer(access_token()),
    )

    assert response.status_code == 200
    assert response.json()["location"] == "Islamabad"


def test_own_candidate_endpoint_returns_owned_profile(client, candidate_id):
    response = client.get("/api/v1/candidates/me", headers=bearer(access_token()))

    assert response.status_code == 200
    assert response.json()["id"] == str(candidate_id)


def test_own_candidate_endpoint_requires_authentication(client):
    response = client.get("/api/v1/candidates/me")

    assert response.status_code == 401


def test_own_candidate_endpoint_links_unowned_profile_by_email(
    client, engine
):
    unowned_id = uuid.uuid4()

    with Session(engine) as db:
        db.add(
            CandidateProfile(
                id=unowned_id,
                full_name="Legacy Candidate",
                email="owner@example.com",
            )
        )
        db.commit()

    response = client.get("/api/v1/candidates/me", headers=bearer(access_token()))

    assert response.status_code == 200
    assert response.json()["id"] == str(unowned_id)

    with Session(engine) as db:
        assert db.get(CandidateProfile, unowned_id).owner_id == USER_ID


def test_claiming_unowned_profile_requires_matching_email(client, engine):
    unowned_id = uuid.uuid4()

    with Session(engine) as db:
        db.add(
            CandidateProfile(
                id=unowned_id,
                full_name="Someone Else",
                email="someone-else@example.com",
            )
        )
        db.commit()

    response = client.get(
        skills_url(unowned_id),
        headers=bearer(access_token()),
    )

    assert response.status_code == 404


def test_create_candidate_assigns_verified_owner(client):
    response = client.post(
        "/api/v1/candidates",
        json={"full_name": "New Owner", "email": "owner@example.com"},
        headers=bearer(access_token()),
    )

    assert response.status_code == 201

    created_id = uuid.UUID(response.json()["id"])
    me = client.get("/api/v1/candidates/me", headers=bearer(access_token()))

    assert me.status_code == 200
    assert me.json()["id"] == str(created_id)


def test_create_candidate_rejects_unverified_email(client):
    response = client.post(
        "/api/v1/candidates",
        json={"full_name": "Impostor", "email": "other@example.com"},
        headers=bearer(access_token()),
    )

    assert response.status_code == 403


def test_second_profile_for_same_account_conflicts(client):
    first = client.post(
        "/api/v1/candidates",
        json={"full_name": "First", "email": "owner@example.com"},
        headers=bearer(access_token()),
    )
    second = client.post(
        "/api/v1/candidates",
        json={"full_name": "Second", "email": "owner@example.com"},
        headers=bearer(access_token(email="OWNER@example.com")),
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_development_key_still_opens_private_routers(client, candidate_id):
    response = client.post(
        f"/api/v1/candidates/{candidate_id}/workflows",
        json={},
        headers={"X-Dev-Job-Key": "test-secret"},
    )

    # The development gate passes; the request reaches the workflow service.
    assert response.status_code != 401
    assert response.status_code != 403


def test_development_key_is_refused_outside_development(
    client, candidate_id, monkeypatch
):
    monkeypatch.setattr(settings, "app_env", "production")

    response = client.post(
        f"/api/v1/candidates/{candidate_id}/workflows",
        json={},
        headers={"X-Dev-Job-Key": "test-secret"},
    )

    assert response.status_code == 401


def test_unconfigured_identity_rejects_token(
    client, candidate_id, monkeypatch
):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    monkeypatch.setattr(settings, "supabase_jwks_url", "")

    response = client.get(skills_url(candidate_id), headers=bearer(access_token()))

    assert response.status_code == 503


def test_unavailable_jwks_fails_safely(client, candidate_id, monkeypatch):
    import httpx

    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    monkeypatch.setattr(
        settings,
        "supabase_jwks_url",
        "https://identity.example.test/jwks.json",
    )

    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("identity provider unreachable")

    monkeypatch.setattr(auth.httpx, "get", unavailable)

    response = client.get(skills_url(candidate_id), headers=bearer(access_token()))

    assert response.status_code == 503
    assert "secret" not in response.text.lower()

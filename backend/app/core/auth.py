"""Verified Supabase identity and candidate ownership.

Browser requests carry a Supabase access token. Before a candidate-scoped
route reads or writes a record, this module verifies the token signature,
issuer, audience and expiry, then scopes the record to that account.

The development key stays a development-only gate. It never establishes
ownership, and it cannot be used outside ``APP_ENV=development``.
"""

from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.candidate import CandidateProfile

JWKS_CACHE_SECONDS = 600.0
JWKS_TIMEOUT_SECONDS = 5.0
ALLOWED_JWKS_ALGORITHMS = ("RS256", "RS384", "RS512", "ES256", "ES384", "EdDSA")

_jwks_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


@dataclass(frozen=True)
class AuthUser:
    """A verified account identity derived from an access token."""

    subject: str
    email: str | None
    claims: dict[str, Any]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _load_jwks(url: str, *, refresh: bool = False) -> list[dict[str, Any]]:
    """Return signing keys, refreshing a stale or incomplete cache."""

    cached = _jwks_cache.get(url)
    now = time.monotonic()

    if cached and not refresh and now - cached[0] < JWKS_CACHE_SECONDS:
        return cached[1]

    try:
        response = httpx.get(url, timeout=JWKS_TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User identity verification is temporarily unavailable",
        ) from None

    keys = payload.get("keys") if isinstance(payload, dict) else None

    if not isinstance(keys, list) or not keys:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User identity verification is temporarily unavailable",
        )

    _jwks_cache[url] = (now, keys)
    return keys


def _signing_material(token: str) -> tuple[Any, list[str]]:
    """Resolve the verification key and accepted algorithms for a token."""

    if settings.supabase_jwt_secret:
        return settings.supabase_jwt_secret, ["HS256", "HS384", "HS512"]

    jwks_url = settings.identity_jwks_url

    if not jwks_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User identity verification is not configured",
        )

    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError:
        raise _unauthorized("Access token is invalid") from None

    key_id = header.get("kid")
    keys = _load_jwks(jwks_url)
    candidate = next((key for key in keys if key.get("kid") == key_id), None)

    if candidate is None:
        # A rotated key is not in the cached set yet; refresh once.
        keys = _load_jwks(jwks_url, refresh=True)
        candidate = next((key for key in keys if key.get("kid") == key_id), None)

    if candidate is None:
        raise _unauthorized("Access token signing key is unknown")

    algorithm = candidate.get("alg")

    if algorithm not in ALLOWED_JWKS_ALGORITHMS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User identity verification is not configured",
        )

    try:
        return jwt.PyJWK(candidate, algorithm=algorithm).key, [algorithm]
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User identity verification is temporarily unavailable",
        ) from None


def decode_access_token(token: str) -> AuthUser:
    """Verify a Supabase access token and return its account identity."""

    key, algorithms = _signing_material(token)
    audience = settings.supabase_jwt_audience or None
    issuer = settings.identity_issuer or None

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=audience,
            issuer=issuer,
            leeway=30,
            options={
                "require": ["exp", "sub"],
                "verify_aud": bool(audience),
                "verify_iss": bool(issuer),
            },
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Access token has expired") from None
    except jwt.InvalidAudienceError:
        raise _unauthorized("Access token audience is invalid") from None
    except jwt.InvalidIssuerError:
        raise _unauthorized("Access token issuer is invalid") from None
    except jwt.InvalidTokenError:
        raise _unauthorized("Access token is invalid") from None

    subject = claims.get("sub")

    if not isinstance(subject, str) or not subject:
        raise _unauthorized("Access token is missing an account subject")

    email = claims.get("email")

    return AuthUser(
        subject=subject,
        email=email if isinstance(email, str) else None,
        claims=claims,
    )


def optional_user(
    authorization: Annotated[str | None, Header()] = None,
) -> AuthUser | None:
    """Return the verified account, or ``None`` when no token was sent."""

    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    token = token.strip()

    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("Authorization header must use the Bearer scheme")

    if not settings.identity_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="User identity verification is not configured",
        )

    return decode_access_token(token)


def require_user(
    user: Annotated[AuthUser | None, Depends(optional_user)],
) -> AuthUser:
    """Require a verified account, whatever the deployment mode."""

    if user is None:
        raise _unauthorized("Sign in to continue")

    return user


def require_private_access(
    authorization: Annotated[str | None, Header()] = None,
    dev_key: Annotated[str | None, Header(alias="X-Dev-Job-Key")] = None,
) -> AuthUser | None:
    """Gate private feature routers.

    A verified access token is always accepted. Outside development the
    development key is refused, so a shared key can never stand in for a
    user identity.
    """

    user = optional_user(authorization)

    if user is not None:
        return user

    if settings.app_env.lower() != "development":
        raise _unauthorized("Sign in to continue")

    if not settings.dev_job_write_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DEV_JOB_WRITE_KEY is not configured",
        )

    if not dev_key or not secrets.compare_digest(dev_key, settings.dev_job_write_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid development job write key",
        )

    return None


def require_candidate_owner(
    candidate_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[AuthUser | None, Depends(optional_user)],
) -> CandidateProfile | None:
    """Ensure the verified account owns the requested candidate record.

    Development requests without a token keep the existing development gate,
    which is why no ownership claim is made there. With a token, a record is
    returned only to its owner. Missing and foreign records both answer 404 so
    the API never confirms that another account's record exists.
    """

    if user is None:
        if settings.app_env.lower() != "development":
            raise _unauthorized("Sign in to continue")
        return None

    candidate = db.get(CandidateProfile, candidate_id)

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    if candidate.owner_id == user.subject:
        return candidate

    if candidate.owner_id is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    # Safe linking for a profile created before ownership existed: only the
    # account whose verified email matches may claim it.
    if (
        not user.email
        or not candidate.email
        or candidate.email.lower() != user.email.lower()
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    candidate.owner_id = user.subject

    try:
        db.commit()
        db.refresh(candidate)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from None

    return candidate

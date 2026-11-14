
"""Development-only Day 24 release-quality inspection endpoints."""

from dataclasses import asdict

from app.api.routes.jobs import require_dev_write_key
from app.schemas.release_readiness import (
    MigrationAuditResponse,
    ReleaseReadinessResponse,
)
from app.services.migration_audit import audit_migrations
from app.services.release_readiness import (
    ROOT,
    assess_release,
)
from fastapi import APIRouter, Depends, Request

router = APIRouter(
    prefix="/api/v1/ops",
    tags=["Day 24 Release Audit"],
    dependencies=[Depends(require_dev_write_key)],
)

@router.get(
    "/migration-audit",
    response_model=MigrationAuditResponse,
)
def get_migration_audit() -> MigrationAuditResponse:
    """Inspect migration source files without connecting to Supabase."""

    report = audit_migrations(ROOT)

    return MigrationAuditResponse.model_validate(
        asdict(report)
    )

@router.get(
    "/release-readiness",
    response_model=ReleaseReadinessResponse,
)
def get_release_readiness(
    request: Request,
) -> ReleaseReadinessResponse:
    """Inspect registered routes and source-level release blockers."""

    report = assess_release(
        request.app,
        ROOT,
    )

    return ReleaseReadinessResponse.model_validate(
        asdict(report)
    )
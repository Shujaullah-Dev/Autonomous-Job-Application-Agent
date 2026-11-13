"""Development-only deployment diagnostics."""

import os

from app.api.routes.jobs import require_dev_write_key
from app.core.config import settings
from app.db.session import engine
from app.schemas.deployment import DeploymentStatusResponse
from fastapi import APIRouter, Depends

router = APIRouter(
    prefix="/api/v1/ops",
    tags=["Deployment Diagnostics"],
    dependencies=[Depends(require_dev_write_key)],
)


@router.get(
    "/deployment",
    response_model=DeploymentStatusResponse,
)
def get_deployment_status() -> DeploymentStatusResponse:
    """
    Report non-secret deployment facts.

    This endpoint does not test database connectivity.
    Use /health/db or /api/v1/ops/readiness for that.
    """

    return DeploymentStatusResponse(
        app_name=settings.app_name,
        app_env=settings.app_env,
        containerized=(
            os.getenv("CONTAINERIZED") == "1"
        ),
        database_backend=engine.url.get_backend_name(),
        workflow_checkpoint="process_memory",
        notification_processing="one_shot",
        schema_migrations="manual",
        automatic_submission_enabled=False,
        message=(
            "Local development deployment diagnostics. "
            "No production user authentication or "
            "automatic application submission is enabled."
        ),
    )
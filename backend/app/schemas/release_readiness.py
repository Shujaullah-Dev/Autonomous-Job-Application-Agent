
"""Audit and release readiness API responses."""

from pydantic import BaseModel, Field


class MigrationFindingRead(BaseModel):
    code: str
    revision: str
    table: str
    message: str

class MigrationAuditResponse(BaseModel):
    heads: list[str]
    revision_count: int = Field(ge=0)
    findings: list[MigrationFindingRead]
    fresh_schema_safe: bool

class ReleaseReadinessResponse(BaseModel):
    ready_for_public_deployment: bool

    migration_heads: list[str]
    migration_findings: list[str]

    candidate_route_count: int = Field(ge=0)
    dev_key_guarded_count: int = Field(ge=0)

    routes_without_dev_key: list[str]

    production_user_auth_verified: bool
    persistent_workflow_checkpoints_verified: bool

    blockers: list[str]
    message: str

"""Combine migration and API-security findings for release review."""

from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI

from app.services.migration_audit import audit_migrations
from app.services.security_audit import audit_candidate_routes

ROOT = Path(__file__).resolve().parents[3]

@dataclass(frozen=True)
class ReleaseAssessment:
    ready_for_public_deployment: bool

    migration_heads: tuple[str, ...]
    migration_findings: tuple[str, ...]

    candidate_route_count: int
    dev_key_guarded_count: int
    routes_without_dev_key: tuple[str, ...]

    production_user_auth_verified: bool
    persistent_workflow_checkpoints_verified: bool

    blockers: tuple[str, ...]
    message: str

def assess_release(
    app: FastAPI,
    repository_root: Path = ROOT,
) -> ReleaseAssessment:
    """Perform source-level release checks without database writes."""

    migrations = audit_migrations(repository_root)
    security = audit_candidate_routes(app)

    checkpoint_file = (
        repository_root
        / "backend"
        / "app"
        / "services"
        / "job_workflow_graph.py"
    )

    checkpoint_source = checkpoint_file.read_text(
        encoding="utf-8"
    )

    # Presence of InMemorySaver is evidence of a non-durable
    # default workflow; this is not a full runtime proof.
    uses_memory_checkpoint = (
        "InMemorySaver" in checkpoint_source
    )

    blockers: list[str] = []

    if not migrations.fresh_schema_safe:
        blockers.append(
            "migration_history_requires_repair"
        )

    if security.routes_without_dev_key:
        blockers.append(
            "candidate_routes_missing_development_gate"
        )

    # A development key cannot establish candidate ownership.
    if not security.production_user_auth_verified:
        blockers.append(
            "production_user_authentication_not_verified"
        )

    if uses_memory_checkpoint:
        blockers.append(
            "workflow_checkpoints_not_durable"
        )

    migration_findings = tuple(
        (
            f"{item.code}: "
            f"{item.revision} "
            f"{item.table}"
        ).strip()
        for item in migrations.findings
    )

    ready = len(blockers) == 0

    return ReleaseAssessment(
        ready_for_public_deployment=ready,
        migration_heads=migrations.heads,
        migration_findings=migration_findings,
        candidate_route_count=security.candidate_route_count,
        dev_key_guarded_count=(
            security.dev_key_guarded_count
        ),
        routes_without_dev_key=(
            security.routes_without_dev_key
        ),
        production_user_auth_verified=(
            security.production_user_auth_verified
        ),
        persistent_workflow_checkpoints_verified=(
            not uses_memory_checkpoint
        ),
        blockers=tuple(blockers),
        message=(
            "Source-level checks found no listed blockers; "
            "live security and deployment review is still required."
            if ready
            else
            "Public deployment is blocked. "
            "Review the reported findings before release."
        ),
    )
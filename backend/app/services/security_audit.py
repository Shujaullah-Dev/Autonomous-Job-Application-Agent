
"""Day 24: Audit candidate API route protections.

Compatible with FastAPI's nested router structure.
"""

from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.api.routes.jobs import require_dev_write_key

try:
    from fastapi.routing import iter_route_contexts
except ImportError:
    # Compatibility with FastAPI versions before 0.137.2.
    iter_route_contexts = None


@dataclass(frozen=True)
class SecurityAudit:
    candidate_route_count: int
    dev_key_guarded_count: int
    routes_without_dev_key: tuple[str, ...]
    production_user_auth_verified: bool


def dependency_contains_dev_key(dependant) -> bool:
    """Recursively check the endpoint's dependencies."""

    if dependant.call is require_dev_write_key:
        return True

    return any(
        dependency_contains_dev_key(child)
        for child in dependant.dependencies
    )


def audit_candidate_routes(app: FastAPI) -> SecurityAudit:
    """Inspect registered candidate endpoints and their guards."""

    if iter_route_contexts is not None:
        routes = iter_route_contexts(app.routes)
    else:
        routes = iter(app.routes)

    candidate_count = 0
    protected_count = 0
    unprotected_routes = []

    for context in routes:
        # Newer FastAPI wraps the original APIRoute
        # in an effective route context.
        original_route = getattr(
            context,
            "original_route",
            context,
        )

        if not isinstance(original_route, APIRoute):
            continue

        # The effective path includes router prefixes.
        path = context.path

        if not path or not path.startswith(
            "/api/v1/candidates"
        ):
            continue

        candidate_count += 1

        # Inspect the effective dependency graph, which
        # includes inherited router-level dependencies.
        dependant = context.dependant

        if dependant is None:
            raise RuntimeError(
                f"Missing dependency information for {path}"
            )

        if dependency_contains_dev_key(dependant):
            protected_count += 1
            continue

        methods = ",".join(
            sorted(context.methods or [])
        )

        unprotected_routes.append(
            f"{methods} {path}"
        )

    if candidate_count == 0:
        raise RuntimeError(
            "Security audit discovered zero candidate routes. "
            "Verify FastAPI route context discovery."
        )

    return SecurityAudit(
        candidate_route_count=candidate_count,
        dev_key_guarded_count=protected_count,
        routes_without_dev_key=tuple(
            sorted(unprotected_routes)
        ),
        production_user_auth_verified=False,
    )

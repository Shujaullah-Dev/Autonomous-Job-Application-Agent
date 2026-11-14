
"""Statically audit Alembic upgrade and downgrade operations."""

import ast
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


@dataclass(frozen=True)
class MigrationFinding:
    code: str
    revision: str
    table: str
    message: str

@dataclass(frozen=True)
class MigrationReport:
    heads: tuple[str, ...]
    revision_count: int
    findings: tuple[MigrationFinding, ...]
    fresh_schema_safe: bool

def migration_operations(
    source: str,
    function_name: str,
) -> list[tuple[str, str]]:
    """Find literal op.create_table and op.drop_table calls."""

    tree = ast.parse(source)

    function = next(
        (
            node
            for node in tree.body
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            )
            and node.name == function_name
        ),
        None,
    )

    if function is None:
        return []

    result = []

    calls = sorted(
        (
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
        ),
        key=lambda node: node.lineno,
    )

    for call in calls:
        method = call.func

        if not isinstance(method, ast.Attribute):
            continue

        if not isinstance(method.value, ast.Name):
            continue

        if method.value.id != "op":
            continue

        if method.attr not in {"create_table", "drop_table"}:
            continue

        if not call.args:
            continue

        table_arg = call.args[0]

        if not isinstance(table_arg, ast.Constant):
            continue

        if not isinstance(table_arg.value, str):
            continue

        result.append(
            (method.attr, table_arg.value)
        )

    return result

def check_operation_history(
    revisions: list[tuple[str, str]],
) -> tuple[MigrationFinding, ...]:
    """Track tables as they are created and dropped in order."""

    existing_tables: dict[str, str] = {}
    findings: list[MigrationFinding] = []

    for revision, source in revisions:
        upgrades = migration_operations(source, "upgrade")
        downgrades = migration_operations(source, "downgrade")

        upgraded_tables = [
            table
            for action, table in upgrades
            if action == "create_table"
        ]

        downgraded_tables = {
            table
            for action, table in downgrades
            if action == "drop_table"
        }

        for action, table in upgrades:
            if action == "drop_table":
                existing_tables.pop(table, None)
                continue

            if table in existing_tables:
                findings.append(
                    MigrationFinding(
                        code="duplicate_table_creation",
                        revision=revision,
                        table=table,
                        message=(
                            "Table was already created in "
                            f"revision {existing_tables[table]}"
                        ),
                    )
                )
            else:
                existing_tables[table] = revision

        for table in upgraded_tables:
            if table not in downgraded_tables:
                findings.append(
                    MigrationFinding(
                        code="missing_table_downgrade",
                        revision=revision,
                        table=table,
                        message=(
                            "Upgrade creates this table but "
                            "downgrade does not drop it"
                        ),
                    )
                )

    return tuple(findings)

def audit_migrations(
    repository_root: Path,
) -> MigrationReport:
    """
    Inspect migrations only.

    This does not execute env.py, connect to PostgreSQL,
    apply upgrades or compare live schema definitions.
    """

    config_path = repository_root / "alembic.ini"
    config = Config(str(config_path))

    script = ScriptDirectory.from_config(config)
    heads = tuple(script.get_heads())

    # Alembic yields newest first; review from base to head.
    revisions = list(reversed(list(script.walk_revisions())))

    source_revisions = [
        (
            revision.revision,
            Path(revision.path).read_text(encoding="utf-8"),
        )
        for revision in revisions
    ]

    findings = list(
        check_operation_history(source_revisions)
    )

    if len(heads) != 1:
        findings.append(
            MigrationFinding(
                code="invalid_revision_heads",
                revision="graph",
                table="",
                message=(
                    f"Expected one Alembic head, found {len(heads)}"
                ),
            )
        )

    return MigrationReport(
        heads=heads,
        revision_count=len(revisions),
        findings=tuple(findings),
        fresh_schema_safe=not findings,
    )
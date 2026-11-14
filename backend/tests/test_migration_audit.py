
"""Tests for the static Alembic migration auditor."""

from pathlib import Path

from app.services.migration_audit import (
    audit_migrations,
    check_operation_history,
    migration_operations,
)

ROOT = Path(__file__).resolve().parents[2]

def test_extracts_upgrade_table_operations():
    source = '''
def upgrade():
    op.create_table("candidate_profiles")
    op.drop_table("temporary_table")
'''

    assert migration_operations(source, "upgrade") == [
        ("create_table", "candidate_profiles"),
        ("drop_table", "temporary_table"),
    ]

def test_duplicate_table_is_detected():
    first = '''
def upgrade():
    op.create_table("candidate_profiles")

def downgrade():
    op.drop_table("candidate_profiles")
'''

    second = '''
def upgrade():
    op.create_table("candidate_profiles")

def downgrade():
    op.drop_table("candidate_profiles")
'''

    findings = check_operation_history(
        [("revision_a", first), ("revision_b", second)]
    )

    duplicates = [
        item for item in findings
        if item.code == "duplicate_table_creation"
    ]

    assert len(duplicates) == 1
    assert duplicates[0].revision == "revision_b"
    assert duplicates[0].table == "candidate_profiles"

def test_incomplete_downgrade_is_detected():
    source = '''
def upgrade():
    op.create_table("applications")

def downgrade():
    pass
'''

    findings = check_operation_history(
        [("revision_a", source)]
    )

    assert any(
        item.code == "missing_table_downgrade"
        and item.table == "applications"
        for item in findings
    )

def test_correct_migration_pair_has_no_findings():
    source = '''
def upgrade():
    op.create_table("applications")

def downgrade():
    op.drop_table("applications")
'''

    findings = check_operation_history(
        [("revision_a", source)]
    )

    assert findings == ()

def test_repository_migration_graph_is_readable():
    report = audit_migrations(ROOT)

    assert report.revision_count > 0
    assert len(report.heads) >= 1
    assert report.fresh_schema_safe == (
        len(report.findings) == 0
    )
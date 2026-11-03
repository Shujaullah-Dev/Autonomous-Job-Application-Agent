
"""Add Day 8 job search fields and align candidate lengths.

Revision ID: d8e20261103
Revises: c1171134e5a3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8e20261103"
down_revision: str | Sequence[str] | None = "c1171134e5a3"

branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("work_mode", sa.String(16), nullable=True),
    )

    op.add_column(
        "jobs",
        sa.Column("salary_min", sa.Integer(), nullable=True),
    )

    op.add_column(
        "jobs",
        sa.Column("salary_max", sa.Integer(), nullable=True),
    )

    op.add_column(
        "jobs",
        sa.Column(
            "salary_currency", sa.String(3), nullable=True
        ),
    )

    op.add_column(
        "jobs",
        sa.Column(
            "posted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "jobs",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )

    op.create_check_constraint(
        "ck_jobs_salary_min_nonnegative",
        "jobs",
        "salary_min IS NULL OR salary_min >= 0",
    )

    op.create_check_constraint(
        "ck_jobs_salary_max_nonnegative",
        "jobs",
        "salary_max IS NULL OR salary_max >= 0",
    )

    op.create_check_constraint(
        "ck_jobs_salary_range",
        "jobs",
        "salary_min IS NULL OR salary_max IS NULL "
        "OR salary_max >= salary_min",
    )

    op.create_check_constraint(
        "ck_jobs_work_mode",
        "jobs",
        "work_mode IS NULL OR work_mode "
        "IN ('remote', 'hybrid', 'onsite')",
    )

    op.create_index(
        "ix_jobs_company_name",
        "jobs",
        ["company_name"],
    )

    op.create_index(
        "ix_jobs_work_mode",
        "jobs",
        ["work_mode"],
    )

    op.create_index(
        "ix_jobs_is_active",
        "jobs",
        ["is_active"],
    )

    # Align the candidate table's column lengths
    # with its existing SQLAlchemy model.
    for column, length, nullable in (
        ("full_name", 150, False),
        ("email", 320, False),
        ("phone", 30, True),
        ("location", 150, True),
    ):
        op.alter_column(
            "candidate_profiles",
            column,
            existing_type=sa.String(),
            type_=sa.String(length),
            existing_nullable=nullable,
        )


def downgrade() -> None:
    for column, length, nullable in (
        ("full_name", 150, False),
        ("email", 320, False),
        ("phone", 30, True),
        ("location", 150, True),
    ):
        op.alter_column(
            "candidate_profiles",
            column,
            existing_type=sa.String(length),
            type_=sa.String(),
            existing_nullable=nullable,
        )

    op.drop_index("ix_jobs_is_active", table_name="jobs")
    op.drop_index("ix_jobs_work_mode", table_name="jobs")
    op.drop_index("ix_jobs_company_name", table_name="jobs")

    op.drop_constraint(
        "ck_jobs_work_mode", "jobs", type_="check"
    )
    op.drop_constraint(
        "ck_jobs_salary_range", "jobs", type_="check"
    )
    op.drop_constraint(
        "ck_jobs_salary_max_nonnegative",
        "jobs",
        type_="check",
    )
    op.drop_constraint(
        "ck_jobs_salary_min_nonnegative",
        "jobs",
        type_="check",
    )

    op.drop_column("jobs", "is_active")
    op.drop_column("jobs", "posted_at")
    op.drop_column("jobs", "salary_currency")
    op.drop_column("jobs", "salary_max")
    op.drop_column("jobs", "salary_min")
    op.drop_column("jobs", "work_mode")

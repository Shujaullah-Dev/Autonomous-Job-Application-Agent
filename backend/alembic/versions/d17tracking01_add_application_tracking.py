
"""Add application tracking, revisions and status history.

Revision ID: d17tracking01
Revises: d12semantic01
"""

import sqlalchemy as sa
from alembic import op

revision = "d17tracking01"
down_revision = "d12semantic01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Uuid(),
            sa.ForeignKey(
                "candidate_profiles.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey("jobs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "workflow_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column(
            "job_title",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "company_name",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "job_url",
            sa.String(2048),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "current_revision",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "candidate_id",
            "job_id",
            name="uq_applications_candidate_job",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'draft', 'ready', 'submitted', 'interview', "
            "'offered', 'rejected', 'withdrawn')",
            name="ck_applications_status",
        ),
        sa.CheckConstraint(
            "current_revision >= 1",
            name="ck_applications_revision_positive",
        ),
    )

    op.create_index(
        "ix_applications_candidate_id",
        "applications",
        ["candidate_id"],
    )
    op.create_index(
        "ix_applications_job_id",
        "applications",
        ["job_id"],
    )

    op.create_table(
        "application_draft_revisions",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey(
                "applications.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "revision_number",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "cover_letter",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "resume_snapshot",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "application_id",
            "revision_number",
            name="uq_application_revision_number",
        ),
        sa.CheckConstraint(
            "revision_number >= 1",
            name="ck_application_revision_positive",
        ),
    )

    op.create_index(
        "ix_application_draft_revisions_application_id",
        "application_draft_revisions",
        ["application_id"],
    )

    op.create_table(
        "application_status_events",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey(
                "applications.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "previous_status",
            sa.String(20),
            nullable=True,
        ),
        sa.Column(
            "new_status",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "actor",
            sa.String(50),
            nullable=False,
        ),
        sa.Column(
            "note",
            sa.String(500),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_application_status_events_application_id",
        "application_status_events",
        ["application_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_application_status_events_application_id",
        table_name="application_status_events",
    )
    op.drop_table("application_status_events")

    op.drop_index(
        "ix_application_draft_revisions_application_id",
        table_name="application_draft_revisions",
    )
    op.drop_table("application_draft_revisions")

    op.drop_index(
        "ix_applications_job_id",
        table_name="applications",
    )
    op.drop_index(
        "ix_applications_candidate_id",
        table_name="applications",
    )
    op.drop_table("applications")

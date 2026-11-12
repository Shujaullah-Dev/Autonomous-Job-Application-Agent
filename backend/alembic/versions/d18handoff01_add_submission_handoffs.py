
"""Add prepared submission handoff audit records.

Revision ID: d18handoff01
Revises: d17tracking01
"""

import sqlalchemy as sa
from alembic import op

revision = "d18handoff01"
down_revision = "d17tracking01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "submission_handoffs",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
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
            "provider_hint",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "destination_url",
            sa.String(2048),
            nullable=False,
        ),
        sa.Column(
            "status",
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
            name="uq_submission_handoff_revision",
        ),
        sa.CheckConstraint(
            "revision_number >= 1",
            name="ck_submission_handoff_revision_positive",
        ),
        sa.CheckConstraint(
            "status = 'prepared'",
            name="ck_submission_handoff_prepared_only",
        ),
    )

    op.create_index(
        "ix_submission_handoffs_application_id",
        "submission_handoffs",
        ["application_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_submission_handoffs_application_id",
        table_name="submission_handoffs",
    )
    op.drop_table("submission_handoffs")

"""Add notification recovery audit records.

Revision ID: d21recover01
Revises: d20interview01
"""

import sqlalchemy as sa
from alembic import op

revision = "d21recover01"
down_revision = "d20interview01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_recovery_runs",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
        ),
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
            "scanned",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "released",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "cancelled",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "scanned >= 0 AND released >= 0 AND cancelled >= 0",
            name="ck_notification_recovery_counts",
        ),
    )

    op.create_index(
        "ix_notification_recovery_runs_candidate_id",
        "notification_recovery_runs",
        ["candidate_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_recovery_runs_candidate_id",
        table_name="notification_recovery_runs",
    )
    op.drop_table("notification_recovery_runs")

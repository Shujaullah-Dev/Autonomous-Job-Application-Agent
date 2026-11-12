"""Create interview scheduling and notification tables.

Revision ID: d20interview01
Revises: d19followup01
"""

import sqlalchemy as sa
from alembic import op

revision = "d20interview01"
down_revision = "d19followup01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey(
                "applications.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column(
            "starts_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "ends_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column(
            "location_or_link",
            sa.String(500),
            nullable=True,
        ),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(
            "status IN ('scheduled', 'completed', 'cancelled')",
            name="ck_interview_status",
        ),
        sa.CheckConstraint(
            "mode IN ('video', 'phone', 'onsite')",
            name="ck_interview_mode",
        ),
        sa.CheckConstraint(
            "ends_at > starts_at",
            name="ck_interview_valid_interval",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_interview_version",
        ),
    )

    op.create_index(
        "ix_interviews_application_id",
        "interviews",
        ["application_id"],
    )
    op.create_index(
        "ix_interviews_starts_at",
        "interviews",
        ["starts_at"],
    )

    op.create_table(
        "interview_notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "interview_id",
            sa.Uuid(),
            sa.ForeignKey(
                "interviews.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "minutes_before",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "due_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "interview_id",
            "minutes_before",
            name="uq_interview_notification_offset",
        ),
        sa.CheckConstraint(
            "minutes_before IN (0, 60, 1440)",
            name="ck_interview_notification_offset",
        ),
        sa.CheckConstraint(
            "state IN ("
            "'scheduled', 'available', 'read', 'cancelled')",
            name="ck_interview_notification_state",
        ),
    )

    op.create_index(
        "ix_interview_notifications_interview_id",
        "interview_notifications",
        ["interview_id"],
    )
    op.create_index(
        "ix_interview_notifications_due_at",
        "interview_notifications",
        ["due_at"],
    )
    op.create_index(
        "ix_interview_notifications_state",
        "interview_notifications",
        ["state"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_interview_notifications_state",
        table_name="interview_notifications",
    )
    op.drop_index(
        "ix_interview_notifications_due_at",
        table_name="interview_notifications",
    )
    op.drop_index(
        "ix_interview_notifications_interview_id",
        table_name="interview_notifications",
    )
    op.drop_table("interview_notifications")

    op.drop_index(
        "ix_interviews_starts_at",
        table_name="interviews",
    )
    op.drop_index(
        "ix_interviews_application_id",
        table_name="interviews",
    )
    op.drop_table("interviews")
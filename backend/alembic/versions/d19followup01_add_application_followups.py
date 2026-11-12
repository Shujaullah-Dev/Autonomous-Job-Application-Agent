
"""Add application follow-ups and audit events.

Revision ID: d19followup01
Revises: d18handoff01
"""

import sqlalchemy as sa
from alembic import op

revision = "d19followup01"
down_revision = "d18handoff01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_follow_ups",
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
            "kind",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "due_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "state",
            sa.String(20),
            nullable=False,
        ),
        sa.Column(
            "note",
            sa.String(500),
            nullable=True,
        ),
        sa.Column(
            "resolution_note",
            sa.String(500),
            nullable=True,
        ),
        sa.Column(
            "resolved_at",
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
            "application_id",
            "kind",
            "due_at",
            name="uq_follow_up_application_kind_due",
        ),
        sa.CheckConstraint(
            "kind IN ('status_check', 'follow_up')",
            name="ck_follow_up_kind",
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'completed', 'dismissed')",
            name="ck_follow_up_state",
        ),
    )

    op.create_index(
        "ix_application_follow_ups_application_id",
        "application_follow_ups",
        ["application_id"],
    )

    op.create_index(
        "ix_application_follow_ups_due_at",
        "application_follow_ups",
        ["due_at"],
    )

    op.create_index(
        "ix_application_follow_ups_state",
        "application_follow_ups",
        ["state"],
    )

    op.create_table(
        "application_follow_up_events",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "follow_up_id",
            sa.Uuid(),
            sa.ForeignKey(
                "application_follow_ups.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "event_type",
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
        sa.CheckConstraint(
            "event_type IN ("
            "'created', 'completed', 'dismissed', 'auto_closed')",
            name="ck_follow_up_event_type",
        ),
    )

    op.create_index(
        "ix_application_follow_up_events_follow_up_id",
        "application_follow_up_events",
        ["follow_up_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_application_follow_up_events_follow_up_id",
        table_name="application_follow_up_events",
    )
    op.drop_table("application_follow_up_events")

    op.drop_index(
        "ix_application_follow_ups_state",
        table_name="application_follow_ups",
    )
    op.drop_index(
        "ix_application_follow_ups_due_at",
        table_name="application_follow_ups",
    )
    op.drop_index(
        "ix_application_follow_ups_application_id",
        table_name="application_follow_ups",
    )
    op.drop_table("application_follow_ups")

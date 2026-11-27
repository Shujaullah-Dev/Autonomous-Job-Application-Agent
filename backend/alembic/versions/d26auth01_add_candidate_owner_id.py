"""Add verified account ownership to candidate profiles.

Revision ID: d26auth01
Revises: d21recover01
"""

import sqlalchemy as sa
from alembic import op

revision = "d26auth01"
down_revision = "d21recover01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column("owner_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_candidate_profiles_owner_id",
        "candidate_profiles",
        ["owner_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_candidate_profiles_owner_id",
        table_name="candidate_profiles",
    )
    op.drop_column("candidate_profiles", "owner_id")

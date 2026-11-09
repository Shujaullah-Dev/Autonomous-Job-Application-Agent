
"""Add job embedding storage for Day 12.

Revision ID: d12semantic01
Revises: 91d44bafc0b0
"""

import sqlalchemy as sa
from alembic import op
from app.models.job_embedding import SupabaseVector

revision = "d12semantic01"
down_revision = "91d44bafc0b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_embeddings",
        sa.Column(
            "job_id",
            sa.Integer(),
            sa.ForeignKey(
                "jobs.id",
                ondelete="CASCADE",
            ),
            primary_key=True,
        ),
        sa.Column(
            "model_name",
            sa.String(160),
            nullable=False,
        ),
        sa.Column(
            "content_hash",
            sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "embedding",
            SupabaseVector(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_job_embeddings_model_name",
        "job_embeddings",
        ["model_name"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_job_embeddings_model_name",
        table_name="job_embeddings",
    )

    op.drop_table("job_embeddings")

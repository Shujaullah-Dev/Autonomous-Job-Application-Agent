"""add multi source job identity

Revision ID: 91d44bafc0b0
Revises: d8e20261103
Create Date: 2026-11-05 20:42:58.383324

"""

from alembic import op
import sqlalchemy as sa

from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)


revision = "91d44bafc0b0"
down_revision = "d8e20261103"
branch_labels = None
depends_on = None


def canonicalize_url(value: str) -> str:
    parts = urlsplit(value)

    if parts.scheme.lower() not in {"http", "https"}:
        raise ValueError("Unsupported URL scheme")

    host = (parts.hostname or "").lower()

    if not host:
        raise ValueError("Missing URL hostname")

    port = parts.port

    if port and not (
        (parts.scheme.lower() == "https" and port == 443)
        or (parts.scheme.lower() == "http" and port == 80)
    ):
        host = f"{host}:{port}"

    ignored = {
        "gclid",
        "fbclid",
        "ref",
        "source",
    }

    query = [
        (key, value)
        for key, value in parse_qsl(
            parts.query,
            keep_blank_values=True,
        )
        if not (
            key.lower().startswith("utm_")
            or key.lower() in ignored
        )
    ]

    query.sort()

    path = parts.path.rstrip("/") or "/"

    return urlunsplit(
        (
            parts.scheme.lower(),
            host,
            path,
            urlencode(query),
            "",
        )
    )


def upgrade():
    op.add_column(
        "jobs",
        sa.Column(
            "source_job_id",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.add_column(
        "jobs",
        sa.Column(
            "canonical_url",
            sa.String(length=2048),
            nullable=True,
        ),
    )

    connection = op.get_bind()

    rows = connection.execute(
        sa.text(
            "SELECT id, job_url FROM jobs ORDER BY id"
        )
    ).fetchall()

    seen = set()

    # Backfill old jobs while safely handling
    # URLs that canonicalize to the same value.
    for row in rows:
        try:
            canonical = canonicalize_url(row.job_url)
        except (ValueError, TypeError):
            continue

        if canonical in seen:
            continue

        seen.add(canonical)

        connection.execute(
            sa.text(
                """
                UPDATE jobs
                SET canonical_url = :canonical
                WHERE id = :job_id
                """
            ),
            {
                "canonical": canonical,
                "job_id": row.id,
            },
        )

    op.create_index(
        "ix_jobs_canonical_url",
        "jobs",
        ["canonical_url"],
        unique=True,
    )

    op.create_unique_constraint(
        "uq_jobs_source_source_job_id",
        "jobs",
        ["source", "source_job_id"],
    )


def downgrade():
    op.drop_constraint(
        "uq_jobs_source_source_job_id",
        "jobs",
        type_="unique",
    )

    op.drop_index(
        "ix_jobs_canonical_url",
        table_name="jobs",
    )

    op.drop_column(
        "jobs",
        "canonical_url",
    )

    op.drop_column(
        "jobs",
        "source_job_id",
    )
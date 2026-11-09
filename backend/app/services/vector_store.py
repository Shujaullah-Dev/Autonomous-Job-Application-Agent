
"""Persist and query embeddings using Supabase pgvector."""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.job_embedding import JobEmbedding
from app.services.semantic_embeddings import (
    DIMENSIONS,
    MODEL_NAME,
    document_hash,
    job_document,
)


@dataclass(frozen=True)
class PendingJob:
    job_id: int
    document: str
    content_hash: str


@dataclass(frozen=True)
class ScanResult:
    scanned: int
    unchanged: int
    last_job_id: int
    pending: list[PendingJob]


def scan_jobs(
    db: Session,
    *,
    limit: int = 100,
    after_id: int = 0,
) -> ScanResult:
    """Find active jobs needing new or refreshed embeddings."""

    rows = db.execute(
        select(
            Job,
            JobEmbedding.content_hash,
            JobEmbedding.model_name,
            JobEmbedding.updated_at,
        )
        .outerjoin(
            JobEmbedding,
            JobEmbedding.job_id == Job.id,
        )
        .where(
            Job.is_active.is_(True),
            Job.id > after_id,
        )
        .order_by(Job.id)
        .limit(limit)
    ).all()

    pending: list[PendingJob] = []

    for job, stored_hash, stored_model, stored_at in rows:
        document = job_document(
            title=job.title,
            description=job.description,
            location=job.location,
            work_mode=job.work_mode,
        )

        digest = document_hash(document)

        stale = job.updated_at is not None and (
            stored_at is None
            or stored_at < job.updated_at
        )

        if (
            stored_hash != digest
            or stored_model != MODEL_NAME
            or stale
        ):
            pending.append(
                PendingJob(
                    job_id=job.id,
                    document=document,
                    content_hash=digest,
                )
            )

    return ScanResult(
        scanned=len(rows),
        unchanged=len(rows) - len(pending),
        last_job_id=(
            rows[-1][0].id
            if rows
            else after_id
        ),
        pending=pending,
    )


def _vector_literal(
    vector: Sequence[float],
) -> str:
    """Validate and serialize a vector for a bound SQL parameter."""

    if (
        len(vector) != DIMENSIONS
        or any(
            not math.isfinite(float(number))
            for number in vector
        )
    ):
        raise ValueError(
            "Vector must contain 384 finite values"
        )

    if not any(float(number) != 0 for number in vector):
        raise ValueError(
            "A zero vector has undefined cosine similarity"
        )

    return (
        "["
        + ",".join(
            format(float(number), ".9g")
            for number in vector
        )
        + "]"
    )


def store_embeddings(
    db: Session,
    items: Sequence[
        tuple[PendingJob, Sequence[float]]
    ],
) -> None:
    """Upsert vectors; caller controls transaction commits."""

    for pending, vector in items:
        literal = _vector_literal(vector)

        if (
            db.bind is not None
            and db.bind.dialect.name == "sqlite"
        ):
            # Test-only fallback. SQLite cannot search vectors.
            db.merge(
                JobEmbedding(
                    job_id=pending.job_id,
                    model_name=MODEL_NAME,
                    content_hash=pending.content_hash,
                    embedding=literal,
                )
            )
        else:
            db.execute(
                text(
                    """
                    INSERT INTO public.job_embeddings
                        (
                            job_id,
                            model_name,
                            content_hash,
                            embedding,
                            updated_at
                        )
                    VALUES
                        (
                            :job_id,
                            :model_name,
                            :content_hash,
                            CAST(
                                :embedding_text
                                AS extensions.vector(384)
                            ),
                            NOW()
                        )
                    ON CONFLICT (job_id)
                    DO UPDATE SET
                        model_name = EXCLUDED.model_name,
                        content_hash = EXCLUDED.content_hash,
                        embedding = EXCLUDED.embedding,
                        updated_at = NOW()
                    """
                ),
                {
                    "job_id": pending.job_id,
                    "model_name": MODEL_NAME,
                    "content_hash": pending.content_hash,
                    "embedding_text": literal,
                },
            )


def nearest_job_similarities(
    db: Session,
    *,
    job_ids: Sequence[int],
    query_vector: Sequence[float],
) -> dict[int, float]:
    """Return cosine similarities for the evaluated job pool."""

    if not job_ids:
        return {}

    if (
        db.bind is None
        or db.bind.dialect.name != "postgresql"
    ):
        raise RuntimeError(
            "Semantic vector search requires PostgreSQL"
        )

    statement = text(
        """
        SELECT
            e.job_id,
            1.0 - (
                e.embedding OPERATOR(extensions.<=>)
                CAST(
                    :query_vector AS extensions.vector(384)
                )
            ) AS similarity
        FROM public.job_embeddings AS e
        JOIN public.jobs AS j
            ON j.id = e.job_id
        WHERE e.model_name = :model_name
          AND j.is_active = TRUE
          AND e.updated_at >= j.updated_at
          AND e.job_id IN :job_ids
        ORDER BY
            e.embedding OPERATOR(extensions.<=>)
            CAST(
                :query_vector AS extensions.vector(384)
            ) ASC
        LIMIT :max_results
        """
    ).bindparams(
        bindparam("job_ids", expanding=True)
    )

    rows = db.execute(
        statement,
        {
            "query_vector": _vector_literal(query_vector),
            "model_name": MODEL_NAME,
            "job_ids": list(job_ids),
            "max_results": len(job_ids),
        },
    ).all()

    return {
        int(job_id): float(similarity)
        for job_id, similarity in rows
        if (
            similarity is not None
            and math.isfinite(float(similarity))
        )
    }

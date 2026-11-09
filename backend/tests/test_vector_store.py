
import pytest
from app.db.base import Base
from app.models.job import Job
from app.models.job_embedding import JobEmbedding
from app.services.vector_store import (
    scan_jobs,
    store_embeddings,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    try:
        with Session(engine) as session:
            yield session

    finally:
        engine.dispose()


def create_job(db):
    job = Job(
        title="Backend Engineer",
        company_name="Example Technologies",
        location="Remote",
        description="Build APIs using Python and FastAPI",
        job_url="https://example.com/jobs/100",
        work_mode="remote",
        is_active=True,
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    return job


def fake_vector():
    return [1.0] + [0.0] * 383


def test_new_job_requires_embedding(db):
    job = create_job(db)

    result = scan_jobs(db)

    assert result.scanned == 1
    assert len(result.pending) == 1
    assert result.pending[0].job_id == job.id


def test_store_embedding_and_skip_unchanged(db):
    job = create_job(db)

    scan = scan_jobs(db)

    store_embeddings(
        db,
        [
            (
                scan.pending[0],
                fake_vector(),
            )
        ],
    )
    db.commit()

    stored = db.get(JobEmbedding, job.id)

    assert stored is not None
    assert stored.content_hash == (
        scan.pending[0].content_hash
    )

    second_scan = scan_jobs(db)

    assert second_scan.unchanged == 1
    assert second_scan.pending == []


def test_modified_job_requires_refresh(db):
    job = create_job(db)

    scan = scan_jobs(db)

    store_embeddings(
        db,
        [(scan.pending[0], fake_vector())],
    )
    db.commit()

    job.description = (
        "Build Python APIs and manage Docker deployments"
    )
    db.commit()

    refreshed = scan_jobs(db)

    assert len(refreshed.pending) == 1


def test_invalid_vector_length_rejected(db):
    create_job(db)

    scan = scan_jobs(db)

    with pytest.raises(ValueError):
        store_embeddings(
            db,
            [
                (
                    scan.pending[0],
                    [0.5, 0.5],
                )
            ],
        )

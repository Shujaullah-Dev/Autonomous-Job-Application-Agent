
import pytest
from app.models.job import Job
from app.schemas.job import JobCreate
from app.services.job_ingestion import ingest_jobs
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Job.__table__.create(engine)

    try:
        with Session(engine) as session:
            yield session

    finally:
        engine.dispose()


def sample_job(
    url="https://example.com/jobs/100",
    description="Build Python APIs",
    source="greenhouse:demo",
    source_job_id="101",
    title="Backend Developer",
):
    return JobCreate(
        title=title,
        company_name="Demo Technologies",
        location="Remote",
        description=description,
        job_url=url,
        source=source,
        source_job_id=source_job_id,
        work_mode="remote",
    )


def count_jobs(db):
    return db.scalar(
        select(func.count()).select_from(Job)
    )


def test_dry_run_does_not_insert(db):
    result = ingest_jobs(
        db,
        [sample_job()],
    )

    assert result.applied is False
    assert result.created == 1
    assert count_jobs(db) == 0


def test_first_import_creates_job(db):
    result = ingest_jobs(
        db,
        [sample_job()],
        apply=True,
    )

    assert result.created == 1
    assert result.updated == 0
    assert count_jobs(db) == 1


def test_second_import_is_idempotent(db):
    jobs = [sample_job()]

    ingest_jobs(db, jobs, apply=True)
    result = ingest_jobs(db, jobs, apply=True)

    assert result.created == 0
    assert result.updated == 0
    assert result.unchanged == 1
    assert count_jobs(db) == 1


def test_changed_description_updates_job(db):
    ingest_jobs(
        db,
        [sample_job()],
        apply=True,
    )

    result = ingest_jobs(
        db,
        [sample_job(description="Updated role")],
        apply=True,
    )

    assert result.updated == 1

    job = db.scalar(select(Job))

    assert job.description == "Updated role"


def test_multiple_jobs_are_inserted(db):
    jobs = [
        sample_job(
            url="https://example.com/jobs/100"
        ),
        sample_job(
            url="https://example.com/jobs/200",
            source_job_id="200",
            title="Platform Engineer",
        ),
    ]

    result = ingest_jobs(
        db,
        jobs,
        apply=True,
    )

    assert result.created == 2
    assert count_jobs(db) == 2


def test_other_source_is_preserved(db):
    manual = Job(
        title="Original Title",
        company_name="Manual Company",
        description="Original description",
        job_url="https://example.com/jobs/100",
        source="manual",
    )

    db.add(manual)
    db.commit()

    result = ingest_jobs(
        db,
        [sample_job()],
        apply=True,
    )

    assert result.skipped == 1
    assert result.updated == 0

    stored = db.scalar(select(Job))

    assert stored.title == "Original Title"
    assert stored.source == "manual"


def test_duplicate_input_urls_rejected(db):
    jobs = [
        sample_job(),
        sample_job(),
    ]

    with pytest.raises(ValueError):
        ingest_jobs(
            db,
            jobs,
            apply=True,
        )

    assert count_jobs(db) == 0


def test_inactive_job_reactivated(db):
    ingest_jobs(
        db,
        [sample_job()],
        apply=True,
    )

    stored = db.scalar(select(Job))
    stored.is_active = False
    db.commit()

    result = ingest_jobs(
        db,
        [sample_job()],
        apply=True,
    )

    assert result.updated == 1

    db.refresh(stored)
    assert stored.is_active is True


def test_cross_source_duplicate_is_skipped(db):
    ingest_jobs(
        db,
        [
            sample_job(
                source="greenhouse:demo",
            )
        ],
        apply=True,
    )

    incoming = sample_job(
        url="https://different.com/jobs/101",
        source="lever:demo",
    )

    result = ingest_jobs(
        db,
        [incoming],
        apply=True,
    )

    assert result.created == 0
    assert result.possible_duplicates == 1
    assert result.skipped == 1
    assert count_jobs(db) == 1


def test_tracking_url_does_not_create_duplicate(db):
    first = sample_job(
        url="https://example.com/jobs/101"
    )

    second = sample_job(
        url=(
            "https://example.com/jobs/101"
            "?utm_source=linkedin"
        )
    )

    ingest_jobs(
        db,
        [first],
        apply=True,
    )

    result = ingest_jobs(
        db,
        [second],
        apply=True,
    )

    assert result.created == 0
    assert result.unchanged == 1
    assert count_jobs(db) == 1


def test_provider_id_identifies_existing_job(db):
    first = sample_job(
        url="https://example.com/jobs/101"
    )

    ingest_jobs(
        db,
        [first],
        apply=True,
    )

    updated = sample_job(
        url="https://example.com/jobs/101-updated",
        description="Updated description",
    )

    result = ingest_jobs(
        db,
        [updated],
        apply=True,
    )

    assert result.created == 0
    assert result.updated == 1
    assert count_jobs(db) == 1
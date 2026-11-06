
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.job import Job
from app.schemas.job import JobCreate

from app.services.job_deduplication import (
    canonicalize_url,
    job_fingerprint,
    find_possible_duplicate,
)


def test_remove_tracking_parameters():

    url = (
        "https://example.com/jobs/123"
        "?utm_source=linkedin"
    )

    result = canonicalize_url(url)

    assert result == (
        "https://example.com/jobs/123"
    )


def test_remove_url_fragment():

    result = canonicalize_url(
        "https://example.com/jobs/123#apply"
    )

    assert result == (
        "https://example.com/jobs/123"
    )


def test_remove_trailing_slash():

    result = canonicalize_url(
        "https://example.com/jobs/123/"
    )

    assert result == (
        "https://example.com/jobs/123"
    )


def test_preserve_meaningful_query():

    result = canonicalize_url(
        "https://example.com/jobs?id=123"
    )

    assert result == (
        "https://example.com/jobs?id=123"
    )


def test_fingerprint_normalization():

    first = job_fingerprint(
        "ABC Technologies",
        "Python Developer",
        "Remote",
    )

    second = job_fingerprint(
        "abc technologies",
        " python developer ",
        " remote ",
    )

    assert first == second


def test_different_companies_have_different_fingerprints():

    first = job_fingerprint(
        "ABC Technologies",
        "Python Developer",
        "Remote",
    )

    second = job_fingerprint(
        "XYZ Technologies",
        "Python Developer",
        "Remote",
    )

    assert first != second


def test_find_possible_duplicate():

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    Job.__table__.create(engine)

    try:
        with Session(engine) as db:

            existing = Job(
                title="Python Developer",
                company_name="ABC Technologies",
                location="Remote",
                description="Build APIs",
                job_url=(
                    "https://example.com/jobs/1"
                ),
                canonical_url=(
                    "https://example.com/jobs/1"
                ),
                source="greenhouse:abc",
                source_job_id="101",
                is_active=True,
            )

            db.add(existing)
            db.commit()

            incoming = JobCreate(
                title="Python Developer",
                company_name="ABC Technologies",
                location="Remote",
                description="Develop APIs",
                job_url=(
                    "https://another-example.com/jobs/2"
                ),
                source="lever:abc",
                source_job_id="201",
            )

            result = find_possible_duplicate(
                db,
                incoming,
            )

            assert result is not None
            assert result.title == "Python Developer"

    finally:
        engine.dispose()
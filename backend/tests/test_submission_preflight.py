
"""Preflight validation tests."""

import uuid

import pytest
from app.db.base import Base
from app.models.application import (
    Application,
    ApplicationDraftRevision,
)
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.services.submission_preflight import (
    evaluate_submission_preflight,
    identify_provider,
    safe_external_url,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def preflight_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        candidate = CandidateProfile(
            id=uuid.uuid4(),
            full_name="Test Candidate",
            email="preflight@example.test",
        )

        job = Job(
            title="Python Developer",
            company_name="Acme",
            description="Build Python APIs.",
            job_url="https://jobs.lever.co/acme/12345",
            source="lever:acme",
            work_mode=None,
            is_active=True,
        )

        db.add_all([candidate, job])
        db.flush()

        application = Application(
            candidate_id=candidate.id,
            job_id=job.id,
            workflow_id=uuid.uuid4(),
            job_title=job.title,
            company_name=job.company_name,
            job_url=job.job_url,
            status="ready",
            current_revision=1,
        )

        db.add(application)
        db.flush()

        db.add(
            ApplicationDraftRevision(
                application_id=application.id,
                revision_number=1,
                cover_letter="Dear Hiring Team, I am interested.",
                resume_snapshot={
                    "candidate_name": "Test Candidate",
                    "candidate_email": "preflight@example.test",
                    "relevant_skills": ["Python"],
                    "experiences": [],
                    "educations": [],
                },
                source="generated",
            )
        )
        db.commit()

        try:
            yield db, application.id, job.id
        finally:
            db.rollback()

    engine.dispose()


def get_report(db, application_id):
    application = db.get(Application, application_id)
    return evaluate_submission_preflight(db, application)


def test_valid_ready_application(preflight_db):
    db, application_id, _ = preflight_db

    report = get_report(db, application_id)

    assert report.can_handoff is True
    assert report.provider_hint == "lever"
    assert report.destination_url is not None
    assert all(item.passed for item in report.checks)


def test_draft_status_blocks_handoff(preflight_db):
    db, application_id, _ = preflight_db

    application = db.get(Application, application_id)
    application.status = "draft"
    db.flush()

    report = get_report(db, application_id)

    assert report.can_handoff is False
    assert report.destination_url is None
    assert any(
        item.code == "application_ready" and not item.passed
        for item in report.checks
    )


def test_inactive_job_blocks_handoff(preflight_db):
    db, application_id, job_id = preflight_db

    job = db.get(Job, job_id)
    job.is_active = False
    db.flush()

    report = get_report(db, application_id)

    assert report.can_handoff is False
    assert any(
        item.code == "job_active" and not item.passed
        for item in report.checks
    )


def test_changed_job_title_blocks_handoff(preflight_db):
    db, application_id, job_id = preflight_db

    job = db.get(Job, job_id)
    job.title = "Different Position"
    db.flush()

    report = get_report(db, application_id)

    assert report.can_handoff is False


def test_missing_revision_blocks_handoff(preflight_db):
    db, application_id, _ = preflight_db

    application = db.get(Application, application_id)
    application.current_revision = 99
    db.flush()

    report = get_report(db, application_id)

    assert report.can_handoff is False
    assert any(
        item.code == "saved_draft_exists"
        and not item.passed
        for item in report.checks
    )


def test_unknown_work_mode_is_warning(preflight_db):
    db, application_id, _ = preflight_db

    report = get_report(db, application_id)

    assert report.can_handoff is True
    assert any(
        "Work mode is unknown" in warning
        for warning in report.warnings
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://jobs.lever.co/acme/123",
        "https://localhost/apply",
        "https://127.0.0.1/apply",
        "https://example.com/jobs/123",
        "https://jobs.example.test/jobs/123",
        "https://user:pass@jobs.lever.co/acme/123",
        "https://jobs.lever.co:8443/acme/123",
        "javascript:alert(1)",
    ],
)
def test_unsafe_urls_are_rejected(url):
    assert safe_external_url(url) is False


def test_valid_employer_urls():
    assert safe_external_url(
        "https://jobs.lever.co/acme/123"
    )
    assert safe_external_url(
        "https://job-boards.greenhouse.io/acme/jobs/123"
    )
    assert safe_external_url(
        "https://careers.acmecorp.com/job/123"
    )


def test_provider_identification():
    assert identify_provider("lever:acme") == "lever"
    assert identify_provider("greenhouse:acme") == "greenhouse"
    assert identify_provider("manual") == "external"


def test_demo_source_blocks_handoff(preflight_db):
    db, application_id, job_id = preflight_db

    job = db.get(Job, job_id)
    job.source = "lever:leverdemo"
    db.flush()

    report = get_report(db, application_id)

    assert report.can_handoff is False
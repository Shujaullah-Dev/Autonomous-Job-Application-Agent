
"""Recovery service tests with a disposable SQLite database."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from app.db.base import Base
from app.models.application import Application
from app.models.candidate import CandidateProfile
from app.models.interview import Interview, InterviewNotification
from app.models.job import Job
from app.models.notification_recovery import NotificationRecoveryRun
from app.services.notification_recovery import (
    RecoveryCandidateNotFound,
    reconcile_notifications,
)
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

NOW = datetime(2030, 1, 1, 12, tzinfo=UTC)


@pytest.fixture
def recovery_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)
    candidate_id = uuid.uuid4()

    with Session(engine) as db:
        candidate = CandidateProfile(
            id=candidate_id,
            full_name="Recovery Test Candidate",
            email="recovery@example.test",
        )

        job = Job(
            title="Python Developer",
            company_name="Test Company",
            description="Python API development",
            job_url="https://company.test/jobs/recovery",
            source="greenhouse:testcompany",
            is_active=True,
        )

        db.add_all([candidate, job])
        db.flush()

        application = Application(
            candidate_id=candidate_id,
            job_id=job.id,
            workflow_id=uuid.uuid4(),
            job_title=job.title,
            company_name=job.company_name,
            job_url=job.job_url,
            status="interview",
            current_revision=1,
        )

        db.add(application)
        db.flush()

        active_interview = Interview(
            application_id=application.id,
            title="Upcoming Interview",
            starts_at=NOW + timedelta(hours=2),
            ends_at=NOW + timedelta(hours=3),
            mode="video",
            status="scheduled",
            version=1,
        )

        expired_interview = Interview(
            application_id=application.id,
            title="Expired Interview",
            starts_at=NOW - timedelta(days=2),
            ends_at=NOW - timedelta(days=2, hours=-1),
            mode="video",
            status="scheduled",
            version=1,
        )

        db.add_all([active_interview, expired_interview])
        db.flush()

        recoverable = InterviewNotification(
            interview_id=active_interview.id,
            minutes_before=60,
            due_at=NOW - timedelta(minutes=1),
            state="scheduled",
        )

        stale = InterviewNotification(
            interview_id=expired_interview.id,
            minutes_before=60,
            due_at=NOW - timedelta(days=3),
            state="scheduled",
        )

        already_read = InterviewNotification(
            interview_id=active_interview.id,
            minutes_before=0,
            due_at=NOW - timedelta(minutes=5),
            state="read",
            read_at=NOW - timedelta(minutes=4),
        )

        db.add_all([recoverable, stale, already_read])
        db.commit()

        ids = {
            "recoverable": recoverable.id,
            "stale": stale.id,
            "read": already_read.id,
        }

    try:
        with Session(engine) as db:
            yield db, candidate_id, ids
    finally:
        engine.dispose()


def test_preview_never_changes_database(recovery_db):
    db, candidate_id, ids = recovery_db

    report = reconcile_notifications(
        db,
        candidate_id=candidate_id,
        dry_run=True,
        now=NOW,
    )

    assert report.scanned == 2
    assert report.released == 1
    assert report.cancelled == 1
    assert report.run_id is None

    assert db.get(
        InterviewNotification, ids["recoverable"]
    ).state == "scheduled"


def test_recovery_is_idempotent(recovery_db):
    db, candidate_id, ids = recovery_db

    first = reconcile_notifications(
        db,
        candidate_id=candidate_id,
        dry_run=False,
        now=NOW,
    )

    assert first.released == 1
    assert first.cancelled == 1
    assert first.run_id is not None

    assert db.get(
        InterviewNotification, ids["recoverable"]
    ).state == "available"

    assert db.get(
        InterviewNotification, ids["stale"]
    ).state == "cancelled"

    assert db.get(
        InterviewNotification, ids["read"]
    ).state == "read"

    second = reconcile_notifications(
        db,
        candidate_id=candidate_id,
        dry_run=False,
        now=NOW,
    )

    assert second.released == 0
    assert second.cancelled == 0
    assert second.run_id is None

    assert db.scalar(
        select(func.count(NotificationRecoveryRun.id))
    ) == 1


def test_unknown_candidate_rejected(recovery_db):
    db, _, _ = recovery_db

    with pytest.raises(RecoveryCandidateNotFound):
        reconcile_notifications(
            db,
            candidate_id=uuid.uuid4(),
            dry_run=True,
            now=NOW,
        )


def test_invalid_limit_rejected(recovery_db):
    db, candidate_id, _ = recovery_db

    with pytest.raises(ValueError):
        reconcile_notifications(
            db,
            candidate_id=candidate_id,
            dry_run=True,
            limit=0,
            now=NOW,
        )

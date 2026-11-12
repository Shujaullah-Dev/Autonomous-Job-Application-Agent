"""Interview scheduling and notification tests."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from app.db.base import Base
from app.models.application import Application
from app.models.candidate import CandidateProfile
from app.models.interview import InterviewNotification
from app.models.job import Job
from app.services.application_tracking import (
    change_application_status,
    create_tracked_application,
)
from app.services.interview_scheduling import (
    InterviewConflict,
    create_interview,
    finish_interview,
    mark_notification_read,
    publish_due_notifications,
    reschedule_interview,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

UTC = timezone.utc  # noqa: UP017

NOW = datetime(2030, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture
def interview_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    candidate_id = uuid.uuid4()

    with Session(engine) as db:
        db.add(
            CandidateProfile(
                id=candidate_id,
                full_name="Interview Tester",
                email="interview@example.test",
            )
        )

        job = Job(
            title="Python Developer",
            company_name="Example Employer",
            description="Python backend development",
            job_url="https://company.test/jobs/interview",
            source="greenhouse:example",
            is_active=True,
        )
        db.add(job)
        db.commit()

        application = create_tracked_application(
            db,
            candidate_id=candidate_id,
            workflow_id=uuid.uuid4(),
            job_id=job.id,
            job_title=job.title,
            company_name=job.company_name,
            job_url=job.job_url,
            cover_letter="Dear Hiring Team, I am interested.",
            resume_snapshot={
                "candidate_name": "Interview Tester",
                "candidate_email": "interview@example.test",
                "relevant_skills": ["Python"],
                "experiences": [],
                "educations": [],
            },
        )

        application_id = application.id

        change_application_status(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            new_status="ready",
            confirm_reviewed=True,
        )
        change_application_status(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            new_status="submitted",
            confirm_external_submission=True,
        )
        change_application_status(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            new_status="interview",
        )

    try:
        with Session(engine) as db:
            yield db, candidate_id, application_id
    finally:
        engine.dispose()


def make_interview(db, candidate_id, application_id, **changes):
    data = {
        "candidate_id": candidate_id,
        "application_id": application_id,
        "title": "Technical Interview",
        "starts_at": NOW + timedelta(days=2),
        "ends_at": NOW + timedelta(days=2, hours=1),
        "mode": "video",
        "location_or_link": "https://meet.example.org/room",
        "now": NOW,
    }
    data.update(changes)
    return create_interview(db, **data)


def test_create_interview_and_two_reminders(interview_db):
    db, candidate_id, application_id = interview_db
    interview = make_interview(db, candidate_id, application_id)

    assert interview.status == "scheduled"
    assert interview.version == 1

    reminders = db.scalars(
        select(InterviewNotification).where(
            InterviewNotification.interview_id == interview.id
        )
    ).all()

    assert len(reminders) == 2
    assert {r.minutes_before for r in reminders} == {60, 1440}
    assert all(r.state == "scheduled" for r in reminders)


def test_timezone_converts_to_utc(interview_db):
    db, candidate_id, application_id = interview_db

    start = datetime(
        2030, 1, 3, 17, 0,
        tzinfo=timezone(timedelta(hours=5)),
    )

    interview = make_interview(
        db, candidate_id, application_id,
        starts_at=start,
        ends_at=start + timedelta(hours=1),
    )

    stored = interview.starts_at.replace(tzinfo=UTC)
    assert stored == datetime(2030, 1, 3, 12, tzinfo=UTC)


def test_overlapping_interview_is_rejected(interview_db):
    db, candidate_id, application_id = interview_db
    make_interview(db, candidate_id, application_id)

    with pytest.raises(InterviewConflict, match="overlaps"):
        make_interview(
            db, candidate_id, application_id,
            starts_at=NOW + timedelta(days=2, minutes=30),
            ends_at=NOW + timedelta(days=2, hours=2),
        )


def test_naive_datetime_is_rejected(interview_db):
    db, candidate_id, application_id = interview_db

    with pytest.raises(InterviewConflict):
        make_interview(
            db, candidate_id, application_id,
            starts_at=datetime(2030, 1, 3, 12, 0),
        )


def test_invalid_duration_is_rejected(interview_db):
    db, candidate_id, application_id = interview_db

    with pytest.raises(InterviewConflict):
        make_interview(
            db, candidate_id, application_id,
            ends_at=NOW + timedelta(days=2, hours=8),
        )


def test_stale_version_rejected(interview_db):
    db, candidate_id, application_id = interview_db
    interview = make_interview(db, candidate_id, application_id)

    with pytest.raises(InterviewConflict, match="Stale"):
        reschedule_interview(
            db,
            candidate_id=candidate_id,
            interview_id=interview.id,
            expected_version=99,
            starts_at=NOW + timedelta(days=3),
            ends_at=NOW + timedelta(days=3, hours=1),
            reminder_minutes=(1440, 60),
            now=NOW,
        )


def test_reschedule_refreshes_reminders(interview_db):
    db, candidate_id, application_id = interview_db
    interview = make_interview(db, candidate_id, application_id)

    moved = reschedule_interview(
        db,
        candidate_id=candidate_id,
        interview_id=interview.id,
        expected_version=1,
        starts_at=NOW + timedelta(days=3),
        ends_at=NOW + timedelta(days=3, hours=1),
        reminder_minutes=(1440, 60),
        now=NOW,
    )

    assert moved.version == 2

    reminders = db.scalars(
        select(InterviewNotification).where(
            InterviewNotification.interview_id == interview.id
        )
    ).all()

    assert len(reminders) == 2
    assert all(r.state == "scheduled" for r in reminders)


def test_due_notification_becomes_available(interview_db):
    db, candidate_id, application_id = interview_db
    interview = make_interview(db, candidate_id, application_id)

    count = publish_due_notifications(
        db,
        candidate_id=candidate_id,
        now=NOW + timedelta(days=1, minutes=1),
    )

    assert count == 1

    # Repeated processing must not create another alert.
    assert publish_due_notifications(
        db,
        candidate_id=candidate_id,
        now=NOW + timedelta(days=1, minutes=1),
    ) == 0

    notification = db.scalar(
        select(InterviewNotification).where(
            InterviewNotification.interview_id == interview.id,
            InterviewNotification.state == "available",
        )
    )

    assert notification is not None

    read = mark_notification_read(
        db,
        candidate_id=candidate_id,
        notification_id=notification.id,
        now=NOW + timedelta(days=1, minutes=2),
    )

    assert read.state == "read"
    assert read.read_at is not None


def test_future_reminder_cannot_be_read(interview_db):
    db, candidate_id, application_id = interview_db
    interview = make_interview(db, candidate_id, application_id)

    notification = db.scalar(
        select(InterviewNotification).where(
            InterviewNotification.interview_id == interview.id
        )
    )

    with pytest.raises(InterviewConflict):
        mark_notification_read(
            db,
            candidate_id=candidate_id,
            notification_id=notification.id,
            now=NOW,
        )


def test_cancel_interview_stops_reminders(interview_db):
    db, candidate_id, application_id = interview_db
    interview = make_interview(db, candidate_id, application_id)

    finished = finish_interview(
        db,
        candidate_id=candidate_id,
        interview_id=interview.id,
        expected_version=1,
        action="cancel",
        now=NOW,
    )

    assert finished.status == "cancelled"

    reminders = db.scalars(
        select(InterviewNotification).where(
            InterviewNotification.interview_id == interview.id
        )
    ).all()
    assert all(r.state == "cancelled" for r in reminders)


def test_terminal_application_closes_interview(interview_db):
    db, candidate_id, application_id = interview_db
    interview = make_interview(
        db,
        candidate_id,
        application_id,
        reminder_minutes=(1440, 60, 0),
    )
    publish_due_notifications(
        db,
        candidate_id=candidate_id,
        now=NOW + timedelta(days=1, minutes=1),
    )

    available = db.scalar(
        select(InterviewNotification).where(
            InterviewNotification.interview_id == interview.id,
            InterviewNotification.state == "available",
        )
    )
    assert available is not None
    mark_notification_read(
        db,
        candidate_id=candidate_id,
        notification_id=available.id,
        now=NOW + timedelta(days=1, minutes=2),
    )

    change_application_status(
        db,
        candidate_id=candidate_id,
        application_id=application_id,
        new_status="offered",
    )

    db.refresh(interview)
    assert interview.status == "cancelled"
    assert interview.version == 2

    application = db.get(Application, application_id)
    assert application.status == "offered"

    reminders = db.scalars(
        select(InterviewNotification).where(
            InterviewNotification.interview_id == interview.id
        )
    ).all()
    assert {reminder.state for reminder in reminders} == {
        "cancelled",
        "read",
    }
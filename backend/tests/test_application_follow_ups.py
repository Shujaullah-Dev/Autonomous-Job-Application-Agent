
"""Day 19 follow-up scheduling and lifecycle tests."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from app.db.base import Base
from app.models.application_follow_up import (
    ApplicationFollowUp,
    ApplicationFollowUpEvent,
)
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.services.application_follow_ups import (
    FollowUpConflict,
    resolve_follow_up,
    schedule_follow_up,
)
from app.services.application_tracking import (
    change_application_status,
    create_tracked_application,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

UTC = timezone.utc  # noqa: UP017


@pytest.fixture
def follow_up_db():
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
                full_name="Follow Up Tester",
                email="followup@example.test",
            )
        )

        job = Job(
            title="Python Developer",
            company_name="Example Employer",
            description="Python and FastAPI development",
            job_url="https://company.test/jobs/followup",
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
                "candidate_name": "Follow Up Tester",
                "candidate_email": "followup@example.test",
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

    try:
        with Session(engine) as db:
            yield db, candidate_id, application_id
    finally:
        engine.dispose()


def schedule(db, candidate_id, application_id, **changes):
    now = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)

    arguments = {
        "candidate_id": candidate_id,
        "application_id": application_id,
        "kind": "status_check",
        "due_at": now + timedelta(days=7),
        "now": now,
    }

    arguments.update(changes)

    return schedule_follow_up(db, **arguments)


def test_creates_pending_follow_up_and_event(follow_up_db):
    db, candidate_id, application_id = follow_up_db

    task = schedule(db, candidate_id, application_id)

    assert task.state == "pending"

    events = db.scalars(
        select(ApplicationFollowUpEvent).where(
            ApplicationFollowUpEvent.follow_up_id == task.id
        )
    ).all()

    assert len(events) == 1
    assert events[0].event_type == "created"


def test_duplicate_follow_up_is_rejected(follow_up_db):
    db, candidate_id, application_id = follow_up_db

    schedule(db, candidate_id, application_id)

    with pytest.raises(FollowUpConflict):
        schedule(db, candidate_id, application_id)


def test_past_due_date_is_rejected(follow_up_db):
    db, candidate_id, application_id = follow_up_db

    now = datetime(2026, 11, 12, 12, tzinfo=UTC)

    with pytest.raises(FollowUpConflict):
        schedule(
            db,
            candidate_id,
            application_id,
            due_at=now - timedelta(days=1),
        )


def test_more_than_one_year_is_rejected(follow_up_db):
    db, candidate_id, application_id = follow_up_db

    now = datetime(2026, 11, 12, 12, tzinfo=UTC)

    with pytest.raises(FollowUpConflict):
        schedule(
            db,
            candidate_id,
            application_id,
            due_at=now + timedelta(days=366),
        )


def test_naive_datetime_is_rejected(follow_up_db):
    db, candidate_id, application_id = follow_up_db

    with pytest.raises(FollowUpConflict):
        schedule(
            db,
            candidate_id,
            application_id,
            due_at=datetime(2026, 11, 20, 9, 0),
        )


def test_timezone_offset_normalization(follow_up_db):
    db, candidate_id, application_id = follow_up_db

    pakistan_time = datetime(
        2026, 11, 20, 9, 0,
        tzinfo=timezone(timedelta(hours=5)),
    )

    task = schedule(
        db,
        candidate_id,
        application_id,
        due_at=pakistan_time,
    )

    # SQLite may return a naive datetime even though the
    # original value was normalized to UTC before insertion.
    assert task.due_at.replace(tzinfo=UTC) == datetime(
        2026, 11, 20, 4, 0, tzinfo=UTC
    )


def test_completion_creates_audit_event(follow_up_db):
    db, candidate_id, application_id = follow_up_db

    task = schedule(db, candidate_id, application_id)

    resolved = resolve_follow_up(
        db,
        candidate_id=candidate_id,
        application_id=application_id,
        follow_up_id=task.id,
        action="complete",
        resolution_note="Checked employer portal manually",
    )

    assert resolved.state == "completed"
    assert resolved.resolved_at is not None

    events = db.scalars(
        select(ApplicationFollowUpEvent)
        .where(
            ApplicationFollowUpEvent.follow_up_id == task.id
        )
        .order_by(ApplicationFollowUpEvent.id)
    ).all()

    assert [event.event_type for event in events] == [
        "created",
        "completed",
    ]


def test_cannot_resolve_twice(follow_up_db):
    db, candidate_id, application_id = follow_up_db

    task = schedule(db, candidate_id, application_id)

    resolve_follow_up(
        db,
        candidate_id=candidate_id,
        application_id=application_id,
        follow_up_id=task.id,
        action="dismiss",
    )

    with pytest.raises(FollowUpConflict):
        resolve_follow_up(
            db,
            candidate_id=candidate_id,
            application_id=application_id,
            follow_up_id=task.id,
            action="complete",
        )


def test_terminal_status_auto_closes_pending_tasks(
    follow_up_db,
):
    db, candidate_id, application_id = follow_up_db

    task = schedule(db, candidate_id, application_id)

    change_application_status(
        db,
        candidate_id=candidate_id,
        application_id=application_id,
        new_status="rejected",
        note="Employer rejection reported",
    )

    db.refresh(task)

    assert task.state == "dismissed"

    events = db.scalars(
        select(ApplicationFollowUpEvent)
        .where(
            ApplicationFollowUpEvent.follow_up_id == task.id
        )
        .order_by(ApplicationFollowUpEvent.id)
    ).all()

    assert [event.event_type for event in events] == [
        "created",
        "auto_closed",
    ]


def test_rejected_application_cannot_schedule(follow_up_db):
    db, candidate_id, application_id = follow_up_db

    change_application_status(
        db,
        candidate_id=candidate_id,
        application_id=application_id,
        new_status="rejected",
    )

    with pytest.raises(FollowUpConflict):
        schedule(db, candidate_id, application_id)


def test_follow_up_models_are_registered():
    assert (
        ApplicationFollowUp.__tablename__
        == "application_follow_ups"
    )
    assert (
        ApplicationFollowUpEvent.__tablename__
        == "application_follow_up_events"
    )


""" Application tracking tests."""

import uuid

import pytest
from app.db.base import Base
from app.models.application import (
    Application,
    ApplicationDraftRevision,
    ApplicationStatusEvent,
)
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.services.application_tracking import (
    ApplicationConflict,
    change_application_status,
    create_tracked_application,
    get_application_details,
    save_draft_revision,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def tracked_db():
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
                full_name="Tracking Tester",
                email="tracking@example.test",
            )
        )

        job = Job(
            title="Python Developer",
            company_name="Example Company",
            description="Build Python APIs.",
            job_url="https://company.test/jobs/17",
            source="greenhouse:example",
            is_active=True,
        )

        db.add(job)
        db.commit()
        job_id = job.id

    try:
        with Session(engine) as db:
            yield db, candidate_id, job_id
    finally:
        engine.dispose()


def create_sample(db, candidate_id, job_id):
    return create_tracked_application(
        db,
        candidate_id=candidate_id,
        workflow_id=uuid.uuid4(),
        job_id=job_id,
        job_title="Python Developer",
        company_name="Example Company",
        job_url="https://company.test/jobs/17",
        cover_letter="Dear Hiring Team, I am interested.",
        resume_snapshot={
            "candidate_name": "Tracking Tester",
            "candidate_email": "tracking@example.test",
            "relevant_skills": ["Python"],
            "experiences": [],
            "educations": [],
        },
    )


def test_initial_application_is_persisted(tracked_db):
    db, candidate_id, job_id = tracked_db

    app = create_sample(db, candidate_id, job_id)

    assert app.status == "draft"
    assert app.current_revision == 1

    application, revisions, events = (
        get_application_details(
            db,
            candidate_id=candidate_id,
            application_id=app.id,
        )
    )

    assert application.id == app.id
    assert len(revisions) == 1
    assert revisions[0].source == "generated"
    assert len(events) == 1
    assert events[0].new_status == "draft"


def test_duplicate_tracking_rejected(tracked_db):
    db, candidate_id, job_id = tracked_db

    create_sample(db, candidate_id, job_id)

    with pytest.raises(ApplicationConflict):
        create_sample(db, candidate_id, job_id)


def test_draft_edits_create_revisions(tracked_db):
    db, candidate_id, job_id = tracked_db

    app = create_sample(db, candidate_id, job_id)

    save_draft_revision(
        db,
        candidate_id=candidate_id,
        application_id=app.id,
        expected_revision=1,
        cover_letter="A revised and reviewed cover letter.",
    )

    _, revisions, _ = get_application_details(
        db,
        candidate_id=candidate_id,
        application_id=app.id,
    )

    assert len(revisions) == 2
    assert revisions[0].revision_number == 1
    assert revisions[1].revision_number == 2
    assert revisions[0].cover_letter != revisions[1].cover_letter
    assert revisions[1].source == "candidate_edit"


def test_stale_revision_rejected(tracked_db):
    db, candidate_id, job_id = tracked_db
    app = create_sample(db, candidate_id, job_id)

    with pytest.raises(ApplicationConflict):
        save_draft_revision(
            db,
            candidate_id=candidate_id,
            application_id=app.id,
            expected_revision=99,
            cover_letter="Some replacement cover letter.",
        )


def test_cannot_mark_ready_without_review(tracked_db):
    db, candidate_id, job_id = tracked_db
    app = create_sample(db, candidate_id, job_id)

    with pytest.raises(ApplicationConflict):
        change_application_status(
            db,
            candidate_id=candidate_id,
            application_id=app.id,
            new_status="ready",
        )


def test_submission_requires_explicit_confirmation(tracked_db):
    db, candidate_id, job_id = tracked_db
    app = create_sample(db, candidate_id, job_id)

    change_application_status(
        db,
        candidate_id=candidate_id,
        application_id=app.id,
        new_status="ready",
        confirm_reviewed=True,
    )

    with pytest.raises(ApplicationConflict):
        change_application_status(
            db,
            candidate_id=candidate_id,
            application_id=app.id,
            new_status="submitted",
        )


def test_complete_status_history(tracked_db):
    db, candidate_id, job_id = tracked_db
    app = create_sample(db, candidate_id, job_id)

    transitions = [
        ("ready", True, False),
        ("submitted", False, True),
        ("interview", False, False),
        ("offered", False, False),
    ]

    for status, reviewed, submitted in transitions:
        change_application_status(
            db,
            candidate_id=candidate_id,
            application_id=app.id,
            new_status=status,
            confirm_reviewed=reviewed,
            confirm_external_submission=submitted,
        )

    application, _, history = get_application_details(
        db,
        candidate_id=candidate_id,
        application_id=app.id,
    )

    assert application.status == "offered"
    assert application.submitted_at is not None
    assert [event.new_status for event in history] == [
        "draft",
        "ready",
        "submitted",
        "interview",
        "offered",
    ]


def test_invalid_transition_rejected(tracked_db):
    db, candidate_id, job_id = tracked_db
    app = create_sample(db, candidate_id, job_id)

    with pytest.raises(ApplicationConflict):
        change_application_status(
            db,
            candidate_id=candidate_id,
            application_id=app.id,
            new_status="offered",
        )


def test_cannot_edit_after_ready(tracked_db):
    db, candidate_id, job_id = tracked_db
    app = create_sample(db, candidate_id, job_id)

    change_application_status(
        db,
        candidate_id=candidate_id,
        application_id=app.id,
        new_status="ready",
        confirm_reviewed=True,
    )

    with pytest.raises(ApplicationConflict):
        save_draft_revision(
            db,
            candidate_id=candidate_id,
            application_id=app.id,
            expected_revision=1,
            cover_letter="Attempted edit after approval.",
        )


def test_application_tables_are_registered():
    assert Application.__tablename__ == "applications"
    assert (
        ApplicationDraftRevision.__tablename__
        == "application_draft_revisions"
    )
    assert (
        ApplicationStatusEvent.__tablename__
        == "application_status_events"
    )


""" Application persistence and lifecycle operations."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import (
    Application,
    ApplicationDraftRevision,
    ApplicationStatusEvent,
)


class ApplicationNotFound(Exception):
    pass


class ApplicationConflict(Exception):
    pass


ALLOWED_TRANSITIONS = {
    "draft": {"ready", "withdrawn"},
    "ready": {"submitted", "withdrawn"},
    "submitted": {"interview", "rejected", "withdrawn"},
    "interview": {"offered", "rejected", "withdrawn"},
    "offered": set(),
    "rejected": set(),
    "withdrawn": set(),
}


def get_application(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    lock: bool = False,
) -> Application:
    query = select(Application).where(
        Application.id == application_id,
        Application.candidate_id == candidate_id,
    )

    if lock:
        query = query.with_for_update()

    application = db.scalar(query)

    if application is None:
        raise ApplicationNotFound()

    return application


def get_application_details(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
) -> tuple[
    Application,
    list[ApplicationDraftRevision],
    list[ApplicationStatusEvent],
]:
    application = get_application(
        db,
        candidate_id=candidate_id,
        application_id=application_id,
    )

    revisions = db.scalars(
        select(ApplicationDraftRevision)
        .where(
            ApplicationDraftRevision.application_id
            == application.id
        )
        .order_by(
            ApplicationDraftRevision.revision_number
        )
    ).all()

    events = db.scalars(
        select(ApplicationStatusEvent)
        .where(
            ApplicationStatusEvent.application_id
            == application.id
        )
        .order_by(ApplicationStatusEvent.id)
    ).all()

    return application, list(revisions), list(events)


def create_tracked_application(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    workflow_id: uuid.UUID,
    job_id: int,
    job_title: str,
    company_name: str,
    job_url: str,
    cover_letter: str,
    resume_snapshot: dict[str, Any],
) -> Application:
    """Atomically create application, revision 1 and history."""

    existing = db.scalar(
        select(Application.id).where(
            Application.candidate_id == candidate_id,
            Application.job_id == job_id,
        )
    )

    if existing is not None:
        raise ApplicationConflict(
            "An application for this job is already tracked"
        )

    application = Application(
        candidate_id=candidate_id,
        workflow_id=workflow_id,
        job_id=job_id,
        job_title=job_title,
        company_name=company_name,
        job_url=job_url,
        status="draft",
        current_revision=1,
    )

    db.add(application)
    db.flush()

    db.add(
        ApplicationDraftRevision(
            application_id=application.id,
            revision_number=1,
            cover_letter=cover_letter,
            resume_snapshot=resume_snapshot,
            source="generated",
        )
    )

    db.add(
        ApplicationStatusEvent(
            application_id=application.id,
            previous_status=None,
            new_status="draft",
            actor="system",
            note="Application tracking record created",
        )
    )

    # One transaction protects all three records.
    db.commit()
    db.refresh(application)

    return application


def save_draft_revision(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    expected_revision: int,
    cover_letter: str,
) -> Application:
    """Save a new draft without overwriting older revisions."""

    application = get_application(
        db,
        candidate_id=candidate_id,
        application_id=application_id,
        lock=True,
    )

    if application.status != "draft":
        raise ApplicationConflict(
            "Only draft applications can be edited"
        )

    if application.current_revision != expected_revision:
        raise ApplicationConflict(
            "Draft revision is stale; reload before editing"
        )

    previous = db.scalar(
        select(ApplicationDraftRevision)
        .where(
            ApplicationDraftRevision.application_id
            == application.id,
            ApplicationDraftRevision.revision_number
            == application.current_revision,
        )
    )

    if previous is None:
        raise ApplicationConflict(
            "Current draft revision is missing"
        )

    next_revision = application.current_revision + 1

    db.add(
        ApplicationDraftRevision(
            application_id=application.id,
            revision_number=next_revision,
            cover_letter=cover_letter,
            resume_snapshot=dict(previous.resume_snapshot),
            source="candidate_edit",
        )
    )

    application.current_revision = next_revision

    db.commit()
    db.refresh(application)

    return application


def change_application_status(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    new_status: str,
    confirm_reviewed: bool = False,
    confirm_external_submission: bool = False,
    note: str | None = None,
) -> Application:
    """
    Record an explicit lifecycle change.

    This function NEVER sends an application.
    'submitted' is a user-reported external action.
    """

    application = get_application(
        db,
        candidate_id=candidate_id,
        application_id=application_id,
        lock=True,
    )

    previous_status = application.status
    allowed = ALLOWED_TRANSITIONS.get(previous_status, set())

    if new_status not in allowed:
        raise ApplicationConflict(
            f"Cannot transition from "
            f"{previous_status} to {new_status}"
        )

    if new_status == "ready" and not confirm_reviewed:
        raise ApplicationConflict(
            "Explicit draft review confirmation is required"
        )

    if (
        new_status == "submitted"
        and not confirm_external_submission
    ):
        raise ApplicationConflict(
            "Explicit confirmation of an external "
            "submission is required"
        )

    event_note = note

    if new_status == "submitted":
        # Record only what the API caller has reported.
        application.submitted_at = datetime.now(
            UTC
        )

        prefix = (
            "External submission reported by API caller; "
            "not independently verified."
        )

        event_note = (
            f"{prefix} {note}"
            if note
            else prefix
        )

    application.status = new_status

    db.add(
        ApplicationStatusEvent(
            application_id=application.id,
            previous_status=previous_status,
            new_status=new_status,
            actor="api_caller",
            note=event_note,
        )
    )

    db.commit()
    db.refresh(application)

    return application

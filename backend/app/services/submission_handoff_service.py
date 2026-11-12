
"""Persist manual handoffs only after a successful preflight."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.submission_handoff import SubmissionHandoff
from app.services.application_tracking import (
    get_application,
)
from app.services.submission_preflight import (
    evaluate_submission_preflight,
)


class HandoffConflict(Exception):
    pass


class HandoffNotFound(Exception):
    pass


def prepare_manual_handoff(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
    expected_revision: int,
) -> tuple[SubmissionHandoff, bool]:
    """
    Prepare a handoff.

    Does not call any employer endpoint.
    Does not change Application.status.

    Returns (handoff, newly_created).
    """

    application = get_application(
        db,
        candidate_id=candidate_id,
        application_id=application_id,
        lock=True,
    )

    if application.current_revision != expected_revision:
        raise HandoffConflict(
            "Draft revision changed; reload before handoff"
        )

    report = evaluate_submission_preflight(
        db,
        application,
    )

    if not report.can_handoff:
        failed = [
            check.code
            for check in report.checks
            if not check.passed
        ]

        raise HandoffConflict(
            "Submission preflight blocked: "
            + ", ".join(failed)
        )

    existing = db.scalar(
        select(SubmissionHandoff)
        .where(
            SubmissionHandoff.application_id
            == application.id,
            SubmissionHandoff.revision_number
            == application.current_revision,
        )
    )

    # Idempotency: do not create duplicate records.
    if existing is not None:
        return existing, False

    destination = report.destination_url

    if destination is None:
        raise HandoffConflict("Destination URL unavailable")

    handoff = SubmissionHandoff(
        application_id=application.id,
        revision_number=application.current_revision,
        provider_hint=report.provider_hint,
        destination_url=destination,
        status="prepared",
    )

    db.add(handoff)
    db.commit()
    db.refresh(handoff)

    return handoff, True


def get_latest_handoff(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    application_id: uuid.UUID,
) -> SubmissionHandoff:
    """Read a prior handoff record for this candidate."""

    application = get_application(
        db,
        candidate_id=candidate_id,
        application_id=application_id,
    )

    handoff = db.scalar(
        select(SubmissionHandoff)
        .where(
            SubmissionHandoff.application_id
            == application.id
        )
        .order_by(
            SubmissionHandoff.revision_number.desc(),
            SubmissionHandoff.created_at.desc(),
        )
        .limit(1)
    )

    if handoff is None:
        raise HandoffNotFound()

    return handoff
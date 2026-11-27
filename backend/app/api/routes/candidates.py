import uuid

from app.core.auth import optional_user, require_candidate_owner, require_user
from app.db.session import get_db
from app.models.candidate import CandidateProfile
from app.schemas.candidate import (
    CandidateCreate,
    CandidateResponse,
    CandidateUpdate,
)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/candidates", tags=["Candidates"])


@router.post(
    "",
    response_model=CandidateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_candidate(
    payload: CandidateCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user=Depends(optional_user),  # noqa: B008
) -> CandidateProfile:
    values = payload.model_dump()

    if user is not None:
        # A verified account owns exactly one profile, and only its own.
        if not user.email or payload.email.lower() != user.email.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Profile email must match the verified account email",
            )

        existing = db.scalar(
            select(CandidateProfile).where(
                CandidateProfile.owner_id == user.subject
            )
        )

        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This account already has a candidate profile",
            )

        values["owner_id"] = user.subject

    candidate = CandidateProfile(**values)
    db.add(candidate)

    try:
        db.commit()
        db.refresh(candidate)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A candidate with this email already exists",
        ) from None

    return candidate


@router.get("/me", response_model=CandidateResponse)
def read_own_candidate(
    db: Session = Depends(get_db),  # noqa: B008
    user=Depends(require_user),  # noqa: B008
) -> CandidateProfile:
    """Return the profile owned by the verified account.

    A profile created before ownership existed is linked only when its email
    matches the verified account email.
    """

    candidate = db.scalar(
        select(CandidateProfile).where(
            CandidateProfile.owner_id == user.subject
        )
    )

    if candidate is None and user.email:
        candidate = db.scalar(
            select(CandidateProfile).where(
                CandidateProfile.email == user.email
            )
        )

        if candidate is not None and candidate.owner_id is None:
            candidate.owner_id = user.subject
            db.commit()
            db.refresh(candidate)
        elif candidate is not None:
            candidate = None

    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate profile not found",
        )

    return candidate


@router.get(
    "/{candidate_id}",
    response_model=CandidateResponse,
    dependencies=[Depends(require_candidate_owner)],
)
def get_candidate(
    candidate_id: uuid.UUID,
    db: Session = Depends(get_db),  # noqa: B008
) -> CandidateProfile:
    candidate = db.get(CandidateProfile, candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )
    return candidate


@router.patch(
    "/{candidate_id}",
    response_model=CandidateResponse,
    dependencies=[Depends(require_candidate_owner)],
)
def update_candidate(
    candidate_id: uuid.UUID,
    payload: CandidateUpdate,
    db: Session = Depends(get_db),  # noqa: B008
) -> CandidateProfile:
    candidate = db.get(CandidateProfile, candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )

    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided",
        )

    for field, value in updates.items():
        setattr(candidate, field, value)

    try:
        db.commit()
        db.refresh(candidate)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The update conflicts with an existing candidate",
        ) from None

    return candidate
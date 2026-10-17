import uuid

from app.db.session import get_db
from app.models.candidate import CandidateProfile
from app.models.experience import WorkExperience
from app.schemas.experience import (
    ExperienceCreate,
    ExperienceResponse,
    ExperienceUpdate,
)
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/v1/candidates/{candidate_id}/experiences",
    tags=["Work Experience"],
)


def require_candidate(candidate_id: uuid.UUID, db: Session) -> None:
    if db.get(CandidateProfile, candidate_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        )


@router.post(
    "",
    response_model=ExperienceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_experience(
    candidate_id: uuid.UUID,
    payload: ExperienceCreate,
    db: Session = Depends(get_db),
) -> WorkExperience:
    require_candidate(candidate_id, db)

    experience = WorkExperience(
        candidate_id=candidate_id,
        **payload.model_dump(),
    )
    db.add(experience)
    db.commit()
    db.refresh(experience)
    return experience


@router.get("", response_model=list[ExperienceResponse])
def list_experiences(
    candidate_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[WorkExperience]:
    require_candidate(candidate_id, db)

    statement = (
        select(WorkExperience)
        .where(WorkExperience.candidate_id == candidate_id)
        .order_by(WorkExperience.start_date.desc())
    )
    return list(db.scalars(statement).all())


@router.patch("/{experience_id}", response_model=ExperienceResponse)
def update_experience(
    candidate_id: uuid.UUID,
    experience_id: uuid.UUID,
    payload: ExperienceUpdate,
    db: Session = Depends(get_db),
) -> WorkExperience:
    require_candidate(candidate_id, db)

    experience = db.scalar(
        select(WorkExperience).where(
            WorkExperience.id == experience_id,
            WorkExperience.candidate_id == candidate_id,
        )
    )
    if experience is None:
        raise HTTPException(status_code=404, detail="Experience not found")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=400,
            detail="At least one field must be provided",
        )

    # Validate the resulting record, not just the partial request.
    resulting_start = updates.get("start_date", experience.start_date)
    resulting_end = updates.get("end_date", experience.end_date)
    resulting_current = updates.get("is_current", experience.is_current)

    if resulting_end is not None and resulting_end < resulting_start:
        raise HTTPException(
            status_code=422,
            detail="End date cannot be before start date",
        )
    if resulting_current and resulting_end is not None:
        raise HTTPException(
            status_code=422,
            detail="Current employment cannot have an end date",
        )

    for field, value in updates.items():
        if field in {"company_name", "job_title"}:
            if value is None or not value.strip():
                raise HTTPException(
                    status_code=422,
                    detail=f"{field} cannot be blank or null",
                )
            value = value.strip()
        elif field in {"start_date", "is_current"} and value is None:
            raise HTTPException(
                status_code=422,
                detail=f"{field} cannot be null",
            )

        setattr(experience, field, value)

    try:
        db.commit()
        db.refresh(experience)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail="The experience record violates a database constraint",
        ) from None

    return experience


@router.delete("/{experience_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experience(
    candidate_id: uuid.UUID,
    experience_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    require_candidate(candidate_id, db)

    experience = db.scalar(
        select(WorkExperience).where(
            WorkExperience.id == experience_id,
            WorkExperience.candidate_id == candidate_id,
        )
    )
    if experience is None:
        raise HTTPException(status_code=404, detail="Experience not found")

    db.delete(experience)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
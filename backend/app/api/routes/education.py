import uuid

from app.db.session import get_db
from app.models.candidate import CandidateProfile
from app.models.education import Education
from app.schemas.education import (
    EducationCreate,
    EducationResponse,
    EducationUpdate,
)
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/v1/candidates/{candidate_id}/education",
    tags=["Education"],
)


def require_candidate(candidate_id: uuid.UUID, db: Session) -> None:
    if db.get(CandidateProfile, candidate_id) is None:
        raise HTTPException(status_code=404, detail="Candidate not found")


@router.post(
    "",
    response_model=EducationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_education(
    candidate_id: uuid.UUID,
    payload: EducationCreate,
    db: Session = Depends(get_db),
) -> Education:
    require_candidate(candidate_id, db)

    education = Education(
        candidate_id=candidate_id,
        **payload.model_dump(),
    )
    db.add(education)
    db.commit()
    db.refresh(education)
    return education


@router.get("", response_model=list[EducationResponse])
def list_education(
    candidate_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[Education]:
    require_candidate(candidate_id, db)

    statement = (
        select(Education)
        .where(Education.candidate_id == candidate_id)
        .order_by(Education.start_date.desc())
    )
    return list(db.scalars(statement).all())


@router.patch("/{education_id}", response_model=EducationResponse)
def update_education(
    candidate_id: uuid.UUID,
    education_id: uuid.UUID,
    payload: EducationUpdate,
    db: Session = Depends(get_db),
) -> Education:
    require_candidate(candidate_id, db)

    education = db.scalar(
        select(Education).where(
            Education.id == education_id,
            Education.candidate_id == candidate_id,
        )
    )
    if education is None:
        raise HTTPException(status_code=404, detail="Education not found")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=400,
            detail="At least one field must be provided",
        )

    resulting_start = updates.get("start_date", education.start_date)
    resulting_end = updates.get("end_date", education.end_date)

    if resulting_end is not None and resulting_end < resulting_start:
        raise HTTPException(
            status_code=422,
            detail="End date cannot be before start date",
        )

    for field, value in updates.items():
        if field in {"institution", "degree"}:
            if value is None or not value.strip():
                raise HTTPException(
                    status_code=422,
                    detail=f"{field} cannot be blank or null",
                )
            value = value.strip()
        elif field == "start_date" and value is None:
            raise HTTPException(
                status_code=422,
                detail="start_date cannot be null",
            )

        setattr(education, field, value)

    try:
        db.commit()
        db.refresh(education)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail="The education record violates a database constraint",
        ) from None

    return education


@router.delete("/{education_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_education(
    candidate_id: uuid.UUID,
    education_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    require_candidate(candidate_id, db)

    education = db.scalar(
        select(Education).where(
            Education.id == education_id,
            Education.candidate_id == candidate_id,
        )
    )
    if education is None:
        raise HTTPException(status_code=404, detail="Education not found")

    db.delete(education)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
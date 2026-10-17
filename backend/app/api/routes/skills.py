import uuid

from app.db.session import get_db
from app.models.candidate import CandidateProfile
from app.models.skill import CandidateSkill
from app.schemas.skill import SkillCreate, SkillResponse, SkillUpdate
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/v1/candidates/{candidate_id}/skills",
    tags=["Candidate Skills"],
)


def get_existing_candidate(
    candidate_id: uuid.UUID,
    db: Session,
) -> CandidateProfile:
    candidate = db.get(CandidateProfile, candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found",
        )
    return candidate


@router.post(
    "",
    response_model=SkillResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_skill(
    candidate_id: uuid.UUID,
    payload: SkillCreate,
    db: Session = Depends(get_db),
) -> CandidateSkill:
    get_existing_candidate(candidate_id, db)

    skill = CandidateSkill(
        candidate_id=candidate_id,
        **payload.model_dump(),
    )
    db.add(skill)

    try:
        db.commit()
        db.refresh(skill)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This skill already exists for the candidate",
        ) from None

    return skill


@router.get("", response_model=list[SkillResponse])
def list_skills(
    candidate_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[CandidateSkill]:
    get_existing_candidate(candidate_id, db)

    statement = (
        select(CandidateSkill)
        .where(CandidateSkill.candidate_id == candidate_id)
        .order_by(CandidateSkill.created_at)
    )
    return list(db.scalars(statement).all())


@router.patch("/{skill_id}", response_model=SkillResponse)
def update_skill(
    candidate_id: uuid.UUID,
    skill_id: uuid.UUID,
    payload: SkillUpdate,
    db: Session = Depends(get_db),
) -> CandidateSkill:
    get_existing_candidate(candidate_id, db)

    skill = db.scalar(
        select(CandidateSkill).where(
            CandidateSkill.id == skill_id,
            CandidateSkill.candidate_id == candidate_id,
        )
    )
    if skill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found",
        )

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided",
        )

    for field, value in updates.items():
        if value is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field} cannot be null",
            )
        setattr(skill, field, value)

    try:
        db.commit()
        db.refresh(skill)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The update conflicts with an existing skill",
        ) from None

    return skill


@router.delete(
    "/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_skill(
    candidate_id: uuid.UUID,
    skill_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    get_existing_candidate(candidate_id, db)

    skill = db.scalar(
        select(CandidateSkill).where(
            CandidateSkill.id == skill_id,
            CandidateSkill.candidate_id == candidate_id,
        )
    )
    if skill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found",
        )

    db.delete(skill)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
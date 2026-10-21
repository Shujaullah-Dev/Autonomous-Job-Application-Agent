
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate import CandidateProfile
from app.models.education import Education
from app.models.experience import WorkExperience
from app.models.skill import CandidateSkill
from app.schemas.resume_import import (
    ImportCounts,
    ResumeImportRequest,
    ResumeImportResponse,
)
from app.services.import_normalization import (
    education_key,
    experience_key,
    skill_key,
)


class CandidateNotFoundError(Exception):
    pass


def import_reviewed_resume(
    db: Session,
    candidate_id: uuid.UUID,
    payload: ResumeImportRequest,
) -> ResumeImportResponse:

    try:
        # Lock this candidate during the transaction.
        candidate = db.scalar(
            select(CandidateProfile)
            .where(CandidateProfile.id == candidate_id)
            .with_for_update()
        )

        if candidate is None:
            raise CandidateNotFoundError()

        skill_counts = ImportCounts()
        experience_counts = ImportCounts()
        education_counts = ImportCounts()

        # ----- SKILLS -----

        existing_skills = db.scalars(
            select(CandidateSkill).where(
                CandidateSkill.candidate_id == candidate_id
            )
        ).all()

        skill_keys = {
            skill_key(item.name)
            for item in existing_skills
        }

        for item in payload.skills:
            key = skill_key(item.name)

            if key in skill_keys:
                skill_counts.skipped += 1
                continue

            db.add(
                CandidateSkill(
                    candidate_id=candidate_id,
                    name=item.name,
                    proficiency_level=item.proficiency_level,
                )
            )

            skill_keys.add(key)
            skill_counts.created += 1

        # ----- WORK EXPERIENCES -----

        existing_experiences = db.scalars(
            select(WorkExperience).where(
                WorkExperience.candidate_id == candidate_id
            )
        ).all()

        experience_keys = {
            experience_key(
                item.company_name,
                item.job_title,
                item.start_date,
                item.end_date,
            )
            for item in existing_experiences
        }

        for item in payload.experiences:
            key = experience_key(
                item.company_name,
                item.job_title,
                item.start_date,
                item.end_date,
            )

            if key in experience_keys:
                experience_counts.skipped += 1
                continue

            db.add(
                WorkExperience(
                    candidate_id=candidate_id,
                    **item.model_dump(),
                )
            )

            experience_keys.add(key)
            experience_counts.created += 1

        # ----- EDUCATION -----

        existing_educations = db.scalars(
            select(Education).where(
                Education.candidate_id == candidate_id
            )
        ).all()

        education_keys = {
            education_key(
                item.institution,
                item.degree,
                item.start_date,
                item.end_date,
            )
            for item in existing_educations
        }

        for item in payload.educations:
            key = education_key(
                item.institution,
                item.degree,
                item.start_date,
                item.end_date,
            )

            if key in education_keys:
                education_counts.skipped += 1
                continue

            db.add(
                Education(
                    candidate_id=candidate_id,
                    **item.model_dump(),
                )
            )

            education_keys.add(key)
            education_counts.created += 1

        db.commit()

        return ResumeImportResponse(
            status="success",
            candidate_id=str(candidate_id),
            skills=skill_counts,
            experiences=experience_counts,
            educations=education_counts,
            message="Reviewed records imported successfully",
        )

    except Exception:
        db.rollback()
        raise
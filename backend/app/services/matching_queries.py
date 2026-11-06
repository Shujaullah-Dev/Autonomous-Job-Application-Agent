
"""Database loading for candidate-to-job matching."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate import CandidateProfile
from app.models.experience import WorkExperience
from app.models.job import Job
from app.models.skill import CandidateSkill
from app.services.job_matching import (
    CandidateInput,
    JobInput,
)

MAX_EVALUATED_JOBS = 500


def load_candidate(
    db: Session,
    candidate_id: uuid.UUID,
) -> CandidateInput | None:
    """Load candidate profile, skills, and job titles."""

    candidate = db.get(
        CandidateProfile,
        candidate_id,
    )

    if candidate is None:
        return None

    skills = db.scalars(
        select(CandidateSkill)
        .where(
            CandidateSkill.candidate_id == candidate_id
        )
        .order_by(CandidateSkill.name)
    ).all()

    experiences = db.scalars(
        select(WorkExperience)
        .where(
            WorkExperience.candidate_id == candidate_id
        )
        .order_by(WorkExperience.start_date.desc())
    ).all()

    titles = [
        experience.job_title
        for experience in experiences
    ]

    # Existing structured skills from resume import.
    skill_names = [
        skill.name
        for skill in skills
    ]

    return CandidateInput(
        skills=skill_names,
        titles=titles,
        years_experience=candidate.years_experience,
        location=candidate.location,
    )


def load_active_jobs(
    db: Session,
) -> list[tuple[Job, JobInput]]:
    """Load a bounded set of active jobs for MVP scoring."""

    jobs = db.scalars(
        select(Job)
        .where(Job.is_active.is_(True))
        .order_by(Job.id.desc())
        .limit(MAX_EVALUATED_JOBS)
    ).all()

    return [
        (
            job,
            JobInput(
                id=job.id,
                title=job.title,
                description=job.description,
                location=job.location,
                work_mode=job.work_mode,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                salary_currency=job.salary_currency,
            ),
        )
        for job in jobs
    ]
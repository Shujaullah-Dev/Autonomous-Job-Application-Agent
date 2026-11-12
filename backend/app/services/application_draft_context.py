
"""Load approved candidate and job facts for application drafts."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.candidate import CandidateProfile
from app.models.education import Education
from app.models.experience import WorkExperience
from app.models.skill import CandidateSkill
from app.services.application_materials import ApplicationFacts
from app.services.job_matching import (
    candidate_skill_keys,
    normalized,
)
from app.services.matching_queries import load_active_jobs
from app.services.resume_skills import extract_skills


class DraftCandidateNotFound(Exception):
    pass


class DraftJobUnavailable(Exception):
    pass


class DraftJobChanged(Exception):
    pass


def load_application_facts(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    job_id: int,
    approved_title: str,
    shortlist_score: float,
) -> ApplicationFacts:
    """
    Load facts for an approved shortlist item.

    Job must still be active and eligible for the
    existing recommendation pool.
    """

    candidate = db.get(
        CandidateProfile,
        candidate_id,
    )

    if candidate is None:
        raise DraftCandidateNotFound()

    # Reuse existing Day 12/13 demo-job exclusions.
    active_jobs = load_active_jobs(db)

    selected = next(
        (
            job
            for job, _ in active_jobs
            if job.id == job_id
        ),
        None,
    )

    if selected is None:
        raise DraftJobUnavailable()

    # A changed title needs a fresh human review.
    if selected.title != approved_title:
        raise DraftJobChanged()

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

    educations = db.scalars(
        select(Education)
        .where(
            Education.candidate_id == candidate_id
        )
        .order_by(Education.start_date.desc())
    ).all()

    # The job parser supplies recognized technology names.
    # We never add technologies the candidate did not list.
    job_skills = {
        normalized(name)
        for name in extract_skills(
            f"{selected.title}\n{selected.description}"
        )
    }

    relevant_skills = []

    for skill in skills:
        aliases = candidate_skill_keys([skill.name])

        if aliases & job_skills:
            relevant_skills.append(skill.name)

    recorded_experiences = []

    for item in experiences[:5]:
        start = item.start_date.isoformat()

        if item.is_current:
            end = "Present"
        elif item.end_date is not None:
            end = item.end_date.isoformat()
        else:
            end = "End date not recorded"

        recorded_experiences.append(
            f"{item.job_title} at {item.company_name} "
            f"({start} to {end})"
        )

    recorded_educations = []

    for item in educations[:5]:
        recorded_educations.append(
            f"{item.degree} at {item.institution}"
        )

    return ApplicationFacts(
        candidate_name=candidate.full_name,
        candidate_email=candidate.email,
        job_id=selected.id,
        job_title=selected.title,
        company_name=selected.company_name,
        job_url=selected.job_url,
        shortlist_score=shortlist_score,
        relevant_skills=tuple(relevant_skills),
        experiences=tuple(recorded_experiences),
        educations=tuple(recorded_educations),
        work_mode=selected.work_mode,
        location=selected.location,
    )

import uuid

from app.schemas.resume_analysis import (
    ResumeAnalysisResponse,
)
from app.services.resume_contact import extract_contact
from app.services.resume_sections import (
    extract_educations,
    extract_experiences,
)
from app.services.resume_skills import extract_skills


def analyze_resume_text(
    candidate_id: uuid.UUID,
    text: str,
) -> ResumeAnalysisResponse:
    contact = extract_contact(text)
    skills = extract_skills(text)
    experiences = extract_experiences(text)
    educations = extract_educations(text)

    warnings = []

    if not skills:
        warnings.append(
            "No supported technical skills were recognized"
        )

    if not experiences:
        warnings.append(
            "No structured work experience was recognized"
        )

    if not educations:
        warnings.append(
            "No structured education was recognized"
        )

    warnings.append(
        "Review all extracted information before saving"
    )

    return ResumeAnalysisResponse(
        candidate_id=candidate_id,
        contact=contact,
        skills=skills,
        experiences=experiences,
        educations=educations,
        warnings=warnings,
    )
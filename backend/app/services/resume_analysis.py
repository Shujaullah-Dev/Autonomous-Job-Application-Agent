import logging
import uuid

from app.core.config import settings
from app.schemas.resume_analysis import (
    ResumeAnalysisResponse,
)
from app.services.resume_contact import extract_contact
from app.services.resume_groq import (
    GroqUnavailable,
    extract_groq,
)
from app.services.resume_sections import (
    extract_educations,
    extract_experiences,
)
from app.services.resume_skills import extract_skills

logger = logging.getLogger(__name__)


def parse_locally(text: str):
    contact = extract_contact(text)
    skills = extract_skills(text)
    experiences = extract_experiences(text)
    educations = extract_educations(text)

    return contact, experiences, educations, skills


def analyze_resume_text(
    candidate_id: uuid.UUID,
    text: str,
) -> ResumeAnalysisResponse:

    warnings = [
        "Review all extracted information before saving"
    ]

    parser_used = "local"
    fallback_used = False

    if settings.resume_ai_enabled:
        try:
            (
                contact,
                experiences,
                educations,
                skills,
                issues,
            ) = extract_groq(text)

            warnings.extend(issues)
            parser_used = "groq"

            # Fill only missing contact fields using
            # locally extracted source information.
            local_contact = extract_contact(text)

            contact = contact.model_copy(
                update={
                    "email": contact.email or local_contact.email,
                    "phone": contact.phone or local_contact.phone,
                }
            )

        except GroqUnavailable as exc:
            fallback_used = True

            logger.warning(
                "Groq unavailable (%s). Local fallback activated.",
                exc.reason,
            )

            (
                contact,
                experiences,
                educations,
                skills,
            ) = parse_locally(text)

            warnings.append(
                f"Groq unavailable ({exc.reason}); "
                "local parser used. "
                "Results may be incomplete."
            )

    else:
        (
            contact,
            experiences,
            educations,
            skills,
        ) = parse_locally(text)

        warnings.append(
            "Groq disabled; local parser used"
        )

    if not skills:
        warnings.append(
            "No supported technical skills recognized"
        )

    if not experiences:
        warnings.append(
            "No verified work experience recognized"
        )

    if not educations:
        warnings.append(
            "No verified education recognized"
        )

    return ResumeAnalysisResponse(
        candidate_id=candidate_id,
        contact=contact,
        skills=skills,
        experiences=experiences,
        educations=educations,
        parser_used=parser_used,
        fallback_used=fallback_used,
        warnings=warnings,
    )
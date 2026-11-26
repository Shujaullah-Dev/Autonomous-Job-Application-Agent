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

# Human-readable explanations for the reasons the AI parser can be
# unavailable. The raw reason is kept alongside it for support/debugging.
GROQ_REASON_LABELS = {
    "missing_api_key": "no API key is configured",
    "input_limit_exceeded": "the resume text is too long for the AI parser",
    "timeout": "the AI service did not respond in time",
    "network_error": "the network request to the AI service failed",
    "rate_limit": "the AI service is rate limited",
    "authentication_error": "the AI service rejected the credentials",
    "invalid_request": "the AI service rejected the request",
    "provider_unavailable": "the AI service is temporarily unavailable",
    "provider_error": "the AI service returned an error",
    "invalid_model_response": (
        "the AI service returned a response that could not be used"
    ),
    "response_truncated": (
        "the AI response was cut off before it finished"
    ),
}


def describe_groq_reason(reason: str) -> str:
    label = GROQ_REASON_LABELS.get(reason, "the AI service is unavailable")
    return f"{label} ({reason})"


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
                "AI parser unavailable: "
                f"{describe_groq_reason(exc.reason)}. "
                "Local extraction was used instead, so results "
                "may be incomplete. Review them carefully."
            )

    else:
        (
            contact,
            experiences,
            educations,
            skills,
        ) = parse_locally(text)

        warnings.append(
            "AI parser is disabled; local extraction was used instead"
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
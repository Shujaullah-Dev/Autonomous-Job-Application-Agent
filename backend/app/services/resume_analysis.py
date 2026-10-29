
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


def local_parse(text: str):
    return (
        extract_contact(text),
        extract_experiences(text),
        extract_educations(text),
        extract_skills(text),
    )


def analyze_resume_text(
    candidate_id: uuid.UUID,
    text: str,
) -> ResumeAnalysisResponse:

    parser_used = "local"
    fallback_used = False
    warnings = [
        "Review extracted details before saving"
    ]

    if settings.resume_ai_enabled:
        try:
            (
                ai_contact,
                experiences,
                educations,
                skills,
                issues,
            ) = extract_groq(text)

            # Preserve deterministic contact extraction where
            # AI did not recognize an explicitly present value.
            local_contact = extract_contact(text)

            contact = ai_contact.model_copy(
                update={
                    "email": (
                        ai_contact.email
                        or local_contact.email
                    ),
                    "phone": (
                        ai_contact.phone
                        or local_contact.phone
                    ),
                }
            )

            warnings.extend(issues)
            parser_used = "groq"

            logger.info(
                "Resume parsed using Groq: "
                "experiences=%d educations=%d skills=%d",
                len(experiences),
                len(educations),
                len(skills),
            )

        except GroqUnavailable as exc:
            fallback_used = True
            parser_used = "local"

            logger.warning(
                "Groq unavailable: %s; using local parser",
                exc.reason,
            )

            (
                contact,
                experiences,
                educations,
                skills,
            ) = local_parse(text)

            warnings.append(
                "Groq unavailable: "
                f"{exc.reason}. "
                "Local fallback used; extraction "
                "may be incomplete."
            )

    else:
        (
            contact,
            experiences,
            educations,
            skills,
        ) = local_parse(text)

        warnings.append(
            "AI parsing disabled; local parser used"
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
        experiences=experiences,
        educations=educations,
        skills=skills,
        parser_used=parser_used,
        fallback_used=fallback_used,
        warnings=warnings,
    )

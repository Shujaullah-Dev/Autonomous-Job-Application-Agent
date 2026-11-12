
"""Day 16: Grounded application material generation."""

from dataclasses import dataclass
from typing import Literal

from langchain_core.runnables import Runnable

from app.services.langchain_explanations import (
    EvidenceContext,
    explain_evidence,
)

DraftMode = Literal[
    "deterministic",
    "langchain_groq",
    "fallback",
]


@dataclass(frozen=True)
class ApplicationFacts:
    """Facts loaded from approved candidate/job records."""

    candidate_name: str
    candidate_email: str

    job_id: int
    job_title: str
    company_name: str
    job_url: str
    shortlist_score: float

    relevant_skills: tuple[str, ...]
    experiences: tuple[str, ...]
    educations: tuple[str, ...]

    work_mode: str | None = None
    location: str | None = None


@dataclass(frozen=True)
class ApplicationDraft:
    generation_mode: DraftMode
    llm_used: bool
    cover_letter: str

    resume_skills: tuple[str, ...]
    resume_experiences: tuple[str, ...]
    resume_educations: tuple[str, ...]

    evidence_used: tuple[str, ...]
    warnings: tuple[str, ...]


def clean_text(value: str) -> str:
    """Collapse whitespace in trusted database fields."""
    return " ".join(value.split())


def collect_evidence(
    facts: ApplicationFacts,
) -> tuple[str, ...]:
    """
    Build bounded statements from stored facts.

    No accomplishments, certifications, dates or
    proficiency levels are invented.
    """

    statements: list[str] = []

    for skill in facts.relevant_skills[:6]:
        statements.append(
            f"Relevant skill listed in my profile: "
            f"{clean_text(skill)}."
        )

    for experience in facts.experiences[:2]:
        statements.append(
            "Recorded professional experience: "
            f"{clean_text(experience)}."
        )

    for education in facts.educations[:2]:
        statements.append(
            "Recorded education: "
            f"{clean_text(education)}."
        )

    return tuple(statements)


def format_cover_letter(
    facts: ApplicationFacts,
    evidence: tuple[str, ...],
) -> str:
    """Build a cover letter using verified facts only."""

    name = clean_text(facts.candidate_name)
    title = clean_text(facts.job_title)
    company = clean_text(facts.company_name)

    if evidence:
        evidence_section = "\n".join(
            f"- {statement}"
            for statement in evidence
        )
    else:
        evidence_section = (
            "- My current profile contains limited "
            "directly comparable evidence for this position."
        )

    return (
        "Dear Hiring Team,\n\n"
        f"I am writing to express my interest in the "
        f"{title} position at {company}.\n\n"
        "For your review, my saved candidate profile "
        "contains the following information:\n"
        f"{evidence_section}\n\n"
        "I would welcome the opportunity to discuss "
        "how my background relates to the responsibilities "
        "of this role.\n\n"
        "Sincerely,\n"
        f"{name}"
    )


def generate_application_draft(
    facts: ApplicationFacts,
    *,
    use_ai: bool = False,
    model: Runnable | None = None,
) -> ApplicationDraft:
    """
    Generate an application draft without invented claims.

    Optional AI can reorder verified evidence only.
    It cannot rewrite the database facts or job score.
    """

    if facts.job_id < 1:
        raise ValueError("Invalid job ID")

    if not clean_text(facts.candidate_name):
        raise ValueError("Candidate name is required")

    if not clean_text(facts.job_title):
        raise ValueError("Job title is required")

    if not clean_text(facts.company_name):
        raise ValueError("Company name is required")

    evidence = collect_evidence(facts)

    context = EvidenceContext(
        job_id=facts.job_id,
        job_title=facts.job_title,
        score=facts.shortlist_score,
        reasons=evidence,
        cautions=(),
    )

    # Reuse Day 14's LangChain chain and fallback.
    explanation = explain_evidence(
        context,
        use_ai=use_ai,
        model=model,
    )

    ordered_evidence = explanation.reasons

    warnings = [
        "This is an application draft only. "
        "No application has been submitted.",
        "Review all generated text before using it.",
        "Hiring-country eligibility and work "
        "authorization have not been verified.",
    ]

    if facts.work_mode is None:
        warnings.append(
            "The job's work mode is unknown."
        )

    if not facts.relevant_skills:
        warnings.append(
            "No direct recognized skill overlap was found "
            "for the tailored skills section."
        )

    warnings.extend(explanation.warnings)

    cover_letter = format_cover_letter(
        facts,
        ordered_evidence,
    )

    return ApplicationDraft(
        generation_mode=explanation.mode,
        llm_used=explanation.llm_used,
        cover_letter=cover_letter,
        resume_skills=facts.relevant_skills,
        resume_experiences=facts.experiences,
        resume_educations=facts.educations,
        evidence_used=ordered_evidence,
        warnings=tuple(dict.fromkeys(warnings)),
    )

"""Day 11: Deterministic candidate-to-job matching."""

import re
from dataclasses import dataclass, field

from app.services.resume_skills import extract_skills

WEIGHTS = {
    "skills": 0.40,
    "experience": 0.20,
    "title": 0.15,
    "location": 0.10,
    "preferences": 0.10,
    "salary": 0.05,
}

TITLE_STOPWORDS = {
    "a", "an", "and", "at", "for", "in",
    "of", "the", "to", "with",
    "senior", "junior", "sr", "jr",
}


@dataclass(frozen=True)
class CandidateInput:
    skills: list[str]
    titles: list[str]
    years_experience: int | None
    location: str | None


@dataclass(frozen=True)
class JobInput:
    id: int
    title: str
    description: str
    location: str | None
    work_mode: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None


@dataclass(frozen=True)
class MatchPreferences:
    preferred_work_mode: str | None = None
    preferred_location: str | None = None
    minimum_salary: int | None = None
    salary_currency: str | None = None


@dataclass
class MatchResult:
    job_id: int
    score: float
    breakdown: dict[str, float]
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def normalized(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def title_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if token not in TITLE_STOPWORDS
    }



def candidate_skill_keys(candidate_skills: list[str]) -> set[str]:
    """Normalize candidate skills and recognized aliases."""
    known: set[str] = set()

    for skill in candidate_skills:
        known.add(normalized(skill))

        for canonical in extract_skills(skill):
            known.add(normalized(canonical))

    return known


def score_skills(
    candidate_skills: list[str],
    job_text: str,
) -> tuple[float, list[str], list[str], bool]:
    """Score recognized skills mentioned by the job."""

    mentioned = set(extract_skills(job_text))

    if not mentioned:
        # Zero positive skill evidence.
        # The False flag means requirements are unknown,
        # NOT that the candidate is proven unqualified.
        return 0.0, [], [], False

    known = candidate_skill_keys(candidate_skills)

    matched = sorted(
        skill
        for skill in mentioned
        if normalized(skill) in known
    )

    missing = sorted(mentioned - set(matched))

    score = 100.0 * len(matched) / len(mentioned)

    return score, matched, missing, True




def score_experience(
    candidate_years: int | None,
    job_text: str,
) -> tuple[float, bool]:
    """Recognize common explicit experience statements."""

    pattern = re.compile(
        r"\b(\d{1,2})\s*\+?\s*(?:years?|yrs?)\s+"
        r"(?:(?:of|in)\s+)?"
        r"(?:(?:professional|relevant|industry|"
        r"hands-on|practical|work)\s+)?"
        r"experience\b",
        re.IGNORECASE,
    )

    company_history = re.compile(
        r"\b(?:company|firm|business|organization|"
        r"team|we)\s+"
        r"(?:has|have|brings?|provides?)\s+"
        r"(?:over\s+)?$",
        re.IGNORECASE,
    )

    requirements: list[int] = []

    for match in pattern.finditer(job_text):
        prefix = job_text[
            max(0, match.start() - 60):match.start()
        ]

        # Avoid common statements describing how
        # long the employer has operated.
        if company_history.search(prefix):
            continue

        requirements.append(int(match.group(1)))

    if candidate_years is None or not requirements:
        return 50.0, False

    required_years = max(requirements)

    if required_years == 0:
        return 100.0, True

    return (
        min(
            100.0,
            100.0 * candidate_years / required_years,
        ),
        True,
    )




def score_title(
    candidate_titles: list[str],
    job_title: str,
    candidate_skills: list[str] | None = None,
) -> tuple[float, bool]:
    """Combine previous-role overlap with title technologies."""

    target = title_tokens(job_title)
    scores: list[float] = []

    # Existing Day 11 comparison with previous roles.
    if target:
        for title in candidate_titles:
            previous = title_tokens(title)

            if previous:
                scores.append(
                    100.0 * len(previous & target)
                    / len(previous | target)
                )

    # Additional evidence from technologies in the title.
    title_skills = set(extract_skills(job_title))

    if title_skills:
        known = candidate_skill_keys(
            candidate_skills or []
        )

        matched_count = sum(
            normalized(skill) in known
            for skill in title_skills
        )

        scores.append(
            100.0 * matched_count / len(title_skills)
        )

    if not scores:
        return 50.0, False

    return max(scores), True





def score_location(
    candidate_location: str | None,
    job_location: str | None,
    preferred_location: str | None,
    work_mode: str | None,
) -> tuple[float, bool]:
    """Compare location text without assuming remote eligibility."""

    desired = normalized(
        preferred_location or candidate_location
    )
    actual = normalized(job_location)

    if desired and actual:
        if desired == actual:
            return 100.0, True

        if desired in actual or actual in desired:
            return 80.0, True

    # Remote does not automatically mean worldwide.
    if work_mode == "remote":
        return 50.0, False

    if not desired or not actual:
        return 50.0, False

    return 0.0, True



def score_preference(
    preferred_work_mode: str | None,
    actual_work_mode: str | None,
) -> tuple[float, bool]:
    if not preferred_work_mode or not actual_work_mode:
        return 50.0, False

    return (
        100.0 if preferred_work_mode == actual_work_mode
        else 0.0,
        True,
    )


# def score_salary(
#     minimum_salary: int | None,
#     preferred_currency: str | None,
#     job_min: int | None,
#     job_max: int | None,
#     job_currency: str | None,
# ) -> tuple[float, bool]:
#     if minimum_salary is None:
#         return 50.0, False

#     if (
#         not preferred_currency
#         or not job_currency
#         or preferred_currency.upper() != job_currency.upper()
#     ):
#         return 50.0, False

#     highest_known = (
#         job_max if job_max is not None else job_min
#     )

#     if highest_known is None:
#         return 50.0, False

#     return (
#         100.0 if highest_known >= minimum_salary
#         else 0.0,
#         True,
#     )


def score_salary(
    minimum_salary: int | None,
    preferred_currency: str | None,
    job_min: int | None,
    job_max: int | None,
    job_currency: str | None,
) -> tuple[float, bool]:
    """
    Day 12 safe behavior.

    We have salary amounts and currencies, but the
    database does not record pay periods.

    Return neutral/unknown until the job and
    candidate salary periods can be compared.
    """

    return 50.0, False



def match_job(
    candidate: CandidateInput,
    job: JobInput,
    preferences: MatchPreferences | None = None,
) -> MatchResult:
    """Calculate the weighted Day 11 match score."""

    prefs = preferences or MatchPreferences()
    warnings: list[str] = []

    # Skills
    skills, matched, missing, skills_known = score_skills(
        candidate.skills,
        f"{job.title}\n{job.description}",
    )
    if not skills_known:
        warnings.append(
            "No catalog skills detected in job text"
        )

    # Experience
    experience, experience_known = score_experience(
        candidate.years_experience,
        job.description,
    )
    if not experience_known:
        warnings.append(
            "Experience comparison has insufficient data"
        )

    # Job title
    title, title_known = score_title(
        candidate.titles,
        job.title,
        candidate.skills,
    )
    if not title_known:
        warnings.append(
            "Candidate job title information is unavailable"
        )

    # Location
    location, location_known = score_location(
        candidate.location,
        job.location,
        prefs.preferred_location,
        job.work_mode,
    )

    if job.work_mode == "remote":
        warnings.append(
        "Remote work does not guarantee geographic "
        "hiring eligibility; verify employer restrictions"
    )
    
    if not location_known:
        warnings.append(
            "Location comparison has insufficient data"
        )

    # Work mode preference
    preference, preference_known = score_preference(
        prefs.preferred_work_mode,
        job.work_mode,
    )
    if not preference_known:
        warnings.append(
            "Work-mode preference was not fully specified"
        )

    # Salary
    salary, salary_known = score_salary(
        prefs.minimum_salary,
        prefs.salary_currency,
        job.salary_min,
        job.salary_max,
        job.salary_currency,
    )
    if not salary_known:
        warnings.append(
            "Salary comparison has insufficient comparable data"
        )

    breakdown = {
        "skills": round(skills, 2),
        "experience": round(experience, 2),
        "title": round(title, 2),
        "location": round(location, 2),
        "preferences": round(preference, 2),
        "salary": round(salary, 2),
    }

    total = sum(
        breakdown[name] * weight
        for name, weight in WEIGHTS.items()
    )

    
    title_technologies = set(extract_skills(job.title))

    missing_title_technologies = (
        title_technologies & set(missing)
    )

    if missing_title_technologies:
        warnings.append(
            "Job title mentions technology not listed "
            "by candidate: "
            + ", ".join(
                sorted(missing_title_technologies)
            )
        )

    return MatchResult(
        job_id=job.id,
        score=round(total, 2),
        breakdown=breakdown,
        matched_skills=matched,
        missing_skills=missing,
        warnings=warnings,
    )

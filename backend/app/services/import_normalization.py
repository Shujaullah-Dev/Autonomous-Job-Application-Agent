
from datetime import date


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""

    return " ".join(
        value.strip().casefold().split()
    )


def skill_key(name: str) -> str:
    return normalize_text(name)


def experience_key(
    company_name: str,
    job_title: str,
    start_date: date,
    end_date: date | None,
) -> tuple:
    return (
        normalize_text(company_name),
        normalize_text(job_title),
        start_date,
        end_date,
    )


def education_key(
    institution: str,
    degree: str,
    start_date: date,
    end_date: date | None,
) -> tuple:
    return (
        normalize_text(institution),
        normalize_text(degree),
        start_date,
        end_date,
    )

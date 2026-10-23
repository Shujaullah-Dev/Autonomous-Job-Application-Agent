
import re
from datetime import date

from app.schemas.resume_analysis import (
    ResumeEducation,
    ResumeExperience,
)


def parse_month(value: str) -> date | None:
    value = value.strip()

    if value.lower() in {
        "present", "current", "ongoing", ""
    }:
        return None

    if not re.fullmatch(r"\d{4}-\d{2}", value):
        return None

    try:
        return date.fromisoformat(value + "-01")
    except ValueError:
        return None


def read_sections(text: str) -> dict[str, list[dict]]:
    sections = {
        "experience": [],
        "education": [],
    }

    current_section = None
    current_record = {}

    def save_record():
        nonlocal current_record

        if current_section and current_record:
            sections[current_section].append(current_record)

        current_record = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            save_record()
            continue

        heading = line.upper().rstrip(":")

        if heading in {
            "EXPERIENCE", "WORK EXPERIENCE"
        }:
            save_record()
            current_section = "experience"
            continue

        if heading in {
            "EDUCATION", "ACADEMIC BACKGROUND"
        }:
            save_record()
            current_section = "education"
            continue

        if current_section is None:
            continue

        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()

        allowed_keys = {
            "experience": {
                "job title", "company", "start", "end"
            },
            "education": {
                "institution", "degree", "start", "end"
            },
        }

        if key in allowed_keys[current_section]:
            # A repeated field begins another record.
            if key in current_record:
                save_record()

            current_record[key] = value

    save_record()
    return sections


def extract_experiences(text: str) -> list[ResumeExperience]:
    records = read_sections(text)["experience"]
    results = []

    for record in records:
        if not any(
            record.get(key)
            for key in ("job title", "company")
        ):
            continue

        results.append(
            ResumeExperience(
                job_title=record.get("job title"),
                company_name=record.get("company"),
                start_date=parse_month(
                    record.get("start", "")
                ),
                end_date=parse_month(
                    record.get("end", "")
                ),
            )
        )

    return results


def extract_educations(text: str) -> list[ResumeEducation]:
    records = read_sections(text)["education"]
    results = []

    for record in records:
        if not any(
            record.get(key)
            for key in ("institution", "degree")
        ):
            continue

        results.append(
            ResumeEducation(
                institution=record.get("institution"),
                degree=record.get("degree"),
                start_date=parse_month(
                    record.get("start", "")
                ),
                end_date=parse_month(
                    record.get("end", "")
                ),
            )
        )

    return results

import re
from datetime import date, datetime

from app.schemas.resume_analysis import (
    ResumeEducation,
    ResumeExperience,
)


HEADINGS = {
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "employment history": "experience",
    "career history": "experience",
    "relevant experience": "experience",
    "internships": "experience",
    "education": "education",
    "academic background": "education",
    "educational background": "education",
    "academic qualifications": "education",
    "qualifications": "education",
}

STOP_HEADINGS = {
    "summary", "professional summary", "profile",
    "about me", "technical skills", "skills",
    "skills & interests", "skills and interests",
    "projects", "featured projects",
    "personal projects", "certifications",
    "certificates", "awards", "languages",
    "interests", "references", "publications",
    "volunteering", "achievements",
}

MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|"
    r"Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
    r"Nov(?:ember)?|Dec(?:ember)?)"
)

DATE_TOKEN = (
    rf"(?:\d{{4}}-\d{{2}}|"
    rf"\d{{2}}/\d{{4}}|"
    rf"{MONTH}\.?\s+\d{{4}}|"
    rf"\d{{4}}|Present|Current|Ongoing)"
)

RANGE = re.compile(
    rf"(?P<start>{DATE_TOKEN})"
    rf"\s*(?:-|–|—|\bto\b)\s*"
    rf"(?P<end>{DATE_TOKEN})",
    re.IGNORECASE,
)

DEGREE = re.compile(
    r"\b(?:Bachelor(?:'s)?|Master(?:'s)?|"
    r"Doctorate|Ph\.?D|B\.?S\.?|BSc|"
    r"B\.?A\.?|M\.?S\.?|MSc|"
    r"MBA|F\.?Sc|Intermediate|"
    r"Matriculation|Diploma|Associate)\b",
    re.IGNORECASE,
)

EXPERIENCE_KEYS = {
    "job title": "job_title",
    "position": "job_title",
    "role": "job_title",
    "company": "company_name",
    "employer": "company_name",
    "organization": "company_name",
    "start": "start_date_text",
    "start date": "start_date_text",
    "end": "end_date_text",
    "end date": "end_date_text",
}

EDUCATION_KEYS = {
    "institution": "institution",
    "university": "institution",
    "school": "institution",
    "degree": "degree",
    "qualification": "degree",
    "start": "start_date_text",
    "start date": "start_date_text",
    "end": "end_date_text",
    "end date": "end_date_text",
}


def parse_month(value: str) -> date | None:
    value = value.strip().replace(".", "")

    if value.lower() in {
        "", "present", "current", "ongoing"
    }:
        return None

    for fmt in (
        "%Y-%m", "%m/%Y", "%b %Y", "%B %Y",
    ):
        try:
            parsed = datetime.strptime(value, fmt)
            return date(parsed.year, parsed.month, 1)
        except ValueError:
            pass

    # Preserve year-only text rather than guessing a month.
    return None


def clean_lines(text: str) -> list[str]:
    lines = []

    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()

        if line:
            lines.append(line)

    return lines


def get_sections(text: str) -> dict[str, list[str]]:
    sections = {"experience": [], "education": []}
    active = None

    for line in clean_lines(text):
        heading = line.strip(" :").lower()

        if heading in HEADINGS:
            active = HEADINGS[heading]
            continue

        if heading in STOP_HEADINGS:
            active = None
            continue

        if active:
            sections[active].append(line)

    return sections


def get_range(line: str):
    match = RANGE.search(line)

    if match is None:
        return None

    remaining = (
        line[:match.start()] + " " + line[match.end():]
    ).strip(" ,-–—")

    return (
        remaining.strip(),
        match.group("start"),
        match.group("end"),
    )


def labeled_records(
    lines: list[str],
    mapping: dict[str, str],
):
    records = []
    current = {}

    for line in lines:
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        field = mapping.get(key.strip().lower())

        if not field:
            continue

        if field in current:
            records.append(current)
            current = {}

        current[field] = value.strip()

    if current:
        records.append(current)

    return records


def extract_experiences(
    text: str,
) -> list[ResumeExperience]:
    lines = get_sections(text)["experience"]
    records = []

    # First: explicit labeled records.
    for item in labeled_records(lines, EXPERIENCE_KEYS):
        if item.get("company_name") or item.get("job_title"):
            records.append(
                ResumeExperience(
                    company_name=item.get("company_name"),
                    job_title=item.get("job_title"),
                    start_date=parse_month(
                        item.get("start_date_text", "")
                    ),
                    end_date=parse_month(
                        item.get("end_date_text", "")
                    ),
                    start_date_text=item.get(
                        "start_date_text"
                    ),
                    end_date_text=item.get(
                        "end_date_text"
                    ),
                )
            )

    # If explicit labels identified records, do not
    # reinterpret the same block as unlabeled records.
    if records:
        return records

    # Second: company — title — date and related layouts.
    i = 0
    while i < len(lines):
        line = lines[i]
        dated = get_range(line)

        # Company — Job Title — Dates on one line.
        if dated:
            prefix, start, end = dated

            match = re.match(
                r"(.+?)\s+[—–]\s+(.+)",
                prefix,
            )

            if match:
                records.append(
                    ResumeExperience(
                        company_name=match.group(1).strip(),
                        job_title=match.group(2).strip(),
                        start_date=parse_month(start),
                        end_date=parse_month(end),
                        start_date_text=start,
                        end_date_text=end,
                    )
                )
                i += 1
                continue

        # Company line, title + date on following line.
        if i + 1 < len(lines):
            next_dated = get_range(lines[i + 1])

            if next_dated:
                title, start, end = next_dated

                if title and not get_range(line):
                    records.append(
                        ResumeExperience(
                            company_name=line,
                            job_title=title,
                            start_date=parse_month(start),
                            end_date=parse_month(end),
                            start_date_text=start,
                            end_date_text=end,
                        )
                    )
                    i += 2
                    continue

        # Company, title and dates each on separate lines.
        if i + 2 < len(lines):
            date_line = get_range(lines[i + 2])

            if date_line and not date_line[0]:
                if not get_range(line) and not get_range(
                    lines[i + 1]
                ):
                    _, start, end = date_line

                    records.append(
                        ResumeExperience(
                            company_name=line,
                            job_title=lines[i + 1],
                            start_date=parse_month(start),
                            end_date=parse_month(end),
                            start_date_text=start,
                            end_date_text=end,
                        )
                    )
                    i += 3
                    continue

        i += 1

    return records


def extract_educations(
    text: str,
) -> list[ResumeEducation]:
    lines = get_sections(text)["education"]
    records = []

    # First: explicitly labeled education.
    for item in labeled_records(lines, EDUCATION_KEYS):
        if item.get("institution") or item.get("degree"):
            records.append(
                ResumeEducation(
                    institution=item.get("institution"),
                    degree=item.get("degree"),
                    start_date=parse_month(
                        item.get("start_date_text", "")
                    ),
                    end_date=parse_month(
                        item.get("end_date_text", "")
                    ),
                    start_date_text=item.get(
                        "start_date_text"
                    ),
                    end_date_text=item.get(
                        "end_date_text"
                    ),
                )
            )

    if records:
        return records

    # Second: degree followed by institution,
    # institution followed by degree, with optional dates.
    i = 0

    while i < len(lines):
        line = lines[i]
        date_info = get_range(line)

        text_part = date_info[0] if date_info else line

        if i + 1 >= len(lines):
            break

        next_line = lines[i + 1]
        next_info = get_range(next_line)
        next_text = (
            next_info[0] if next_info else next_line
        )

        first_is_degree = bool(DEGREE.search(text_part))
        second_is_degree = bool(DEGREE.search(next_text))

        if first_is_degree == second_is_degree:
            i += 1
            continue

        degree = (
            text_part if first_is_degree else next_text
        )
        institution = (
            next_text if first_is_degree else text_part
        )

        dates = date_info or next_info
        consumed = 2

        if not dates and i + 2 < len(lines):
            third = get_range(lines[i + 2])
            if third and not third[0]:
                dates = third
                consumed = 3

        start = dates[1] if dates else None
        end = dates[2] if dates else None

        records.append(
            ResumeEducation(
                institution=institution,
                degree=degree,
                start_date=parse_month(start or ""),
                end_date=parse_month(end or ""),
                start_date_text=start,
                end_date_text=end,
            )
        )

        i += consumed

    return records

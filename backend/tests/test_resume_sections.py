
from datetime import date

from app.services.resume_sections import (
    extract_educations,
    extract_experiences,
    parse_month,
)

SAMPLE_RESUME = """
EXPERIENCE
Job Title: Backend Developer
Company: Example Technologies
Start: 2023-01
End: Present

EDUCATION
Institution: Example University
Degree: BS Computer Science
Start: 2019-09
End: 2023-06
"""


def test_parse_month():
    assert parse_month("2023-01") == date(2023, 1, 1)
    assert parse_month("Present") is None
    assert parse_month("2023-13") is None


def test_extract_experience():
    result = extract_experiences(SAMPLE_RESUME)

    assert len(result) == 1
    assert result[0].job_title == "Backend Developer"
    assert result[0].company_name == "Example Technologies"
    assert result[0].start_date == date(2023, 1, 1)
    assert result[0].end_date is None


def test_extract_education():
    result = extract_educations(SAMPLE_RESUME)

    assert len(result) == 1
    assert result[0].institution == "Example University"
    assert result[0].degree == "BS Computer Science"
    assert result[0].end_date == date(2023, 6, 1)


def test_unstructured_text():
    result = extract_experiences(
        "Worked on backend systems and API design"
    )

    assert result == []
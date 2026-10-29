
import uuid
from datetime import date
from unittest.mock import patch

import httpx

from app.schemas.resume_analysis import (
    ResumeContact,
    ResumeEducation,
    ResumeExperience,
)
from app.services.resume_analysis import analyze_resume_text
from app.services.resume_groq import (
    GroqUnavailable,
    extract_groq,
    parsed_date,
)
from app.services.resume_sections import (
    extract_educations,
    extract_experiences,
)


SAMPLE = """
WORK EXPERIENCE
Northstar Technologies
Software Engineer Jan 2023 - Dec 2024

EDUCATION
Riverside University
BS Computer Science
"""


def test_local_experience():
    results = extract_experiences(SAMPLE)

    assert len(results) == 1
    assert results[0].company_name == "Northstar Technologies"
    assert results[0].job_title == "Software Engineer"
    assert results[0].start_date == date(2023, 1, 1)


def test_local_education_without_dates():
    results = extract_educations(SAMPLE)

    assert len(results) == 1
    assert results[0].institution == "Riverside University"
    assert results[0].degree == "BS Computer Science"
    assert results[0].start_date is None


def test_year_only_does_not_invent_month():
    assert parsed_date("2022") is None
    assert parsed_date("Present") is None
    assert parsed_date("Jun 2024") == date(2024, 6, 1)


def test_empty_sections_remain_empty():
    text = """
    SUMMARY
    Motivated developer with personal projects.
    SKILLS
    Python
    """

    assert extract_experiences(text) == []
    assert extract_educations(text) == []


def test_groq_success(monkeypatch):
    monkeypatch.setattr(
        "app.services.resume_analysis.settings.resume_ai_enabled",
        True,
    )

    ai_result = (
        ResumeContact(),
        [
            ResumeExperience(
                company_name="Northstar Technologies",
                job_title="Software Engineer",
            )
        ],
        [
            ResumeEducation(
                institution="Riverside University",
                degree="BS Computer Science",
            )
        ],
        ["Python"],
        [],
    )

    with patch(
        "app.services.resume_analysis.extract_groq",
        return_value=ai_result,
    ):
        result = analyze_resume_text(
            uuid.uuid4(),
            SAMPLE,
        )

    assert result.parser_used == "groq"
    assert result.fallback_used is False
    assert len(result.experiences) == 1


def test_rate_limit_automatically_falls_back(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.resume_analysis.settings.resume_ai_enabled",
        True,
    )

    with patch(
        "app.services.resume_analysis.extract_groq",
        side_effect=GroqUnavailable(
            "rate_limit", 429
        ),
    ):
        result = analyze_resume_text(
            uuid.uuid4(),
            SAMPLE,
        )

    assert result.parser_used == "local"
    assert result.fallback_used is True
    assert len(result.experiences) == 1
    assert len(result.educations) == 1
    assert any(
        "rate_limit" in warning
        for warning in result.warnings
    )


def test_timeout_automatically_falls_back(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.resume_analysis.settings.resume_ai_enabled",
        True,
    )

    with patch(
        "app.services.resume_analysis.extract_groq",
        side_effect=GroqUnavailable("timeout"),
    ):
        result = analyze_resume_text(
            uuid.uuid4(),
            SAMPLE,
        )

    assert result.parser_used == "local"
    assert result.fallback_used is True


def test_real_http_429_handled(monkeypatch):
    monkeypatch.setattr(
        "app.services.resume_groq.settings.groq_api_key",
        "test-key",
    )

    def fake_post(*args, **kwargs):
        return httpx.Response(
            429,
            json={
                "error": {
                    "message": "Rate limit exceeded"
                }
            },
            request=httpx.Request(
                "POST",
                "https://api.groq.com/openai/v1/chat/completions",
            ),
        )

    monkeypatch.setattr(
        "app.services.resume_groq.httpx.post",
        fake_post,
    )

    try:
        extract_groq(SAMPLE)
        assert False, "Expected GroqUnavailable"
    except GroqUnavailable as exc:
        assert exc.reason == "rate_limit"
        assert exc.status_code == 429

import json

import httpx
import pytest
from app.services.resume_groq import (
    GroqUnavailable,
    extract_groq,
    parse_date,
)


def test_month_year_conversion():
    assert parse_date("2024") is None
    assert parse_date("Present") is None
    assert parse_date("Jun 2024").isoformat() == "2024-06-01"


def test_groq_rate_limit(monkeypatch):
    from app.services import resume_groq

    monkeypatch.setattr(
        resume_groq.settings,
        "groq_api_key",
        "test-key",
    )

    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(
            429,
            json={"error": {"message": "Rate limited"}},
        ),
    )

    with pytest.raises(GroqUnavailable) as exc:
        extract_groq("Example CV")

    assert exc.value.reason == "rate_limit"
    assert exc.value.status_code == 429


def test_groq_valid_response(monkeypatch):
    from app.services import resume_groq

    monkeypatch.setattr(
        resume_groq.settings,
        "groq_api_key",
        "test-key",
    )

    source = """
    EXPERIENCE
    Example Technology
    Backend Engineer
    Jan 2022 - Dec 2023

    EDUCATION
    Northern University
    BS Software Engineering

    SKILLS
    Python
    """

    model_output = {
        "contact": {"email": None, "phone": None},
        "skills": ["Python"],
        "experiences": [
            {
                "company_name": "Example Technology",
                "job_title": "Backend Engineer",
                "start_date_text": "Jan 2022",
                "end_date_text": "Dec 2023",
                "evidence": (
                    "Example Technology\n"
                    "Backend Engineer\n"
                    "Jan 2022 - Dec 2023"
                ),
            }
        ],
        "educations": [
            {
                "institution": "Northern University",
                "degree": "BS Software Engineering",
                "start_date_text": None,
                "end_date_text": None,
                "evidence": (
                    "Northern University\n"
                    "BS Software Engineering"
                ),
            }
        ],
    }

    fake_response = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps(model_output)
                },
            }
        ]
    }

    monkeypatch.setattr(
        httpx,
        "post",
        lambda *args, **kwargs: httpx.Response(
            200,
            json=fake_response,
        ),
    )

    contact, experiences, education, skills, issues = (
        extract_groq(source)
    )

    assert len(experiences) == 1
    assert len(education) == 1
    assert education[0].start_date is None
    assert skills == ["Python"]
    assert issues == []


def test_missing_key(monkeypatch):
    from app.services import resume_groq

    monkeypatch.setattr(
        resume_groq.settings,
        "groq_api_key",
        "",
    )

    with pytest.raises(GroqUnavailable) as exc:
        extract_groq("Test document")

    assert exc.value.reason == "missing_api_key"
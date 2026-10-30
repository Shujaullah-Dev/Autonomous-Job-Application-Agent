
import uuid
from unittest.mock import patch

from app.schemas.resume_analysis import (
    ResumeContact,
    ResumeEducation,
    ResumeExperience,
)
from app.services.resume_analysis import analyze_resume_text
from app.services.resume_groq import GroqUnavailable

RESUME = """
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

SKILLS
Python, FastAPI
"""


def test_groq_success(monkeypatch):
    from app.services import resume_analysis

    monkeypatch.setattr(
        resume_analysis.settings,
        "resume_ai_enabled",
        True,
    )

    fake_result = (
        ResumeContact(),
        [
            ResumeExperience(
                company_name="Example Technologies",
                job_title="Backend Developer",
            )
        ],
        [
            ResumeEducation(
                institution="Example University",
                degree="BS Computer Science",
            )
        ],
        ["Python"],
        [],
    )

    with patch(
        "app.services.resume_analysis.extract_groq",
        return_value=fake_result,
    ):
        result = analyze_resume_text(
            uuid.uuid4(),
            RESUME,
        )

    assert result.parser_used == "groq"
    assert result.fallback_used is False
    assert len(result.experiences) == 1
    assert len(result.educations) == 1


def test_rate_limit_activates_fallback(monkeypatch):
    from app.services import resume_analysis

    monkeypatch.setattr(
        resume_analysis.settings,
        "resume_ai_enabled",
        True,
    )

    with patch(
        "app.services.resume_analysis.extract_groq",
        side_effect=GroqUnavailable("rate_limit", 429),
    ):
        result = analyze_resume_text(
            uuid.uuid4(),
            RESUME,
        )

    assert result.parser_used == "local"
    assert result.fallback_used is True
    assert len(result.experiences) == 1
    assert len(result.educations) == 1


def test_timeout_activates_fallback(monkeypatch):
    from app.services import resume_analysis

    monkeypatch.setattr(
        resume_analysis.settings,
        "resume_ai_enabled",
        True,
    )

    with patch(
        "app.services.resume_analysis.extract_groq",
        side_effect=GroqUnavailable("timeout"),
    ):
        result = analyze_resume_text(
            uuid.uuid4(),
            RESUME,
        )

    assert result.parser_used == "local"
    assert result.fallback_used is True


def test_local_mode(monkeypatch):
    from app.services import resume_analysis

    monkeypatch.setattr(
        resume_analysis.settings,
        "resume_ai_enabled",
        False,
    )

    result = analyze_resume_text(
        uuid.uuid4(),
        RESUME,
    )

    assert result.parser_used == "local"
    assert result.fallback_used is False
    assert len(result.experiences) == 1

"""Unit tests for grounded application drafts."""

import json

import pytest
from app.services.application_materials import (
    ApplicationFacts,
    generate_application_draft,
)
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda


def sample_facts():
    return ApplicationFacts(
        candidate_name="Alex Morgan",
        candidate_email="alex@example.test",
        job_id=101,
        job_title="Python Backend Developer",
        company_name="Example Technologies",
        job_url="https://careers.example.test/jobs/101",
        shortlist_score=78.5,
        relevant_skills=("Python", "FastAPI"),
        experiences=(
            "AI Intern at Example Company",
        ),
        educations=(
            "BS Artificial Intelligence at Example University",
        ),
        work_mode=None,
        location="Islamabad, Pakistan",
    )


def test_generates_cover_letter():
    result = generate_application_draft(
        sample_facts()
    )

    assert result.generation_mode == "deterministic"
    assert result.llm_used is False

    assert "Alex Morgan" in result.cover_letter
    assert "Python Backend Developer" in result.cover_letter
    assert "Example Technologies" in result.cover_letter
    assert "Python" in result.cover_letter
    assert "FastAPI" in result.cover_letter


def test_preserves_real_skills():
    result = generate_application_draft(
        sample_facts()
    )

    assert result.resume_skills == (
        "Python",
        "FastAPI",
    )

    assert "Rust" not in result.cover_letter
    assert "AWS Certified" not in result.cover_letter


def test_preserves_work_history():
    result = generate_application_draft(
        sample_facts()
    )

    assert result.resume_experiences == (
        "AI Intern at Example Company",
    )

    assert "AI Intern" in result.cover_letter


def test_no_invented_proficiency():
    result = generate_application_draft(
        sample_facts()
    )

    assert "expert" not in result.cover_letter.lower()
    assert "advanced" not in result.cover_letter.lower()
    assert "five years" not in result.cover_letter.lower()


def test_ai_disabled_never_calls_model():
    def fail(_):
        raise AssertionError(
            "LLM must not be called"
        )

    result = generate_application_draft(
        sample_facts(),
        use_ai=False,
        model=RunnableLambda(fail),
    )

    assert result.llm_used is False


def test_ai_reorders_verified_evidence_only():
    original = generate_application_draft(
        sample_facts()
    )

    count = len(original.evidence_used)

    fake_output = json.dumps(
        {
            "reason_order": list(reversed(range(count))),
            "caution_order": [],
        }
    )

    fake_model = RunnableLambda(
        lambda prompt: AIMessage(
            content=fake_output
        )
    )

    result = generate_application_draft(
        sample_facts(),
        use_ai=True,
        model=fake_model,
    )

    assert result.generation_mode == "langchain_groq"
    assert result.llm_used is True

    assert result.evidence_used == tuple(
        reversed(original.evidence_used)
    )

    assert set(result.evidence_used) == set(
        original.evidence_used
    )


def test_invalid_ai_output_uses_fallback():
    fake_model = RunnableLambda(
        lambda prompt: AIMessage(
            content='{"new_qualification": "Rust expert"}'
        )
    )

    result = generate_application_draft(
        sample_facts(),
        use_ai=True,
        model=fake_model,
    )

    assert result.generation_mode == "fallback"
    assert result.llm_used is False
    assert "Rust expert" not in result.cover_letter


def test_missing_model_uses_fallback():
    result = generate_application_draft(
        sample_facts(),
        use_ai=True,
        model=None,
    )

    assert result.generation_mode == "fallback"
    assert result.warnings


def test_work_mode_unknown_has_warning():
    result = generate_application_draft(
        sample_facts()
    )

    assert any(
        "work mode is unknown" in warning
        for warning in result.warnings
    )


def test_invalid_job_id_rejected():
    from dataclasses import replace

    facts = replace(
        sample_facts(),
        job_id=0,
    )

    with pytest.raises(ValueError):
        generate_application_draft(facts)

import pytest
from app.services.job_matching import (
    CandidateInput,
    JobInput,
    MatchPreferences,
    match_job,
    score_experience,
    score_location,
    score_skills,
)


@pytest.fixture
def candidate():
    return CandidateInput(
        skills=[
            "Python",
            "FastAPI",
            "PostgreSQL",
        ],
        titles=[
            "Backend Developer",
        ],
        years_experience=3,
        location="Islamabad",
    )


@pytest.fixture
def job():
    return JobInput(
        id=1,
        title="Backend Developer",
        description=(
            "Required: Python, FastAPI, Docker. "
            "2+ years of experience."
        ),
        location="Islamabad",
        work_mode="remote",
        salary_min=80000,
        salary_max=150000,
        salary_currency="PKR",
    )


def test_skill_matching():
    score, matched, missing, known = score_skills(
        ["Python", "FastAPI"],
        "Python, FastAPI, Docker",
    )

    assert known is True
    assert score == pytest.approx(66.6667, rel=0.001)
    assert matched == ["FastAPI", "Python"]
    assert missing == ["Docker"]


def test_experience_requirement():
    score, known = score_experience(
        3,
        "Minimum 2+ years of experience",
    )

    assert known is True
    assert score == 100.0


def test_experience_shortfall():
    score, known = score_experience(
        2,
        "5 years of professional experience",
    )

    assert known is True
    assert score == 40.0


def test_full_matching(candidate, job):
    result = match_job(
        candidate,
        job,
        MatchPreferences(
            preferred_work_mode="remote",
            preferred_location="Islamabad",
            minimum_salary=100000,
            salary_currency="PKR",
        ),
    )

    assert 0 <= result.score <= 100
    assert result.breakdown["title"] == 100
    assert result.breakdown["experience"] == 100
    assert result.breakdown["salary"] == 50
    assert "Docker" in result.missing_skills


def test_currency_mismatch_is_unknown(candidate, job):
    result = match_job(
        candidate,
        job,
        MatchPreferences(
            minimum_salary=50000,
            salary_currency="USD",
        ),
    )

    assert result.breakdown["salary"] == 50
    assert any(
        "Salary comparison" in warning
        for warning in result.warnings
    )


def test_unknown_requirements_are_not_zero(candidate):
    job = JobInput(
        id=2,
        title="Research Associate",
        description="Interesting research position",
        location=None,
        work_mode=None,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
    )

    result = match_job(candidate, job)

    assert result.breakdown["skills"] == 0
    assert result.breakdown["experience"] == 50
    assert result.warnings


def test_score_is_deterministic(candidate, job):
    first = match_job(candidate, job)
    second = match_job(candidate, job)

    assert first.score == second.score
    assert first.breakdown == second.breakdown


def test_remote_does_not_mean_global_eligibility():
    score, known = score_location(
        "Islamabad",
        "New York, New York",
        "Islamabad",
        "remote",
    )

    assert score == 50.0
    assert known is False


def test_matching_local_location():
    score, known = score_location(
        "Islamabad",
        "Islamabad, Pakistan",
        "Islamabad",
        "remote",
    )

    assert score == 80.0
    assert known is True


def test_onsite_location_mismatch():
    score, known = score_location(
        "Islamabad",
        "Lahore, Pakistan",
        "Islamabad",
        "onsite",
    )

    assert score == 0.0
    assert known is True
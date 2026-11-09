
import pytest
from app.models.job import Job
from app.services.job_matching import (
    CandidateInput,
    JobInput,
    MatchPreferences,
    match_job,
    score_experience,
    score_location,
    score_skills,
    score_title,
)
from app.services.matching_queries import load_active_jobs
from app.services.resume_skills import extract_skills
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def candidate():
    return CandidateInput(
        skills=[
            "Python",
            "FastAPI",
            "PostgreSQL",
            "REST APIs",
        ],
        titles=["AI Intern"],
        years_experience=0,
        location="Islamabad",
    )


def make_job(
    job_id,
    title,
    description,
    location,
    work_mode,
):
    return JobInput(
        id=job_id,
        title=title,
        description=description,
        location=location,
        work_mode=work_mode,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
    )


def test_rust_is_recognized():
    skills = extract_skills(
        "Build RuST services and REST APIs."
    )

    assert "Rust" in skills
    assert "REST API" in skills


def test_skill_aliases_match():
    score, matched, missing, known = score_skills(
        ["REST APIs"],
        "Build a REST API",
    )

    assert known is True
    assert score == 100.0
    assert matched == ["REST API"]
    assert missing == []


def test_rust_remains_missing_from_candidate():
    score, matched, missing, known = score_skills(
        candidate().skills,
        "Build Rust, Python, FastAPI and PostgreSQL services",
    )

    assert known is True
    assert score == 75.0
    assert matched == [
        "FastAPI",
        "PostgreSQL",
        "Python",
    ]
    assert missing == ["Rust"]


def test_unknown_skills_receive_no_positive_credit():
    score, matched, missing, known = score_skills(
        candidate().skills,
        "Support customer onboarding",
    )

    assert score == 0.0
    assert matched == []
    assert missing == []
    assert known is False


def test_python_skill_supports_backend_title():
    score, known = score_title(
        ["AI Intern"],
        "Python Backend Developer",
        candidate().skills,
    )

    assert known is True
    assert score == 100.0


def test_unlisted_rust_does_not_match_title():
    score, known = score_title(
        ["AI Intern"],
        "Rust Developer",
        candidate().skills,
    )

    assert known is True
    assert score == 0.0


def test_company_history_is_not_experience_requirement():
    score, known = score_experience(
        0,
        "Our company has over 20 years of experience.",
    )

    assert known is False
    assert score == 50.0


def test_real_experience_requirement():
    score, known = score_experience(
        2,
        "Minimum 5 years of professional experience",
    )

    assert known is True
    assert score == 40.0


def test_local_location_is_recognized():
    score, known = score_location(
        "Islamabad",
        "Islamabad, Pakistan",
        "Islamabad",
        "remote",
    )

    assert score == 80.0
    assert known is True


def test_remote_is_not_automatically_worldwide():
    score, known = score_location(
        "Islamabad",
        "New York, New York",
        "Islamabad",
        "remote",
    )

    assert score == 50.0
    assert known is False


def test_backend_job_ranks_above_rust_and_sales():
    prefs = MatchPreferences(
        preferred_work_mode="remote",
        preferred_location="Islamabad",
    )

    backend = make_job(
        1,
        "Python Backend Developer",
        "Build REST APIs using Python, FastAPI and PostgreSQL.",
        "Islamabad, Pakistan",
        "remote",
    )

    rust = make_job(
        5,
        "Rust Developer",
        "Build Rust and Python APIs using FastAPI and PostgreSQL.",
        "Lahore, Pakistan",
        "remote",
    )

    sales = make_job(
        26,
        "Sales Engineer",
        "Help customers with presentations and sales.",
        "New York, New York",
        "remote",
    )

    backend_result = match_job(candidate(), backend, prefs)
    rust_result = match_job(candidate(), rust, prefs)
    sales_result = match_job(candidate(), sales, prefs)

    assert (
        backend_result.score
        > rust_result.score
        > sales_result.score
    )
    assert "Rust" in rust_result.missing_skills


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Job.__table__.create(engine)

    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def test_matching_query_excludes_demo_jobs(db):
    records = [
        Job(
            title="Real Backend Role",
            company_name="Real Company",
            description="Build Python services.",
            job_url="https://careers.company.test/jobs/1",
            source="greenhouse:realcompany",
            is_active=True,
        ),
        Job(
            title="Manual Example",
            company_name="Example Technologies",
            description="Python API development.",
            job_url="https://example.com/jobs/1",
            source="manual",
            is_active=True,
        ),
        Job(
            title="Lever Demo",
            company_name="Lever Demo",
            description="Customer support.",
            job_url="https://jobs.lever.co/leverdemo/test123",
            source="lever:leverdemo",
            is_active=True,
        ),
        Job(
            title="Explicitly Fictional",
            company_name="Test Organization",
            description=(
                "This is a fictional job created solely "
                "for demonstration purposes."
            ),
            job_url="https://careers.company.test/jobs/2",
            source="greenhouse:testing",
            is_active=True,
        ),
    ]

    db.add_all(records)
    db.commit()

    result = load_active_jobs(db)

    titles = [job.title for job, _ in result]

    assert titles == ["Real Backend Role"]

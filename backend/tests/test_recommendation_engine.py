
from app.models.job import Job
from app.services.job_matching import (
    CandidateInput,
    JobInput,
    MatchPreferences,
)
from app.services.recommendation_engine import (
    filter_job_pool,
    rank_recommendations,
)
from app.services.recommendation_metrics import evaluate_ranking


def candidate():
    return CandidateInput(
        skills=["Python", "FastAPI", "PostgreSQL"],
        titles=["AI Intern"],
        years_experience=0,
        location="Islamabad",
    )


def job_pair(job_id, title, description, work_mode="remote"):
    job = Job(
        id=job_id,
        title=title,
        company_name="Test Company",
        description=description,
        job_url=f"https://careers.company.test/jobs/{job_id}",
        source="greenhouse:company",
        location="Islamabad, Pakistan",
        work_mode=work_mode,
        is_active=True,
    )

    data = JobInput(
        id=job_id,
        title=title,
        description=description,
        location=job.location,
        work_mode=work_mode,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
    )

    return job, data


def test_relevance_gate_excludes_unrelated_sales():
    jobs = [
        job_pair(
            1,
            "Python Backend Developer",
            "Build Python and FastAPI services",
        ),
        job_pair(
            2,
            "Sales Representative",
            "Customer outreach and presentations",
        ),
    ]

    outcome = rank_recommendations(
        candidate(),
        jobs,
        preferences=MatchPreferences(),
        mode="rules",
        min_score=0,
    )

    assert [item.job.id for item in outcome.items] == [1]
    assert outcome.insufficient_evidence == 1


def test_missing_rust_does_not_block_related_python_job():
    jobs = [
        job_pair(
            1,
            "Rust Developer",
            "Python, FastAPI, PostgreSQL and Rust",
        )
    ]

    outcome = rank_recommendations(
        candidate(),
        jobs,
        preferences=MatchPreferences(),
        mode="rules",
        min_score=0,
    )

    assert len(outcome.items) == 1
    assert "Rust" in outcome.items[0].match.missing_skills
    assert outcome.items[0].cautions


def test_title_and_location_filters():
    jobs = [
        job_pair(1, "Python Developer", "Python APIs"),
        job_pair(2, "Data Analyst", "SQL reporting", "onsite"),
    ]

    filtered = filter_job_pool(
        jobs,
        work_mode="remote",
        title_contains="python",
        location_contains="Islamabad",
        source="greenhouse:company",
    )

    assert len(filtered) == 1
    assert filtered[0][0].id == 1


def test_score_threshold_can_return_empty():
    jobs = [
        job_pair(
            1,
            "Python Developer",
            "Build Python applications",
        )
    ]

    outcome = rank_recommendations(
        candidate(),
        jobs,
        preferences=MatchPreferences(),
        mode="rules",
        min_score=100,
    )

    assert outcome.items == ()
    assert outcome.below_threshold == 1


def test_hybrid_sort_uses_semantic_scores():
    jobs = [
        job_pair(1, "Python Developer", "Build Python APIs"),
        job_pair(2, "Python Developer", "Build Python APIs"),
    ]

    outcome = rank_recommendations(
        candidate(),
        jobs,
        preferences=MatchPreferences(),
        similarities={1: 0.20, 2: 0.90},
        mode="hybrid",
        min_score=0,
    )

    assert outcome.items[0].job.id == 2
    assert outcome.items[1].job.id == 1


def test_tied_scores_have_deterministic_order():
    jobs = [
        job_pair(5, "Python Developer", "Python APIs"),
        job_pair(2, "Python Developer", "Python APIs"),
    ]

    outcome = rank_recommendations(
        candidate(),
        jobs,
        preferences=MatchPreferences(),
        mode="rules",
        min_score=0,
    )

    assert [item.job.id for item in outcome.items] == [2, 5]


def test_explanations_include_evidence_and_cautions():
    jobs = [
        job_pair(
            1,
            "Python Backend Developer",
            "Python, FastAPI and Docker",
        )
    ]

    outcome = rank_recommendations(
        candidate(),
        jobs,
        preferences=MatchPreferences(),
        mode="rules",
        min_score=0,
    )

    result = outcome.items[0]

    assert result.reasons
    assert any("Python" in reason for reason in result.reasons)
    assert any(
        "Hiring-country" in caution
        for caution in result.cautions
    )


def test_offline_evaluation_metrics():
    result = evaluate_ranking(
        [101, 103, 105, 102, 104],
        {101, 102, 103},
        k=3,
    )

    assert result.precision_at_k == 0.6667
    assert result.recall_at_k == 0.6667
    assert result.reciprocal_rank_at_k == 1.0


def test_duplicate_ranked_ids_rejected():
    import pytest

    with pytest.raises(ValueError):
        evaluate_ranking([1, 1], {1}, k=2)


def test_unknown_work_mode_requires_opt_in():
    jobs = [
        job_pair(
            1, "Python Developer", "Python",
            work_mode="remote",
        ),
        job_pair(
            2, "Python Developer", "Python",
            work_mode=None,
        ),
        job_pair(
            3, "Python Developer", "Python",
            work_mode="onsite",
        ),
    ]

    strict = filter_job_pool(
        jobs,
        work_mode="remote",
    )

    include_unknown = filter_job_pool(
        jobs,
        work_mode="remote",
        include_unknown_work_mode=True,
    )

    assert [job.id for job, _ in strict] == [1]
    assert [job.id for job, _ in include_unknown] == [1, 2]
    assert include_unknown[1][0].work_mode is None

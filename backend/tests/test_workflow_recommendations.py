
"""Database integration for the LangGraph recommendation provider."""

import uuid

from app.db.base import Base
from app.models.candidate import CandidateProfile
from app.models.job import Job
from app.models.skill import CandidateSkill
from app.services.workflow_recommendations import (
    load_workflow_recommendations,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def test_provider_reads_candidate_and_ranks_jobs():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    candidate_id = uuid.uuid4()

    try:
        with Session(engine) as db:
            db.add(
                CandidateProfile(
                    id=candidate_id,
                    full_name="Workflow Tester",
                    email="workflow-test@example.test",
                    location="Islamabad",
                    years_experience=0,
                )
            )

            for skill in ["Python", "FastAPI"]:
                db.add(
                    CandidateSkill(
                        candidate_id=candidate_id,
                        name=skill,
                        proficiency_level="unassessed",
                    )
                )

            db.add(
                Job(
                    title="Python Backend Developer",
                    company_name="Test Employer",
                    description="Build Python and FastAPI services.",
                    job_url=(
                        "https://company.test/jobs/python"
                    ),
                    source="greenhouse:testcompany",
                    location="Islamabad, Pakistan",
                    work_mode=None,
                    is_active=True,
                )
            )

            db.add(
                Job(
                    title="Sales Representative",
                    company_name="Test Employer",
                    description="Make sales presentations.",
                    job_url="https://company.test/jobs/sales",
                    source="greenhouse:testcompany",
                    location="New York",
                    work_mode=None,
                    is_active=True,
                )
            )

            db.commit()

        state = {
            "candidate_id": str(candidate_id),
            "options": {
                "limit": 5,
                "min_score": 0,
                "work_mode": "remote",
                "include_unknown_work_mode": True,
            },
        }

        results = load_workflow_recommendations(
            state,
            session_factory=lambda: Session(engine),
        )

        assert len(results) == 1
        assert results[0]["title"] == (
            "Python Backend Developer"
        )
        assert results[0]["reasons"]
        assert any(
            "Work mode is unknown" in caution
            for caution in results[0]["cautions"]
        )

    finally:
        engine.dispose()

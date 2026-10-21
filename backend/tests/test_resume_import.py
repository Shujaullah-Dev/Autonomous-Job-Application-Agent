
import uuid

import pytest
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.candidate import CandidateProfile
from app.models.education import Education
from app.models.experience import WorkExperience
from app.models.skill import CandidateSkill
from app.schemas.resume_import import ResumeImportRequest
from app.services.resume_import import (
    CandidateNotFoundError,
    import_reviewed_resume,
)
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(
        engine,
        tables=[
            CandidateProfile.__table__,
            CandidateSkill.__table__,
            WorkExperience.__table__,
            Education.__table__,
        ],
    )

    yield engine

    engine.dispose()


@pytest.fixture
def candidate_id(engine):
    with Session(engine) as db:
        candidate = CandidateProfile(
            full_name="Alex Morgan",
            email="alex.day9@example.com",
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        return candidate.id


def sample_payload():
    return ResumeImportRequest.model_validate({
        "approved": True,
        "skills": [
            {
                "name": "Python",
                "proficiency_level": "advanced",
            }
        ],
        "experiences": [
            {
                "company_name": "Example Technologies",
                "job_title": "Backend Developer",
                "start_date": "2023-01-01",
                "is_current": True,
            }
        ],
        "educations": [
            {
                "institution": "Example University",
                "degree": "BS Computer Science",
                "start_date": "2019-09-01",
                "end_date": "2023-06-01",
            }
        ],
    })


def test_import_creates_records(engine, candidate_id):
    with Session(engine) as db:
        result = import_reviewed_resume(
            db,
            candidate_id,
            sample_payload(),
        )

        assert result.status == "success"
        assert result.skills.created == 1
        assert result.experiences.created == 1
        assert result.educations.created == 1

        skills = db.scalars(
            select(CandidateSkill).where(
                CandidateSkill.candidate_id == candidate_id
            )
        ).all()

        assert len(skills) == 1
        assert skills[0].name == "Python"


def test_repeat_import_skips_duplicates(
    engine, candidate_id
):
    with Session(engine) as db:
        payload = sample_payload()

        import_reviewed_resume(
            db, candidate_id, payload
        )

        result = import_reviewed_resume(
            db, candidate_id, payload
        )

        assert result.skills.created == 0
        assert result.skills.skipped == 1
        assert result.experiences.skipped == 1
        assert result.educations.skipped == 1


def test_duplicate_skills_within_request(
    engine, candidate_id
):
    payload = ResumeImportRequest.model_validate({
        "approved": True,
        "skills": [
            {
                "name": "Python",
                "proficiency_level": "advanced",
            },
            {
                "name": " python ",
                "proficiency_level": "advanced",
            },
        ],
    })

    with Session(engine) as db:
        result = import_reviewed_resume(
            db, candidate_id, payload
        )

        assert result.skills.created == 1
        assert result.skills.skipped == 1


def test_unknown_candidate(engine):
    with Session(engine) as db:
        with pytest.raises(CandidateNotFoundError):
            import_reviewed_resume(
                db,
                uuid.uuid4(),
                sample_payload(),
            )


def test_import_api(engine, candidate_id):
    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/candidates/{candidate_id}/resume/import",
                json=sample_payload().model_dump(mode="json"),
            )

        assert response.status_code == 200
        assert response.json()["skills"]["created"] == 1
    finally:
        app.dependency_overrides.clear()


def test_unapproved_api_request(engine, candidate_id):
    def override_get_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/candidates/{candidate_id}/resume/import",
                json={
                    "approved": False,
                    "skills": [
                        {
                            "name": "Python",
                            "proficiency_level": "advanced",
                        }
                    ],
                },
            )

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
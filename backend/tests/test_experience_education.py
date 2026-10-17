import pytest
from app.schemas.education import EducationCreate
from app.schemas.experience import ExperienceCreate
from pydantic import ValidationError


def test_experience_rejects_end_date_before_start_date() -> None:
    with pytest.raises(ValidationError):
        ExperienceCreate(
            company_name="Example Ltd",
            job_title="Developer",
            start_date="2025-06-01",
            end_date="2025-01-01",
            is_current=False,
        )


def test_current_experience_cannot_have_end_date() -> None:
    with pytest.raises(ValidationError):
        ExperienceCreate(
            company_name="Example Ltd",
            job_title="Developer",
            start_date="2025-01-01",
            end_date="2025-06-01",
            is_current=True,
        )


def test_education_rejects_invalid_date_range() -> None:
    with pytest.raises(ValidationError):
        EducationCreate(
            institution="Example University",
            degree="BS",
            field_of_study="Computer Science",
            start_date="2025-09-01",
            end_date="2025-01-01",
        )
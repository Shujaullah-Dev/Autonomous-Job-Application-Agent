
import pytest
from app.schemas.resume_import import ResumeImportRequest
from pydantic import ValidationError


def test_plain_string_skills_are_accepted():
    payload = ResumeImportRequest.model_validate(
        {
            "approved": True,
            "skills": [
                "Python",
                "FastAPI",
                "PostgreSQL",
            ],
        }
    )

    assert len(payload.skills) == 3
    assert payload.skills[0].name == "Python"
    assert payload.skills[0].proficiency_level == "unassessed"


def test_existing_object_format_still_works():
    payload = ResumeImportRequest.model_validate(
        {
            "approved": True,
            "skills": [
                {
                    "name": "Python",
                    "proficiency_level": "advanced",
                }
            ],
        }
    )

    assert payload.skills[0].proficiency_level == "advanced"


def test_import_requires_approval():
    with pytest.raises(ValidationError):
        ResumeImportRequest.model_validate(
            {
                "approved": False,
                "skills": ["Python"],
            }
        )


def test_blank_skill_is_rejected():
    with pytest.raises(ValidationError):
        ResumeImportRequest.model_validate(
            {
                "approved": True,
                "skills": ["   "],
            }
        )
def test_rust_detected_from_job_title():
    from app.services.resume_skills import extract_skills

    result = extract_skills(
        "Rust Developer building high-performance services"
    )

    assert "Rust" in result
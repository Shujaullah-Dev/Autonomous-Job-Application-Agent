
import pytest
from app.schemas.resume_import import ResumeImportRequest
from pydantic import ValidationError


def test_valid_approved_import():
    request = ResumeImportRequest.model_validate({
        "approved": True,
        "skills": [
            {
                "name": "Python",
                "proficiency_level": "advanced",
            }
        ],
    })

    assert request.approved is True
    assert len(request.skills) == 1


def test_approval_is_required():
    with pytest.raises(ValidationError):
        ResumeImportRequest.model_validate({
            "skills": [
                {
                    "name": "Python",
                    "proficiency_level": "advanced",
                }
            ]
        })


def test_false_approval_rejected():
    with pytest.raises(ValidationError):
        ResumeImportRequest.model_validate({
            "approved": False,
            "skills": [
                {
                    "name": "Python",
                    "proficiency_level": "advanced",
                }
            ],
        })


def test_empty_import_rejected():
    with pytest.raises(ValidationError):
        ResumeImportRequest.model_validate({
            "approved": True,
        })


def test_missing_proficiency_rejected():
    with pytest.raises(ValidationError):
        ResumeImportRequest.model_validate({
            "approved": True,
            "skills": [{"name": "Python"}],
        })


def test_invalid_experience_date_rejected():
    with pytest.raises(ValidationError):
        ResumeImportRequest.model_validate({
            "approved": True,
            "experiences": [
                {
                    "company_name": "Example Technologies",
                    "job_title": "Developer",
                    "start_date": "2024-01-01",
                    "end_date": "2023-01-01",
                }
            ],
        })


def test_unknown_top_level_field_rejected():
    with pytest.raises(ValidationError):
        ResumeImportRequest.model_validate({
            "approved": True,
            "skills": [
                {
                    "name": "Python",
                    "proficiency_level": "beginner",
                }
            ],
            "delete_existing": True,
        })


import pytest
from pydantic import ValidationError

from app.schemas.job import JobCreate


def valid_job():
    return {
        "title": "Python Developer",
        "company_name": "Example Technologies",
        "description": "Build Python APIs",
        "job_url": "https://example.com/jobs/100",
        "salary_min": 50000,
        "salary_max": 90000,
        "salary_currency": "pkr",
        "work_mode": "remote",
    }


def test_valid_job_schema():
    job = JobCreate(**valid_job())

    assert job.title == "Python Developer"
    assert job.salary_currency == "PKR"
    assert job.work_mode == "remote"


def test_negative_salary_rejected():
    data = valid_job()
    data["salary_min"] = -100

    with pytest.raises(ValidationError):
        JobCreate(**data)


def test_invalid_salary_range_rejected():
    data = valid_job()
    data["salary_max"] = 1000

    with pytest.raises(ValidationError):
        JobCreate(**data)


def test_invalid_url_rejected():
    data = valid_job()
    data["job_url"] = "not-a-valid-url"

    with pytest.raises(ValidationError):
        JobCreate(**data)


def test_invalid_work_mode_rejected():
    data = valid_job()
    data["work_mode"] = "unknown"

    with pytest.raises(ValidationError):
        JobCreate(**data)


def test_salary_requires_currency():
    data = valid_job()
    data["salary_currency"] = None

    with pytest.raises(ValidationError):
        JobCreate(**data)


def test_blank_title_rejected():
    data = valid_job()
    data["title"] = "   "

    with pytest.raises(ValidationError):
        JobCreate(**data)

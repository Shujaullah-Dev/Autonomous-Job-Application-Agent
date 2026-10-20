
from datetime import date

from app.services.import_normalization import (
    education_key,
    experience_key,
    normalize_text,
    skill_key,
)


def test_normalize_text():
    assert normalize_text("  PYTHON  ") == "python"
    assert normalize_text("Senior   Developer") == (
        "senior developer"
    )


def test_skill_key():
    assert skill_key("Python") == skill_key(
        "  python "
    )


def test_experience_duplicate_key():
    first = experience_key(
        "Example Technologies",
        "Backend Developer",
        date(2023, 1, 1),
        None,
    )

    second = experience_key(
        " example technologies ",
        "BACKEND DEVELOPER",
        date(2023, 1, 1),
        None,
    )

    assert first == second


def test_education_duplicate_key():
    first = education_key(
        "Example University",
        "BS Computer Science",
        date(2019, 9, 1),
        date(2023, 6, 1),
    )

    second = education_key(
        "example university",
        "bs computer science",
        date(2019, 9, 1),
        date(2023, 6, 1),
    )

    assert first == second

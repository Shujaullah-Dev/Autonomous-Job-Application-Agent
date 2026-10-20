
from app.services.resume_skills import extract_skills


def test_extract_skills():
    text = "Skills: Python, FastAPI, Docker, PostgreSQL"

    result = extract_skills(text)

    assert "Python" in result
    assert "FastAPI" in result
    assert "Docker" in result
    assert "PostgreSQL" in result


def test_duplicate_skill_aliases():
    result = extract_skills(
        "Postgres and PostgreSQL"
    )

    assert result.count("PostgreSQL") == 1


def test_case_insensitive():
    result = extract_skills(
        "PYTHON and fastapi"
    )

    assert "Python" in result
    assert "FastAPI" in result


def test_avoid_partial_word_matches():
    result = extract_skills(
        "I build digital products"
    )

    assert "Git" not in result

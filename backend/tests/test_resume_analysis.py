
import uuid

from app.services.resume_analysis import analyze_resume_text


def test_complete_resume_analysis():
    candidate_id = uuid.uuid4()

    text = """
    Alex Morgan
    Email: alex@example.com
    Phone: +92 300 1234567

    SKILLS
    Python, FastAPI, PostgreSQL

    EXPERIENCE
    Job Title: Backend Developer
    Company: Example Technologies
    Start: 2023-01
    End: Present

    EDUCATION
    Institution: Example University
    Degree: BS Computer Science
    Start: 2019-09
    End: 2023-06
    """

    result = analyze_resume_text(
        candidate_id=candidate_id,
        text=text,
    )

    assert result.candidate_id == candidate_id
    assert result.contact.email == "alex@example.com"
    assert "Python" in result.skills
    assert "FastAPI" in result.skills

    assert len(result.experiences) == 1
    assert len(result.educations) == 1


def test_incomplete_resume():
    candidate_id = uuid.uuid4()

    result = analyze_resume_text(
        candidate_id=candidate_id,
        text="Alex Morgan",
    )

    assert result.skills == []
    assert result.experiences == []
    assert result.educations == []
    assert len(result.warnings) >= 3
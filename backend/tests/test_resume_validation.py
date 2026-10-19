import pytest
from app.services.resume_validation import (
    MAX_RESUME_SIZE,
    ResumeValidationError,
    validate_resume,
)


def test_valid_pdf():
    result = validate_resume(
        "resume.pdf",
        "application/pdf",
        b"%PDF-1.4\nsample",
    )
    assert result == "pdf"


def test_valid_docx_signature():
    result = validate_resume(
        "resume.docx",
        (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        b"PK\x03\x04sample",
    )
    assert result == "docx"


def test_invalid_extension():
    with pytest.raises(ResumeValidationError):
        validate_resume(
            "resume.exe",
            "application/octet-stream",
            b"example",
        )


def test_empty_file():
    with pytest.raises(
        ResumeValidationError,
        match="cannot be empty",
    ):
        validate_resume(
            "resume.pdf",
            "application/pdf",
            b"",
        )


def test_oversized_file():
    with pytest.raises(ResumeValidationError) as exc:
        validate_resume(
            "resume.pdf",
            "application/pdf",
            b"%PDF-" + b"a" * MAX_RESUME_SIZE,
        )

    assert exc.value.status_code == 413


def test_mismatched_content_type():
    with pytest.raises(ResumeValidationError):
        validate_resume(
            "resume.pdf",
            "text/plain",
            b"%PDF-1.4",
        )

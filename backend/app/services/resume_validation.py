
from pathlib import Path

MAX_RESUME_SIZE = 5 * 1024 * 1024  # 5 MiB

ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
}


class ResumeValidationError(ValueError):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def validate_resume(
    filename: str | None,
    content_type: str | None,
    file_content: bytes,
) -> str:
    if not filename:
        raise ResumeValidationError("Filename is required")

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_TYPES:
        raise ResumeValidationError(
            "Only PDF and DOCX resumes are supported"
        )

    if content_type != ALLOWED_TYPES[extension]:
        raise ResumeValidationError(
            "File content type does not match its extension"
        )

    if not file_content:
        raise ResumeValidationError("Resume cannot be empty")

    if len(file_content) > MAX_RESUME_SIZE:
        raise ResumeValidationError(
            "Resume must be 5 MiB or smaller",
            status_code=413,
        )

    if extension == ".pdf" and not file_content.startswith(b"%PDF-"):
        raise ResumeValidationError("Invalid PDF signature")

    if extension == ".docx" and not file_content.startswith(b"PK"):
        raise ResumeValidationError("Invalid DOCX signature")

    return extension.removeprefix(".")

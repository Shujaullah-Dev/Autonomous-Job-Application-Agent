
import re

from app.schemas.resume_analysis import ResumeContact

EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])"
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"
    r"(?![\w.-])"
)

PHONE_PATTERN = re.compile(
    r"(?<!\w)"
    r"(?:\+?\d[\d\s().-]{7,}\d)"
    r"(?!\w)"
)


def extract_contact(text: str) -> ResumeContact:
    email_match = EMAIL_PATTERN.search(text)

    email = (
        email_match.group(0)
        if email_match
        else None
    )

    phone = None

    # Prefer explicitly labeled phone fields.
    for line in text.splitlines():
        if not re.match(
            r"^\s*(phone|mobile|contact)\s*:",
            line,
            flags=re.IGNORECASE,
        ):
            continue

        match = PHONE_PATTERN.search(line)

        if match:
            phone = match.group(0).strip()
            break

    return ResumeContact(
        email=email,
        phone=phone,
    )

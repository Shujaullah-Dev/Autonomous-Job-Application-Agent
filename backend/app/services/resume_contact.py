import re

from app.schemas.resume_analysis import ResumeContact

EMAIL_PATTERN = re.compile(r'(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])')
PHONE_PATTERN = re.compile(
    r'(?<![\w\d])(?:\+92|0092|0)[\s().-]*'
    r'3\d{2}[\s().-]*\d{7}(?!\d)'
)
LABELED_PHONE = re.compile(r'^\s*(?:phone|mobile|contact|tel)\s*:', re.I)


def extract_contact(text: str) -> ResumeContact:
    email_match = EMAIL_PATTERN.search(text)
    phone = None
    lines = text.splitlines()
    for line in lines:
        if LABELED_PHONE.match(line):
            match = PHONE_PATTERN.search(line)
            if match:
                phone = match.group(0).strip()
                break
    if phone is None:
        # Restrict unlabeled extraction to the resume header, avoiding project metrics.
        for line in lines[:12]:
            match = PHONE_PATTERN.search(line)
            if match:
                phone = match.group(0).strip()
                break
    return ResumeContact(
        email=email_match.group(0) if email_match else None,
        phone=phone,
    )

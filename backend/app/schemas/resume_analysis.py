
import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ResumeContact(BaseModel):
    email: str | None = None
    phone: str | None = None


class ResumeExperience(BaseModel):
    company_name: str | None = None
    job_title: str | None = None
    start_date: date | None = None
    end_date: date | None = None

    # Original date text is preserved when the
    # document does not provide an exact month.
    start_date_text: str | None = None
    end_date_text: str | None = None


class ResumeEducation(BaseModel):
    institution: str | None = None
    degree: str | None = None
    start_date: date | None = None
    end_date: date | None = None

    start_date_text: str | None = None
    end_date_text: str | None = None


class ResumeAnalysisResponse(BaseModel):
    candidate_id: uuid.UUID

    contact: ResumeContact

    skills: list[str] = Field(default_factory=list)

    experiences: list[ResumeExperience] = Field(
        default_factory=list
    )

    educations: list[ResumeEducation] = Field(
        default_factory=list
    )

    # Allows frontend and developers to distinguish
    # AI extraction from local fallback.
    parser_used: Literal["groq", "local"] = "local"

    # True whenever Groq was requested but unavailable.
    fallback_used: bool = False

    warnings: list[str] = Field(default_factory=list)

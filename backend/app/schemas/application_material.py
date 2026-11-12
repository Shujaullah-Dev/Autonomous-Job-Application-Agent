
"""Day 16: Application material request and response schemas."""

import uuid
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class ApplicationDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    use_ai: bool = False


class TailoredResumePreview(BaseModel):
    candidate_name: str
    candidate_email: str

    relevant_skills: list[str]
    experiences: list[str]
    educations: list[str]


class ApplicationDraftResponse(BaseModel):
    candidate_id: uuid.UUID
    workflow_id: uuid.UUID

    job_id: int = Field(ge=1)
    job_title: str
    company_name: str
    job_url: str

    status: Literal["draft"] = "draft"

    generation_mode: Literal[
        "deterministic",
        "langchain_groq",
        "fallback",
    ]

    llm_used: bool
    model_name: str | None

    cover_letter: str
    tailored_resume: TailoredResumePreview

    evidence_used: list[str]
    warnings: list[str]

    message: str
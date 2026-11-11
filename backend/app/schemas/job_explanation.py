
"""Public response schema for grounded job explanations."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class JobExplanationResponse(BaseModel):
    candidate_id: uuid.UUID
    job_id: int = Field(ge=1)
    job_title: str

    score: float = Field(ge=0, le=100)
    scoring_mode: Literal["rules"] = "rules"

    explanation_mode: Literal[
        "deterministic",
        "langchain_groq",
        "fallback",
    ]

    llm_used: bool
    model_name: str | None

    summary: str
    reasons: list[str]
    cautions: list[str]
    warnings: list[str]
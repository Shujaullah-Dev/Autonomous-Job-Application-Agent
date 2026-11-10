
"""Candidate recommendation API schemas."""

from datetime import datetime
from typing import Literal

from app.schemas.job import WorkMode
from pydantic import BaseModel, Field


class RecommendationItem(BaseModel):
    job_id: int
    title: str
    company_name: str
    job_url: str
    location: str | None
    source: str | None
    work_mode: WorkMode | None
    posted_at: datetime | None

    score: float = Field(ge=0, le=100)
    rule_score: float = Field(ge=0, le=100)
    semantic_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )

    breakdown: dict[str, float]
    matched_skills: list[str]
    missing_skills: list[str]

    reasons: list[str]
    cautions: list[str]


class RecommendationResponse(BaseModel):
    candidate_id: str

    requested_mode: Literal["rules", "hybrid"]
    ranking_mode: Literal["rules", "hybrid", "mixed"]
    model_name: str | None

    evaluated_jobs: int = Field(ge=0)
    filtered_jobs: int = Field(ge=0)
    unknown_work_mode_jobs: int = Field(ge=0)
    filtered_out_jobs: int = Field(ge=0)
    semantic_jobs: int = Field(ge=0)

    total_matches: int = Field(ge=0)
    returned_jobs: int = Field(ge=0)

    below_threshold: int = Field(ge=0)
    insufficient_evidence: int = Field(ge=0)

    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    has_more: bool

    warnings: list[str]
    items: list[RecommendationItem]
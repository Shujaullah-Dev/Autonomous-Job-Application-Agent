
"""Response models for Day 11 job matching."""

from pydantic import BaseModel, Field


class JobMatchItem(BaseModel):
    job_id: int
    title: str
    company_name: str
    location: str | None
    job_url: str

    score: float = Field(ge=0, le=100)
    breakdown: dict[str, float]

    matched_skills: list[str]
    missing_skills: list[str]
    warnings: list[str]


class JobMatchResponse(BaseModel):
    candidate_id: str
    evaluated_jobs: int
    returned_jobs: int
    items: list[JobMatchItem]

class HybridMatchItem(JobMatchItem):
    rule_score: float = Field(ge=0, le=100)
    semantic_score: float | None = Field(
        default=None,
        ge=0,
        le=100,
    )
    hybrid_score: float = Field(ge=0, le=100)


class HybridMatchResponse(BaseModel):
    candidate_id: str
    model_name: str
    evaluated_jobs: int
    embedded_jobs: int
    returned_jobs: int
    items: list[HybridMatchItem]

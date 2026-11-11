
"""Workflow API validation and response models."""

import uuid
from typing import Literal

from app.schemas.job import WorkMode
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    model_validator,
)


class WorkflowStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_mode: WorkMode | None = None
    include_unknown_work_mode: bool = False
    preferred_work_mode: WorkMode | None = None

    preferred_location: str | None = Field(
        default=None,
        max_length=150,
    )

    min_score: float = Field(
        default=50.0,
        ge=0,
        le=100,
    )

    limit: int = Field(
        default=5,
        ge=1,
        le=10,
    )

    @model_validator(mode="after")
    def validate_work_mode(self):
        if (
            self.include_unknown_work_mode
            and self.work_mode is None
        ):
            raise ValueError(
                "include_unknown_work_mode requires work_mode"
            )

        return self


class WorkflowReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]

    approved_job_ids: list[StrictInt] = Field(
        default_factory=list,
        max_length=10,
    )

    @model_validator(mode="after")
    def validate_decision(self):
        ids = self.approved_job_ids

        if any(job_id <= 0 for job_id in ids):
            raise ValueError("Job IDs must be positive")

        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate job IDs")

        if self.decision == "approve" and not ids:
            raise ValueError(
                "Approval requires at least one job ID"
            )

        if self.decision == "reject" and ids:
            raise ValueError(
                "Rejection cannot approve any jobs"
            )

        return self


class WorkflowJob(BaseModel):
    job_id: int
    title: str
    score: float = Field(ge=0, le=100)
    work_mode: WorkMode | None = None
    summary: str
    reasons: list[str]
    cautions: list[str]


class WorkflowResponse(BaseModel):
    candidate_id: uuid.UUID
    workflow_id: uuid.UUID

    status: Literal[
        "pending_review",
        "approved",
        "rejected",
        "no_matches",
    ]

    awaiting_review: bool
    shortlist: list[WorkflowJob]
    approved_job_ids: list[int]

    message: str

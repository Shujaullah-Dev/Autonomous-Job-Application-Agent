
"""Request and response schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

ApplicationStatus = Literal[
    "draft",
    "ready",
    "submitted",
    "interview",
    "offered",
    "rejected",
    "withdrawn",
]


class DraftEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)

    cover_letter: str = Field(
        min_length=20,
        max_length=15000,
    )


class StatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_status: Literal[
        "ready",
        "submitted",
        "interview",
        "offered",
        "rejected",
        "withdrawn",
    ]

    confirm_reviewed: bool = False
    confirm_external_submission: bool = False

    note: str | None = Field(
        default=None,
        max_length=300,
    )


class DraftRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    revision_number: int
    cover_letter: str
    resume_snapshot: dict[str, Any]
    source: str
    created_at: datetime


class StatusEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    previous_status: str | None
    new_status: ApplicationStatus
    actor: str
    note: str | None
    created_at: datetime


class ApplicationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_id: uuid.UUID
    job_id: int
    workflow_id: uuid.UUID

    job_title: str
    company_name: str
    job_url: str

    status: ApplicationStatus
    current_revision: int

    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApplicationDetailResponse(ApplicationSummary):
    latest_draft: DraftRevisionRead
    revisions: list[DraftRevisionRead]
    history: list[StatusEventRead]
    message: str


class ApplicationListResponse(BaseModel):
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)

    items: list[ApplicationSummary]

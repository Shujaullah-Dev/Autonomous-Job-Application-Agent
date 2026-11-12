
"""Request and response models."""

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

UTC = timezone.utc  # noqa: UP017

FollowUpKind = Literal["status_check", "follow_up"]
FollowUpState = Literal[
    "pending",
    "completed",
    "dismissed",
]


class FollowUpCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: FollowUpKind
    due_at: datetime

    note: str | None = Field(
        default=None,
        max_length=500,
    )

    @field_validator("due_at")
    @classmethod
    def validate_due_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "due_at must include a timezone offset"
            )

        return value.astimezone(UTC)


class FollowUpResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["complete", "dismiss"]

    resolution_note: str | None = Field(
        default=None,
        max_length=500,
    )


class FollowUpRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID

    kind: FollowUpKind
    due_at: datetime
    state: FollowUpState

    note: str | None
    resolution_note: str | None
    resolved_at: datetime | None

    created_at: datetime
    updated_at: datetime


class FollowUpEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: Literal[
        "created",
        "completed",
        "dismissed",
        "auto_closed",
    ]
    actor: str
    note: str | None
    created_at: datetime


class FollowUpDetailResponse(FollowUpRead):
    history: list[FollowUpEventRead]


class FollowUpListItem(FollowUpRead):
    job_title: str


class FollowUpListResponse(BaseModel):
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)

    items: list[FollowUpListItem]


class ApplicationMonitoringResponse(BaseModel):
    candidate_id: uuid.UUID
    total_applications: int = Field(ge=0)

    applications_by_status: dict[str, int]

    pending_follow_ups: int = Field(ge=0)
    overdue_follow_ups: int = Field(ge=0)
    due_next_7_days: int = Field(ge=0)

    checked_at: datetime
    message: str

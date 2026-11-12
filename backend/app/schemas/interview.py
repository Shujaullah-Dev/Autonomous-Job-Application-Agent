"""Interview and notification request/response schemas."""

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

UTC = timezone.utc  # noqa: UP017

InterviewMode = Literal["video", "phone", "onsite"]
InterviewStatus = Literal["scheduled", "completed", "cancelled"]
ReminderOffset = Literal[0, 60, 1440]


def normalize_input_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("A timezone offset is required")
    return value.astimezone(UTC)


def normalize_output_datetime(
    value: datetime | None,
) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class InterviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=150)
    starts_at: datetime
    ends_at: datetime
    mode: InterviewMode

    location_or_link: str | None = Field(
        default=None, max_length=500
    )
    notes: str | None = Field(
        default=None, max_length=1000
    )

    reminder_minutes: list[ReminderOffset] = Field(
        default_factory=lambda: [1440, 60],
        max_length=3,
    )

    @field_validator("starts_at", "ends_at")
    @classmethod
    def validate_timezone(cls, value: datetime) -> datetime:
        return normalize_input_datetime(value)

    @model_validator(mode="after")
    def validate_request(self):
        if not self.title.strip():
            raise ValueError("Title cannot be empty")
        if self.ends_at <= self.starts_at:
            raise ValueError("End time must follow start time")
        if len(self.reminder_minutes) != len(set(self.reminder_minutes)):
            raise ValueError("Duplicate reminder offsets")
        return self


class InterviewReschedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    starts_at: datetime
    ends_at: datetime
    reminder_minutes: list[ReminderOffset] = Field(
        max_length=3
    )

    @field_validator("starts_at", "ends_at")
    @classmethod
    def validate_timezone(cls, value: datetime) -> datetime:
        return normalize_input_datetime(value)

    @model_validator(mode="after")
    def validate_request(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("Invalid interview interval")
        if len(self.reminder_minutes) != len(set(self.reminder_minutes)):
            raise ValueError("Duplicate reminder offsets")
        return self


class InterviewAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["cancel", "complete"]
    expected_version: int = Field(ge=1)


class InterviewReminderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    interview_id: uuid.UUID
    minutes_before: int
    due_at: datetime
    state: Literal["scheduled", "available", "read", "cancelled"]
    available_at: datetime | None
    read_at: datetime | None

    @field_validator("due_at", "available_at", "read_at")
    @classmethod
    def display_utc(cls, value):
        return normalize_output_datetime(value)


class InterviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    title: str
    starts_at: datetime
    ends_at: datetime
    mode: InterviewMode
    location_or_link: str | None
    notes: str | None
    status: InterviewStatus
    version: int
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "starts_at", "ends_at", "created_at", "updated_at"
    )
    @classmethod
    def display_utc(cls, value):
        return normalize_output_datetime(value)


class InterviewDetail(InterviewRead):
    reminders: list[InterviewReminderRead]


class InterviewList(BaseModel):
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    items: list[InterviewRead]


class NotificationItem(InterviewReminderRead):
    interview_title: str
    job_title: str
    interview_starts_at: datetime

    @field_validator("interview_starts_at")
    @classmethod
    def display_start_utc(cls, value):
        return normalize_output_datetime(value)


class NotificationList(BaseModel):
    total: int = Field(ge=0)
    items: list[NotificationItem]


class NotificationRefreshResult(BaseModel):
    released: int = Field(ge=0)
    checked_at: datetime
    message: str
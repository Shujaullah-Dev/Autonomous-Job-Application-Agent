
"""Manual handoff API schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class PreflightCheckRead(BaseModel):
    code: str
    passed: bool
    detail: str


class SubmissionPreflightResponse(BaseModel):
    candidate_id: uuid.UUID
    application_id: uuid.UUID
    application_status: str
    revision_number: int = Field(ge=1)

    provider_hint: str
    can_handoff: bool
    destination_url: str | None

    checks: list[PreflightCheckRead]
    warnings: list[str]


class ManualHandoffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    confirm_reviewed: bool
    confirm_manual_handoff: bool

    @model_validator(mode="after")
    def require_explicit_confirmation(self):
        if not self.confirm_reviewed:
            raise ValueError(
                "The application materials must be reviewed"
            )

        if not self.confirm_manual_handoff:
            raise ValueError(
                "Explicit manual handoff confirmation "
                "is required"
            )

        return self


class ManualHandoffResponse(BaseModel):
    handoff_id: uuid.UUID
    application_id: uuid.UUID
    revision_number: int = Field(ge=1)

    status: Literal["prepared"]
    provider_hint: str
    destination_url: str
    created_at: datetime

    newly_created: bool
    message: str
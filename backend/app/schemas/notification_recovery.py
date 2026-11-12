
"""Recovery API request and response models."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RecoveryApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: Literal[True]
    limit: int = Field(default=100, ge=1, le=200)


class RecoveryResponse(BaseModel):
    candidate_id: uuid.UUID
    scanned: int = Field(ge=0)
    released: int = Field(ge=0)
    cancelled: int = Field(ge=0)
    dry_run: bool
    limit: int
    checked_at: datetime
    run_id: uuid.UUID | None
    message: str


class RecoveryRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_id: uuid.UUID
    scanned: int
    released: int
    cancelled: int
    created_at: datetime


class RecoveryRunList(BaseModel):
    total: int = Field(ge=0)
    items: list[RecoveryRunRead]


class ReadinessResponse(BaseModel):
    status: Literal["ready"]
    database: Literal["connected"]
    checked_at: datetime

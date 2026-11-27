from datetime import datetime

from pydantic import BaseModel, Field


class JobRefreshFailure(BaseModel):
    source: str
    reason: str


class JobRefreshStatus(BaseModel):
    running: bool
    trigger: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    created: int = Field(default=0, ge=0)
    updated: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    deactivated: int = Field(default=0, ge=0)
    possible_duplicates: int = Field(default=0, ge=0)

    sources_total: int = Field(default=0, ge=0)
    sources_ok: int = Field(default=0, ge=0)
    failures: list[JobRefreshFailure] = Field(default_factory=list)

    enabled: bool = True
    interval_hours: float = 6.0
    message: str | None = None


class JobRefreshStartResponse(BaseModel):
    started: bool
    reason: str
    status: JobRefreshStatus

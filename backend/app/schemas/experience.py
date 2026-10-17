import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExperienceFields(BaseModel):
    company_name: str = Field(min_length=1, max_length=150)
    job_title: str = Field(min_length=1, max_length=150)
    location: str | None = Field(default=None, max_length=150)
    start_date: date
    end_date: date | None = None
    is_current: bool = False
    description: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")
        if self.is_current and self.end_date is not None:
            raise ValueError("Current employment cannot have an end date")
        if self.company_name != self.company_name.strip():
            self.company_name = self.company_name.strip()
        if self.job_title != self.job_title.strip():
            self.job_title = self.job_title.strip()
        if not self.company_name or not self.job_title:
            raise ValueError("Company and job title cannot be blank")
        return self


class ExperienceCreate(ExperienceFields):
    pass


class ExperienceUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=150)
    job_title: str | None = Field(default=None, min_length=1, max_length=150)
    location: str | None = Field(default=None, max_length=150)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None
    description: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("End date cannot be before start date")
        if self.is_current is True and self.end_date is not None:
            raise ValueError("Current employment cannot have an end date")
        return self


class ExperienceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_id: uuid.UUID
    company_name: str
    job_title: str
    location: str | None
    start_date: date
    end_date: date | None
    is_current: bool
    description: str | None
    created_at: datetime
    updated_at: datetime
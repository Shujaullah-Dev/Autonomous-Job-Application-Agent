import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EducationFields(BaseModel):
    institution: str = Field(min_length=1, max_length=200)
    degree: str = Field(min_length=1, max_length=150)
    field_of_study: str | None = Field(default=None, max_length=150)
    start_date: date
    end_date: date | None = None
    description: str | None = None

    @model_validator(mode="after")
    def validate_fields(self):
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("End date cannot be before start date")

        self.institution = self.institution.strip()
        self.degree = self.degree.strip()

        if not self.institution or not self.degree:
            raise ValueError("Institution and degree cannot be blank")

        return self


class EducationCreate(EducationFields):
    pass


class EducationUpdate(BaseModel):
    institution: str | None = Field(default=None, min_length=1, max_length=200)
    degree: str | None = Field(default=None, min_length=1, max_length=150)
    field_of_study: str | None = Field(default=None, max_length=150)
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("End date cannot be before start date")
        return self


class EducationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_id: uuid.UUID
    institution: str
    degree: str
    field_of_study: str | None
    start_date: date
    end_date: date | None
    description: str | None
    created_at: datetime
    updated_at: datetime
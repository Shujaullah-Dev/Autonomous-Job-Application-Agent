
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

WorkMode = Literal["remote", "hybrid", "onsite"]


class JobCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=255)
    company_name: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)

    description: str = Field(min_length=1, max_length=40000)
    job_url: HttpUrl

    source: str | None = Field(default="manual", max_length=100)
    employment_type: str | None = Field(
        default=None, max_length=50
    )
    work_mode: WorkMode | None = None

    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)

    salary_currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    )

    posted_at: datetime | None = None

    @field_validator("salary_currency")
    @classmethod
    def uppercase_currency(
        cls, value: str | None
    ) -> str | None:
        return value.upper() if value else value

    @model_validator(mode="after")
    def validate_salary(self):
        if (
            self.salary_min is not None
            or self.salary_max is not None
        ) and not self.salary_currency:
            raise ValueError(
                "salary_currency is required when salary is provided"
            )

        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_max < self.salary_min
        ):
            raise ValueError(
                "salary_max must be greater than or equal to salary_min"
            )

        return self


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    company_name: str
    location: str | None
    description: str
    job_url: str

    source: str | None
    employment_type: str | None
    work_mode: WorkMode | None

    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None

    posted_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    items: list[JobRead]

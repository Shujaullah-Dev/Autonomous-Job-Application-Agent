
from typing import Literal

from app.schemas.education import EducationCreate
from app.schemas.experience import ExperienceCreate
from app.schemas.skill import SkillCreate
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class ResumeImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: Literal[True]

    skills: list[SkillCreate] = Field(
        default_factory=list,
        max_length=100,
    )

    experiences: list[ExperienceCreate] = Field(
        default_factory=list,
        max_length=100,
    )

    educations: list[EducationCreate] = Field(
        default_factory=list,
        max_length=100,
    )

    @model_validator(mode="after")
    def require_records(self):
        if not (
            self.skills
            or self.experiences
            or self.educations
        ):
            raise ValueError(
                "Select at least one record to import"
            )
        return self


class ImportCounts(BaseModel):
    created: int = 0
    skipped: int = 0


class ResumeImportResponse(BaseModel):
    status: str
    candidate_id: str
    skills: ImportCounts
    experiences: ImportCounts
    educations: ImportCounts
    message: str

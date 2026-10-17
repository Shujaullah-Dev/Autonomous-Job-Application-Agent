import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ProficiencyLevel = Literal[
    "beginner",
    "intermediate",
    "advanced",
    "expert",
]


class SkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    proficiency_level: ProficiencyLevel

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Skill name cannot be blank")
        return value


class SkillUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    proficiency_level: ProficiencyLevel | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Skill name cannot be blank")
        return value


class SkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_id: uuid.UUID
    name: str
    proficiency_level: ProficiencyLevel
    created_at: datetime
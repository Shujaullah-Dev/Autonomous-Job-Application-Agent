import pytest
from app.schemas.skill import SkillCreate
from pydantic import ValidationError


def test_skill_create_accepts_valid_data() -> None:
    skill = SkillCreate(
        name="  Python  ",
        proficiency_level="advanced",
    )

    assert skill.name == "Python"
    assert skill.proficiency_level == "advanced"


def test_skill_create_rejects_invalid_proficiency() -> None:
    with pytest.raises(ValidationError):
        SkillCreate(
            name="Python",
            proficiency_level="master",
        )


def test_skill_create_rejects_blank_name() -> None:
    with pytest.raises(ValidationError):
        SkillCreate(
            name="   ",
            proficiency_level="beginner",
        )
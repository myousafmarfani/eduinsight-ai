"""Student profile schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class StudentProfile(BaseModel):
    """Student information collected by the form (also the creation request body)."""

    name: str = Field(min_length=1, max_length=100)
    board: str = Field(min_length=1, max_length=60, description="Education board key or name, e.g. AKU-EB")
    country: str = Field(min_length=1, max_length=60)
    grade: str = Field(min_length=1, max_length=40, description="Class / grade, e.g. 'HSSC 1' or 'Grade 10'")
    academic_year: str = Field(min_length=1, max_length=20)
    school_name: str | None = Field(default=None, max_length=120)
    goals: str | None = Field(default=None, max_length=1000)
    target_percentage: float | None = Field(default=None, ge=0, le=100)
    difficult_subjects: list[str] = Field(default_factory=list)
    difficult_topics: dict[str, list[str]] = Field(
        default_factory=dict, description="Optional: subject -> topics the student finds hard")
    preferred_resources: list[str] = Field(default_factory=list)
    preferred_language: str | None = Field(default=None, max_length=40)

    @field_validator("name", "board", "country", "grade", "academic_year")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("difficult_subjects", "preferred_resources")
    @classmethod
    def _clean_list(cls, values: list[str]) -> list[str]:
        return [v.strip() for v in values if v and v.strip()]


class StudentRead(StudentProfile):
    """Stored student record."""

    student_id: str
    created_at: datetime
    has_results: bool = False

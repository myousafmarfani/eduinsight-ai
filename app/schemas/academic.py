"""Academic result schemas (examinations, subject results, extraction preview)."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class SubjectResult(BaseModel):
    """One subject's marks. Numeric fields are validated for sense by the data engine so that every
    problem is reported with its table row number."""

    subject: str | None = None
    obtained: float | None = None
    total: float | None = None
    grade: str | None = None


class ResultRow(SubjectResult):
    """One row of the marks table as the student sees it: a subject result tagged with its exam."""

    exam: str | None = None
    exam_type: str | None = None
    exam_date: date | None = None


class AcademicResult(BaseModel):
    """Request body for saving results. Rows are listed oldest examination first; the last
    examination is treated as the current one unless every exam has a date."""

    rows: list[ResultRow] = Field(min_length=1)
    default_total: float | None = Field(default=None, gt=0, description="Used only when a row has no total")
    replace_existing: bool = True


class Examination(BaseModel):
    """A stored examination with its subject results."""

    exam_name: str
    exam_type: str | None = None
    exam_date: date | None = None
    sequence: int = 0
    subjects: list[SubjectResult]


class ResultsRead(BaseModel):
    student_id: str
    examinations: list[Examination]


class DataIssueModel(BaseModel):
    row: int | None = None
    field: str
    message: str
    severity: str = "error"


class ExtractedRow(BaseModel):
    """A row read from an uploaded file. Values are *proposals* the student must confirm."""

    row: int
    exam: str = ""
    exam_type: str = ""
    subject: str = ""
    obtained: float | None = None
    total: float | None = None
    grade: str = ""
    confidence: str = "high"  # high | medium
    source_text: str | None = None


class ExtractedMarksheet(BaseModel):
    filename: str
    file_type: str
    rows: list[ExtractedRow]
    issues: list[DataIssueModel] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    ocr_used: bool = False
    requires_confirmation: bool = True

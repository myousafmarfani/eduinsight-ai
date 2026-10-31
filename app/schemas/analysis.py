"""Analysis, report, resource and visualization schemas."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ResourceType(str, Enum):
    VIDEO = "video"
    ARTICLE = "article"
    DOCUMENTATION = "documentation"
    PRACTICE = "practice"
    COURSE = "course"
    OTHER = "other"


class InsightCategory(str, Enum):
    STRENGTH = "strength"
    IMPROVEMENT_AREA = "improvement_area"
    ATTENTION = "attention"
    PROGRESS = "progress"
    PRIORITY = "priority"


class ReasonDetail(BaseModel):
    criterion: str
    observed: float
    threshold: float
    explanation: str


class PerformanceMetrics(BaseModel):
    exam_name: str
    subject_count: int
    total_obtained: float
    total_possible: float
    overall_percentage: float
    overall_grade: str
    overall_grade_is_indicative: bool
    average_subject_percentage: float | None
    median_percentage: float | None
    std_dev: float | None
    highest_subject: str
    highest_percentage: float
    highest_subjects_tied: list[str] = Field(default_factory=list)
    lowest_subject: str
    lowest_percentage: float
    lowest_subjects_tied: list[str] = Field(default_factory=list)


class SubjectPerformance(BaseModel):
    subject: str
    obtained: float
    total: float
    percentage: float
    grade: str
    grade_is_indicative: bool


class WeakSubject(BaseModel):
    subject: str
    percentage: float
    obtained: float
    total: float
    priority: Priority
    score: int
    reasons: list[ReasonDetail]
    gap_to_target: float | None = None
    change_since_previous: float | None = None
    trend_slope: float | None = None
    student_reported_difficulty: bool = False


class StrongSubject(BaseModel):
    subject: str
    percentage: float
    obtained: float
    total: float
    reasons: list[ReasonDetail]


class AcademicInsight(BaseModel):
    category: InsightCategory
    title: str
    statement: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class ImprovementRecommendation(BaseModel):
    """Study advice for one subject. `evidence` comes from the student's marks; `actions` and `goal`
    are advice (flagged by `ai_generated` when written by the LLM, otherwise a standard template)."""

    subject: str
    priority: Priority
    evidence: str
    actions: list[str] = Field(min_length=1)
    goal: str
    ai_generated: bool = False


class EducationalResource(BaseModel):
    title: str
    url: str
    resource_type: ResourceType
    description: str
    subject: str
    why_recommended: str
    search_query: str | None = None


class AcademicReport(BaseModel):
    student_id: str
    generated_at: datetime
    ai_generated: bool
    ai_notes: list[str] = Field(default_factory=list)
    overview: PerformanceMetrics
    strengths: list[StrongSubject]
    weaknesses: list[WeakSubject]
    weak_topics: list[dict[str, Any]] = Field(default_factory=list)
    insights: list[AcademicInsight]
    comparison: dict[str, Any]
    recommendations: list[ImprovementRecommendation]
    resources: list[EducationalResource]
    resource_search_status: str
    narrative_markdown: str


class PerformanceResponse(BaseModel):
    student_id: str
    metrics: PerformanceMetrics
    subjects: list[SubjectPerformance]
    statistics: dict[str, Any]
    comparison: dict[str, Any]
    insights: list[AcademicInsight]
    summary: str


class WeaknessResponse(BaseModel):
    student_id: str
    weak_threshold_percent: float
    pass_mark_percent: float
    target_percentage: float | None
    threshold_explanation: str
    weak_subjects: list[WeakSubject]
    strong_subjects: list[StrongSubject]
    priorities: list[dict[str, Any]]
    weak_topics: list[dict[str, Any]] = Field(default_factory=list)


class ChartInfo(BaseModel):
    id: str
    title: str
    available: bool
    reason: str = ""
    url: str | None = None


class VisualizationResponse(BaseModel):
    student_id: str
    charts: list[ChartInfo]
    data: dict[str, Any]


class ImprovementTaskRead(BaseModel):
    id: str
    subject: str
    description: str
    priority: Priority
    completed: bool
    completed_at: datetime | None = None


class TaskUpdate(BaseModel):
    completed: bool

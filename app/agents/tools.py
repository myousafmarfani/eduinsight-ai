"""LangChain tool wrappers around `StudentAnalyzer`.

Each tool is a thin, schema-validated wrapper; all numbers come from the Pandas/NumPy engine.
Tools are built per student (`build_student_tools`), so one student's data can never leak into
another student's conversation.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.data_engine.analyzer import StudentAnalyzer, SubjectNotFoundError


class NoInput(BaseModel):
    """This tool takes no arguments."""


class ThresholdInput(BaseModel):
    threshold: float | None = Field(
        default=None, ge=0, le=100,
        description="Optional percentage below which a subject counts as weak. Omit to use the configured default.")


class SubjectInput(BaseModel):
    subject: str = Field(min_length=1, description="Subject name, e.g. 'Mathematics'")


class OptionalSubjectInput(BaseModel):
    subject: str | None = Field(default=None, description="Optional subject filter")


def _safe(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    """Return errors as data so the model can recover (e.g. from a misspelt subject)."""

    def wrapper(**kwargs: Any) -> dict[str, Any]:
        try:
            return fn(**kwargs)
        except SubjectNotFoundError as exc:
            return {"error": str(exc)}

    return wrapper


def tool_specs(a: StudentAnalyzer) -> list[tuple[str, str, type[BaseModel], Callable[..., dict[str, Any]]]]:
    """(name, description, input schema, function) for the 12 analysis tools."""
    return [
        ("get_student_profile", "Get the student's profile: board, grade, goals, target, self-reported difficult subjects.", NoInput, a.get_student_profile),
        ("get_student_subjects", "List the subjects in the student's current examination.", NoInput, a.get_student_subjects),
        ("calculate_overall_performance", "Overall marks, percentage, grade, highest and lowest subject for the current examination.", NoInput, a.calculate_overall_performance),
        ("calculate_subject_percentages", "Obtained marks, total marks, percentage and grade for every subject.", NoInput, a.calculate_subject_percentages),
        ("identify_weak_subjects", "Subjects meeting weakness criteria, each with explained reasons and priority.", ThresholdInput, a.identify_weak_subjects),
        ("identify_strong_subjects", "Subjects that meet strength criteria, with explained reasons.", NoInput, a.identify_strong_subjects),
        ("compare_examinations", "Previous vs current examination: overall and per-subject change, plus trends when 3+ exams exist.", NoInput, a.compare_examinations),
        ("calculate_performance_statistics", "Mean, median, standard deviation, quartiles and distribution of subject percentages.", NoInput, a.calculate_performance_statistics),
        ("get_subject_performance_details", "Detailed marks, rank, history and weakness/strength flags for ONE subject.", SubjectInput, a.get_subject_performance_details),
        ("generate_performance_summary", "A short factual summary of the student's current performance.", NoInput, a.generate_performance_summary),
        ("generate_visualization_data", "Datasets behind the dashboard charts (use to explain a chart).", NoInput, a.generate_visualization_data),
        ("get_academic_improvement_priorities", "Subjects ranked by study priority with the evidence for each rank.", NoInput, a.get_academic_improvement_priorities),
        ("get_topic_mastery", "Quiz-derived topic mastery and weak-topic evidence; optionally filter by subject.", OptionalSubjectInput, a.get_topic_mastery),
    ]


def build_student_tools(analyzer: StudentAnalyzer) -> list[StructuredTool]:
    """Create the LangChain tools bound to one student's analyzer."""
    return [
        StructuredTool.from_function(func=_safe(fn), name=name, description=description, args_schema=schema)
        for name, description, schema, fn in tool_specs(analyzer)
    ]


TOOL_NAMES = [
    "get_student_profile", "get_student_subjects", "calculate_overall_performance", "calculate_subject_percentages",
    "identify_weak_subjects", "identify_strong_subjects", "compare_examinations", "calculate_performance_statistics",
    "get_subject_performance_details", "generate_performance_summary", "generate_visualization_data",
    "get_academic_improvement_priorities",
    "get_topic_mastery",
]

"""Glue between stored data, the analysis engine, charts and the agent orchestrator."""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.orchestrator import AcademicOrchestrator
from app.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.data_engine.analyzer import StudentAnalyzer
from app.data_engine.weakness_detection import WeaknessConfig
from app.schemas.analysis import (
    AcademicReport,
    ChartInfo,
    PerformanceMetrics,
    PerformanceResponse,
    SubjectPerformance,
    VisualizationResponse,
    WeaknessResponse,
)
from app.services import report_service, student_service
from app.visualizations.visualization_service import chart_ids, generate_charts

logger = logging.getLogger(__name__)


def weakness_config(settings: Settings) -> WeaknessConfig:
    return WeaknessConfig(
        weak_threshold=settings.weak_threshold, strong_threshold=settings.strong_threshold,
        relative_gap=settings.relative_gap, decline_points=settings.decline_points,
        inconsistency_std=settings.inconsistency_std, target_gap=settings.target_gap)


def build_analyzer(db: Session, student_id: str, settings: Settings | None = None) -> StudentAnalyzer:
    """Load ONE student's stored data and validate it. Raises DataValidationError if it is unusable."""
    settings = settings or get_settings()
    student = student_service.get_student(db, student_id)
    results = student_service.load_results_df(db, student_id)
    from app.services.quiz_service import mastery
    return StudentAnalyzer(results, student_service.profile_dict(student), weakness_config(settings),
                           topic_mastery=mastery(db, student_id, settings))


def get_performance(db: Session, student_id: str) -> PerformanceResponse:
    a = build_analyzer(db, student_id)
    snap = a.full_snapshot()
    return PerformanceResponse(
        student_id=student_id, metrics=PerformanceMetrics(**snap["overall"]),
        subjects=[SubjectPerformance(**s) for s in snap["subjects"]], statistics=snap["statistics"],
        comparison=snap["comparison"], insights=snap["insights"], summary=snap["summary"]["summary_text"])


def get_weaknesses(db: Session, student_id: str) -> WeaknessResponse:
    a = build_analyzer(db, student_id)
    weak, strong = a.identify_weak_subjects(), a.identify_strong_subjects()
    return WeaknessResponse(
        student_id=student_id, weak_threshold_percent=weak["weak_threshold_percent"],
        pass_mark_percent=weak["pass_mark_percent"], target_percentage=weak["target_percentage"],
        threshold_explanation=weak["threshold_explanation"], weak_subjects=weak["weak_subjects"],
        strong_subjects=strong["strong_subjects"], priorities=a.get_academic_improvement_priorities()["priorities"],
        weak_topics=weak["weak_topics"])


def student_chart_dir(settings: Settings, student_id: str) -> Path:
    return settings.chart_path / student_id


def get_visualizations(db: Session, student_id: str) -> VisualizationResponse:
    settings = get_settings()
    a = build_analyzer(db, student_id, settings)
    data = a.generate_visualization_data()
    charts = generate_charts(data, student_chart_dir(settings, student_id))
    return VisualizationResponse(
        student_id=student_id, data=data,
        charts=[ChartInfo(id=c.id, title=c.title, available=c.available, reason=c.reason,
                          url=f"/students/{student_id}/visualizations/{c.id}/" if c.available else None)
                for c in charts])


def get_chart_file(student_id: str, chart_id: str) -> Path:
    if chart_id not in chart_ids():
        raise NotFoundError("Unknown chart.")
    path = student_chart_dir(get_settings(), student_id) / f"{chart_id}.png"
    if not path.exists():
        raise NotFoundError("Chart not available. Request /visualizations/ first or the data does not support this chart.")
    return path


def run_analysis(db: Session, student_id: str) -> AcademicReport:
    """Validate -> orchestrate agents -> persist report, tasks and a Markdown export."""
    settings = get_settings()
    analyzer = build_analyzer(db, student_id, settings)  # raises before any agent runs if data is invalid
    report = AcademicOrchestrator(settings).run(student_id, analyzer)
    report_id = student_service.save_report(db, student_id, report)
    student_service.sync_tasks(db, student_id, report_id, report.recommendations, report.generated_at)
    try:
        report_service.export_report(report, settings.report_path)
    except OSError:
        logger.exception("Could not export the report file")  # the stored report is still available via the API
    return report

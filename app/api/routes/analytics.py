"""HTTP endpoints for deterministic, non-AI analytics."""
from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, valid_student_id
from app.core.exceptions import DataValidationError
from app.data_engine import advanced_stats, explorer, loss_analysis
from app.services.analysis_service import build_analyzer
from app.services import student_service

router = APIRouter(tags=["analytics"])


class TargetRequest(BaseModel):
    target_percentage: float = Field(ge=0, le=100)


class ChangesRequest(BaseModel):
    changes: dict[str, float]


class WeightsRequest(BaseModel):
    weights: dict[str, float]


class PivotRequest(BaseModel):
    index: str
    columns: str
    values: str = "percentage"
    aggfunc: str = "mean"


def _data(db: Session, student_id: str) -> tuple[Any, Any]:
    analyzer = build_analyzer(db, student_id)
    return analyzer.history, analyzer.profile


@router.get("/students/{student_id}/analytics/summary/")
def analytics_summary(student_id: str = Depends(valid_student_id), db: Session = Depends(get_db)) -> dict[str, Any]:
    frame, _ = _data(db, student_id)
    return {"shape": advanced_stats.distribution_shape(frame),
            "standardized_scores": advanced_stats.standardized_scores(frame),
            "consistency": advanced_stats.consistency_table(frame),
            "outliers": advanced_stats.outlier_report(frame),
            "moving_average": advanced_stats.moving_average(frame),
            "correlations": advanced_stats.subject_correlations(frame),
            "significance": advanced_stats.change_significance(frame),
            "projection": advanced_stats.project_next_exam(frame)}


@router.get("/students/{student_id}/analytics/loss/")
def analytics_loss(student_id: str = Depends(valid_student_id), db: Session = Depends(get_db)) -> dict[str, Any]:
    frame, _ = _data(db, student_id)
    return loss_analysis.marks_lost_pareto(frame)


@router.post("/students/{student_id}/analytics/planner/")
def analytics_planner(payload: TargetRequest, student_id: str = Depends(valid_student_id),
                     db: Session = Depends(get_db)) -> dict[str, Any]:
    frame, _ = _data(db, student_id)
    return loss_analysis.target_planner(frame, payload.target_percentage)


@router.post("/students/{student_id}/analytics/what-if/")
def analytics_what_if(payload: ChangesRequest, student_id: str = Depends(valid_student_id),
                      db: Session = Depends(get_db)) -> dict[str, Any]:
    frame, profile = _data(db, student_id)
    try:
        return loss_analysis.what_if(frame, payload.changes, profile.get("board"))
    except ValueError as exc:
        raise DataValidationError(str(exc)) from exc


@router.post("/students/{student_id}/analytics/weighted/")
def analytics_weighted(payload: WeightsRequest, student_id: str = Depends(valid_student_id),
                       db: Session = Depends(get_db)) -> dict[str, Any]:
    frame, _ = _data(db, student_id)
    try:
        return loss_analysis.weighted_score(frame, payload.weights)
    except ValueError as exc:
        raise DataValidationError(str(exc)) from exc


@router.post("/students/{student_id}/analytics/pivot/")
def analytics_pivot(payload: PivotRequest, student_id: str = Depends(valid_student_id),
                    db: Session = Depends(get_db)) -> dict[str, Any]:
    frame, _ = _data(db, student_id)
    try:
        result = explorer.pivot_results(frame, payload.index, payload.columns, payload.values, payload.aggfunc)
    except ValueError as exc:
        raise DataValidationError(str(exc)) from exc
    return {"columns": [str(c) for c in result.columns], "index": [str(i) for i in result.index],
            "rows": result.reset_index().replace({pd.NA: None}).to_dict("records")}


@router.get("/students/{student_id}/analytics/export/")
def analytics_export(student_id: str = Depends(valid_student_id), format: str = Query("xlsx"),
                     db: Session = Depends(get_db)) -> Response:
    frame, _ = _data(db, student_id)
    if format == "csv":
        return Response(explorer.export_csv(frame), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=student_results.csv"})
    if format != "xlsx":
        raise DataValidationError("format must be xlsx or csv.")
    content = explorer.export_results(frame)
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=student_analytics.xlsx"})


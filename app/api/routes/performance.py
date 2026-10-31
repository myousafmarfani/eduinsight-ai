from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, valid_student_id
from app.schemas.analysis import (
    PerformanceResponse,
    VisualizationResponse,
    WeaknessResponse,
)
from app.services import analysis_service

router = APIRouter(tags=["performance"])


@router.get("/students/{student_id}/performance/", response_model=PerformanceResponse)
def performance(student_id: str = Depends(valid_student_id), db: Session = Depends(get_db)) -> PerformanceResponse:
    """Calculated metrics (no LLM involved)."""
    return analysis_service.get_performance(db, student_id)


@router.get("/students/{student_id}/weaknesses/", response_model=WeaknessResponse)
def weaknesses(student_id: str = Depends(valid_student_id), db: Session = Depends(get_db)) -> WeaknessResponse:
    return analysis_service.get_weaknesses(db, student_id)


@router.get("/students/{student_id}/visualizations/", response_model=VisualizationResponse)
def visualizations(student_id: str = Depends(valid_student_id), db: Session = Depends(get_db)) -> VisualizationResponse:
    """Render the charts and return chart metadata plus the datasets behind them."""
    return analysis_service.get_visualizations(db, student_id)


@router.get("/students/{student_id}/visualizations/{chart_id}/")
def chart_image(chart_id: str, student_id: str = Depends(valid_student_id)) -> FileResponse:
    """A rendered chart PNG (call the list endpoint first, which renders them)."""
    return FileResponse(analysis_service.get_chart_file(student_id, chart_id), media_type="image/png")

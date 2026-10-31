from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, valid_student_id
from app.core.exceptions import NotFoundError
from app.schemas.analysis import AcademicReport, ImprovementTaskRead, TaskUpdate
from app.services import analysis_service, student_service

router = APIRouter(tags=["analysis"])


@router.post("/students/{student_id}/analyze/", response_model=AcademicReport)
def analyze(student_id: str = Depends(valid_student_id), db: Session = Depends(get_db)) -> AcademicReport:
    """Run the full agent workflow. Refuses (422) when the stored data is missing or invalid."""
    return analysis_service.run_analysis(db, student_id)


@router.get("/students/{student_id}/report/", response_model=AcademicReport)
def report(student_id: str = Depends(valid_student_id), db: Session = Depends(get_db)) -> AcademicReport:
    latest = student_service.latest_report(db, student_id)
    if latest is None:
        raise NotFoundError("No report has been generated yet. Run the analysis first.")
    return latest


@router.get("/students/{student_id}/tasks/", response_model=list[ImprovementTaskRead])
def tasks(student_id: str = Depends(valid_student_id), db: Session = Depends(get_db)) -> list[ImprovementTaskRead]:
    return student_service.list_tasks(db, student_id)


@router.patch("/students/{student_id}/tasks/{task_id}/", response_model=ImprovementTaskRead)
def update_task(task_id: str, update: TaskUpdate, student_id: str = Depends(valid_student_id),
                db: Session = Depends(get_db)) -> ImprovementTaskRead:
    return student_service.set_task_completed(db, student_id, task_id, update.completed)

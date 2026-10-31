from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, valid_student_id
from app.schemas.academic import AcademicResult, ResultsRead
from app.services import student_service

router = APIRouter(tags=["results"])


@router.post("/students/{student_id}/results/", response_model=ResultsRead, status_code=status.HTTP_201_CREATED)
def save_results(payload: AcademicResult, student_id: str = Depends(valid_student_id),
                 db: Session = Depends(get_db)) -> ResultsRead:
    """Validate and store the confirmed marks table (422 with row-level issues if anything is wrong)."""
    return student_service.save_results(db, student_id, payload)


@router.get("/students/{student_id}/results/", response_model=ResultsRead)
def get_results(student_id: str = Depends(valid_student_id), db: Session = Depends(get_db)) -> ResultsRead:
    return student_service.get_results(db, student_id)

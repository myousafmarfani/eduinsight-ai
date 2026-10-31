from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, valid_student_id
from app.schemas.student import StudentProfile, StudentRead
from app.services import student_service

router = APIRouter(tags=["students"])


@router.post("/students/", response_model=StudentRead, status_code=status.HTTP_201_CREATED)
def create_student(profile: StudentProfile, db: Session = Depends(get_db)) -> StudentRead:
    return student_service.create_student(db, profile)


@router.get("/students/", response_model=list[StudentRead])
def list_students(db: Session = Depends(get_db)) -> list[StudentRead]:
    return student_service.list_students(db)


@router.get("/students/{student_id}/", response_model=StudentRead)
def get_student(student_id: str = Depends(valid_student_id), db: Session = Depends(get_db)) -> StudentRead:
    return student_service.to_read(db, student_service.get_student(db, student_id))


@router.delete("/students/{student_id}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(student_id: str = Depends(valid_student_id), db: Session = Depends(get_db)) -> Response:
    """Delete the student and every record that belongs to them."""
    student_service.delete_student(db, student_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

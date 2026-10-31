from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, valid_student_id
from app.config import get_settings
from app.schemas.quiz import (
    QuizQuestionPublic,
    QuizSessionRead,
    QuizStart,
    QuizSubmit,
    QuizTopics,
)
from app.services import quiz_service

router = APIRouter(tags=["quiz"])


@router.get("/students/{student_id}/quiz/topics/", response_model=QuizTopics)
def topics(subject: str, student_id: str = Depends(valid_student_id), db: Session = Depends(get_db)) -> QuizTopics:
    return quiz_service.topic_options(db, student_id, subject, get_settings())


@router.post("/students/{student_id}/quiz/", response_model=QuizSessionRead)
def create_quiz(request: QuizStart, student_id: str = Depends(valid_student_id),
                db: Session = Depends(get_db)) -> QuizSessionRead:
    return quiz_service.start_quiz(
        db, student_id, request.subject, request.topic, request.n_questions, get_settings(), request.question_type
    )


@router.get("/students/{student_id}/quiz/mastery/", response_model=list[dict])
def mastery(student_id: str = Depends(valid_student_id), db: Session = Depends(get_db)) -> list[dict]:
    return quiz_service.mastery(db, student_id, get_settings())


@router.get("/students/{student_id}/quiz/{session_id}/", response_model=QuizSessionRead)
def get_quiz(session_id: str, student_id: str = Depends(valid_student_id),
             db: Session = Depends(get_db)) -> QuizSessionRead:
    return quiz_service.get_quiz(db, student_id, session_id)


@router.post("/students/{student_id}/quiz/{session_id}/submit/", response_model=QuizSessionRead)
def submit_quiz(request: QuizSubmit, session_id: str, student_id: str = Depends(valid_student_id),
                db: Session = Depends(get_db)) -> QuizSessionRead:
    return quiz_service.submit_quiz(db, student_id, session_id, request.answers)


@router.post("/students/{student_id}/quiz/{session_id}/questions/{question_id}/flag/",
             response_model=QuizQuestionPublic)
def flag_question(question_id: str, session_id: str, student_id: str = Depends(valid_student_id),
                  db: Session = Depends(get_db)) -> QuizQuestionPublic:
    return quiz_service.flag_question(db, student_id, session_id, question_id)

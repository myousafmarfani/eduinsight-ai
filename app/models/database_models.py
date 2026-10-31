"""SQLAlchemy ORM models. Every child table is keyed (directly or indirectly) to one student."""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100))
    board: Mapped[str] = mapped_column(String(60))
    country: Mapped[str] = mapped_column(String(60))
    grade: Mapped[str] = mapped_column(String(40))
    academic_year: Mapped[str] = mapped_column(String(20))
    school_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    difficult_subjects: Mapped[list] = mapped_column(JSON, default=list)
    difficult_topics: Mapped[dict] = mapped_column(JSON, default=dict)
    preferred_resources: Mapped[list] = mapped_column(JSON, default=list)
    preferred_language: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    examinations: Mapped[list[ExaminationRecord]] = relationship(
        back_populates="student", cascade="all, delete-orphan", order_by="ExaminationRecord.sequence")
    reports: Mapped[list[ReportRecord]] = relationship(
        back_populates="student", cascade="all, delete-orphan", order_by="ReportRecord.created_at")
    tasks: Mapped[list[ImprovementTask]] = relationship(back_populates="student", cascade="all, delete-orphan")
    messages: Mapped[list[ChatMessage]] = relationship(back_populates="student", cascade="all, delete-orphan")
    quiz_sessions: Mapped[list[QuizSession]] = relationship(
        back_populates="student", cascade="all, delete-orphan")


class ExaminationRecord(Base):
    __tablename__ = "examinations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    exam_name: Mapped[str] = mapped_column(String(100))
    exam_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0)  # chronological position (0 = oldest)

    student: Mapped[Student] = relationship(back_populates="examinations")
    marks: Mapped[list[SubjectMark]] = relationship(
        back_populates="examination", cascade="all, delete-orphan", order_by="SubjectMark.position")


class SubjectMark(Base):
    __tablename__ = "subject_marks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    exam_id: Mapped[str] = mapped_column(ForeignKey("examinations.id", ondelete="CASCADE"), index=True)
    subject: Mapped[str] = mapped_column(String(80))
    obtained: Mapped[float] = mapped_column(Float)
    total: Mapped[float] = mapped_column(Float)
    grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    examination: Mapped[ExaminationRecord] = relationship(back_populates="marks")


class ReportRecord(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict] = mapped_column(JSON)

    student: Mapped[Student] = relationship(back_populates="reports")


class ImprovementTask(Base):
    __tablename__ = "improvement_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    report_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    subject: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    student: Mapped[Student] = relationship(back_populates="tasks")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    role: Mapped[str] = mapped_column(String(10))  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    student: Mapped[Student] = relationship(back_populates="messages")


class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    subject: Mapped[str] = mapped_column(String(80))
    topic: Mapped[str | None] = mapped_column(String(120), nullable=True)
    difficulty_mix: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    student: Mapped[Student] = relationship(back_populates="quiz_sessions")
    questions: Mapped[list[QuizQuestion]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="QuizQuestion.position")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("quiz_sessions.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON)
    correct_index: Mapped[int] = mapped_column(Integer, default=-1)
    explanation: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_type: Mapped[str] = mapped_column(String(10), default="mcq")
    topic: Mapped[str] = mapped_column(String(120))
    difficulty: Mapped[str] = mapped_column(String(10))
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped[QuizSession] = relationship(back_populates="questions")
    answers: Mapped[list[QuizAnswer]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="QuizAnswer.answered_at")


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    question_id: Mapped[str] = mapped_column(ForeignKey("quiz_questions.id", ondelete="CASCADE"), index=True)
    selected_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    question: Mapped[QuizQuestion] = relationship(back_populates="answers")

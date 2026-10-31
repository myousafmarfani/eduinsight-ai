"""Quiz API schemas. Correct answers are intentionally separate from in-progress responses."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class QuizDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuizStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class QuizQuestionType(str, Enum):
    MCQ = "mcq"
    QA = "qa"


class QuizStart(BaseModel):
    subject: str = Field(min_length=1, max_length=80)
    topic: str | None = Field(default=None, max_length=120)
    n_questions: int = Field(default=5, ge=1, le=20)
    question_type: QuizQuestionType = QuizQuestionType.MCQ


class QuizQuestionCreate(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    options: list[str] = Field(default_factory=list, max_length=4)
    correct_index: int = Field(default=-1, ge=-1, le=3)
    explanation: str = Field(min_length=1, max_length=1000)
    answer: str = Field(default="", max_length=1000)
    topic: str = Field(min_length=1, max_length=120)
    difficulty: QuizDifficulty
    question_type: QuizQuestionType = QuizQuestionType.MCQ


class QuizQuestionPublic(BaseModel):
    id: str
    text: str
    options: list[str]
    question_type: QuizQuestionType
    topic: str
    difficulty: QuizDifficulty
    flagged: bool = False


class QuizQuestionResult(QuizQuestionPublic):
    selected_index: int | None
    selected_text: str | None
    is_correct: bool
    correct_index: int
    explanation: str
    answer: str | None


class QuizSessionRead(BaseModel):
    id: str
    student_id: str
    subject: str
    topic: str | None
    difficulty_mix: dict[str, int]
    status: QuizStatus
    created_at: datetime
    completed_at: datetime | None
    score: float | None
    questions: list[QuizQuestionPublic | QuizQuestionResult]
    question_count: int
    note: str | None = None


class QuizSubmit(BaseModel):
    answers: list[int | str | None]


class QuizTopics(BaseModel):
    subject: str
    topics: list[dict[str, str]]


class QuizMasteryRow(BaseModel):
    subject: str
    topic: str
    attempts: int
    correct: int
    sessions: int
    accuracy: float
    recency_weighted_accuracy: float
    trend: float | None
    trend_label: str
    mastery_level: str | None
    confidence_note: str
    evidence: str
    enough_data: bool

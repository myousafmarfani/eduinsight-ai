"""Persistence and orchestration for scoped adaptive practice quizzes."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agents.llm import get_llm
from app.agents.openrouter import OpenRouterAPIError
from app.agents.quiz_generator import generate_questions, propose_topics
from app.config import Settings, get_settings
from app.core.exceptions import (
    ConflictError,
    DataValidationError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.data_engine.mastery import adaptive_difficulty_mix, calculate_mastery_table
from app.models.database_models import QuizAnswer, QuizQuestion, QuizSession
from app.schemas.quiz import (
    QuizDifficulty,
    QuizQuestionCreate,
    QuizQuestionPublic,
    QuizQuestionResult,
    QuizQuestionType,
    QuizSessionRead,
    QuizStatus,
    QuizTopics,
)
from app.services import student_service
from app.services.analysis_service import build_analyzer


def _session(db: Session, student_id: str, session_id: str) -> QuizSession:
    value = db.scalar(
        select(QuizSession).options(selectinload(QuizSession.questions).selectinload(QuizQuestion.answers))
        .where(QuizSession.id == session_id, QuizSession.student_id == student_id)
    )
    if value is None:
        raise NotFoundError("Quiz session not found.")
    return value


def _records(db: Session, student_id: str) -> list[dict[str, Any]]:
    sessions = db.scalars(
        select(QuizSession).options(selectinload(QuizSession.questions).selectinload(QuizQuestion.answers))
        .where(QuizSession.student_id == student_id, QuizSession.status == QuizStatus.COMPLETED.value)
    ).all()
    return [
        {"session_id": session.id, "subject": session.subject, "topic": question.topic,
         "is_correct": answer.is_correct, "flagged": question.flagged}
        for session in sessions for question in session.questions
        for answer in question.answers
    ]


def _public(question: QuizQuestion) -> QuizQuestionPublic:
    return QuizQuestionPublic(id=question.id, text=question.text, options=question.options,
                              question_type=QuizQuestionType(question.question_type),
                              topic=question.topic, difficulty=QuizDifficulty(question.difficulty),
                              flagged=question.flagged)


def _read(session: QuizSession, *, include_answers: bool = False, note: str | None = None) -> QuizSessionRead:
    questions = []
    for question in session.questions:
        if include_answers and question.answers:
            answer = question.answers[-1]
            questions.append(QuizQuestionResult(
                **_public(question).model_dump(), selected_index=answer.selected_index,
                selected_text=answer.selected_text, is_correct=answer.is_correct,
                correct_index=question.correct_index, explanation=question.explanation,
                answer=question.answer))
        else:
            questions.append(_public(question))
    return QuizSessionRead(
        id=session.id, student_id=session.student_id, subject=session.subject, topic=session.topic,
        difficulty_mix=session.difficulty_mix, status=QuizStatus(session.status), created_at=session.created_at,
        completed_at=session.completed_at, score=session.score, questions=questions,
        question_count=len(questions), note=note,
    )


def topic_options(db: Session, student_id: str, subject: str, settings: Settings | None = None) -> QuizTopics:
    settings = settings or get_settings()
    student = student_service.get_student(db, student_id)
    profile = student_service.profile_dict(student)
    seen = {r["topic"] for r in _records(db, student_id) if r["subject"].lower() == subject.lower()}
    entered = [str(topic).strip() for key, values in (profile.get("difficult_topics") or {}).items()
               if key.lower() == subject.lower() for topic in values if str(topic).strip()]
    topics = [{"topic": topic, "label": "student-entered"} for topic in dict.fromkeys(entered)]
    topics.extend({"topic": topic, "label": "from-quiz"} for topic in sorted(seen - {x["topic"] for x in topics}))
    if not topics:
        llm = get_llm(settings)
        if llm is not None:
            try:
                topics.extend({"topic": topic, "label": "AI-suggested"}
                              for topic in propose_topics(llm, profile=profile, subject=subject))
            except Exception as exc:
                raise ServiceUnavailableError("The AI topic suggestions are temporarily unavailable.") from exc
    return QuizTopics(subject=subject, topics=topics[:8])


def _validate_questions(questions: list[QuizQuestionCreate], excluded: set[str]) -> list[QuizQuestionCreate]:
    accepted: list[QuizQuestionCreate] = []
    seen = set(excluded)
    for question in questions:
        text = question.text.strip()
        options = [option.strip() for option in question.options]
        normalized = {option.casefold() for option in options}
        if not text or question.question_type == QuizQuestionType.MCQ and (
            len(normalized) != 4 or any(not option for option in options)
        ):
            continue
        if question.question_type == QuizQuestionType.QA and (
            options or question.correct_index != -1 or not question.answer.strip()
        ):
            continue
        if question.question_type == QuizQuestionType.MCQ and not 0 <= question.correct_index < 4:
            continue
        if text.casefold() in seen:
            continue
        question.text, question.options, question.answer = text, options, question.answer.strip()
        seen.add(text.casefold())
        accepted.append(question)
    return accepted


def start_quiz(db: Session, student_id: str, subject: str, topic: str | None, n_questions: int,
               settings: Settings | None = None,
               question_type: QuizQuestionType = QuizQuestionType.MCQ) -> QuizSessionRead:
    settings = settings or get_settings()
    student = student_service.get_student(db, student_id)
    analyzer = build_analyzer(db, student_id, settings)
    subjects = [str(value) for value in analyzer.subjects["subject"]]
    matched = next((value for value in subjects if value.lower() == subject.strip().lower()), None)
    if matched is None:
        raise DataValidationError(f"Subject '{subject}' is not in the student's saved results.")
    llm = get_llm(settings)
    if llm is None:
        raise ServiceUnavailableError("Quiz questions require an available OPENROUTER_API_KEY; no questions were created.")
    prior = db.scalars(select(QuizQuestion).join(QuizSession).where(
        QuizSession.student_id == student_id).order_by(QuizQuestion.id.desc()).limit(50)).all()
    excluded = {question.text.casefold() for question in prior}
    records = _records(db, student_id)
    topic_records = [r for r in records if r["subject"].lower() == matched.lower() and
                     (topic is None or r["topic"].lower() == topic.lower())]
    recent = calculate_mastery_table(topic_records, min_questions=1, min_sessions=1)
    recent_accuracy = recent[0]["recency_weighted_accuracy"] if recent else None
    mix = adaptive_difficulty_mix(recent_accuracy, n_questions)
    profile = student_service.profile_dict(student)
    valid: list[QuizQuestionCreate] = []
    note = None
    for _ in range(3):
        remaining = n_questions - len(valid)
        if remaining <= 0:
            break
        try:
            batch = generate_questions(llm, profile=profile, subject=matched, topic=topic,
                                       difficulty_mix=mix, count=remaining, excluded_texts=excluded,
                                       question_type=question_type)
        except OpenRouterAPIError as exc:
            if exc.status_code == 429:
                raise ServiceUnavailableError(
                    "The AI provider rate limit has been reached. Wait for the free-model daily reset "
                    "or configure a paid/available LLM_MODEL in .env; no quiz session was created."
                ) from exc
            raise ServiceUnavailableError(
                "The AI quiz provider rejected the request. Check LLM_MODEL and OPENROUTER_API_KEY; "
                "no quiz session was created."
            ) from exc
        except Exception as exc:
            raise ServiceUnavailableError(
                "The AI quiz generator is temporarily unavailable; no quiz session was created.") from exc
        fresh = _validate_questions(batch, excluded)
        valid.extend(fresh)
        excluded.update(q.text.casefold() for q in fresh)
        if not fresh:
            break
    if not valid:
        raise ServiceUnavailableError("The LLM did not return any valid quiz questions; no session was created.")
    if len(valid) < n_questions:
        note = f"Only {len(valid)} valid question(s) were generated out of {n_questions}."
    quiz = QuizSession(student_id=student_id, subject=matched, topic=topic, difficulty_mix=mix)
    quiz.questions = [QuizQuestion(text=q.text, options=q.options, correct_index=q.correct_index,
                                   explanation=q.explanation, answer=q.answer or None,
                                   question_type=q.question_type.value, topic=q.topic, difficulty=q.difficulty.value,
                                   position=index) for index, q in enumerate(valid)]
    db.add(quiz)
    db.commit()
    return _read(quiz, note=note)


def get_quiz(db: Session, student_id: str, session_id: str) -> QuizSessionRead:
    quiz = _session(db, student_id, session_id)
    return _read(quiz, include_answers=quiz.status == QuizStatus.COMPLETED.value)


def submit_quiz(db: Session, student_id: str, session_id: str, answers: list[int | None]) -> QuizSessionRead:
    quiz = _session(db, student_id, session_id)
    if quiz.status == QuizStatus.COMPLETED.value:
        raise ConflictError("This quiz has already been submitted.")
    if len(answers) != len(quiz.questions):
        raise DataValidationError(f"Submit exactly {len(quiz.questions)} answer(s).")
    correct = 0
    for question, selected in zip(quiz.questions, answers):
        selected_text = selected if isinstance(selected, str) else None
        if question.question_type == QuizQuestionType.MCQ.value:
            if selected is not None and (not isinstance(selected, int) or not 0 <= selected < len(question.options)):
                raise DataValidationError("Each multiple-choice answer must be an option index.")
            is_correct = selected == question.correct_index
        else:
            if selected_text is not None and not selected_text.strip():
                selected_text = None
            is_correct = bool(selected_text and question.answer and
                              selected_text.strip().casefold() == question.answer.strip().casefold())
        correct += int(is_correct)
        question.answers.append(QuizAnswer(
            selected_index=selected if isinstance(selected, int) else None,
            selected_text=selected_text, is_correct=is_correct))
    quiz.status = QuizStatus.COMPLETED.value
    quiz.completed_at = datetime.now(UTC)
    quiz.score = round(correct / len(quiz.questions) * 100, 2)
    db.commit()
    return _read(quiz, include_answers=True)


def flag_question(db: Session, student_id: str, session_id: str, question_id: str) -> QuizQuestionPublic:
    quiz = _session(db, student_id, session_id)
    question = next((q for q in quiz.questions if q.id == question_id), None)
    if question is None:
        raise NotFoundError("Quiz question not found.")
    question.flagged = True
    db.commit()
    return _public(question)


def mastery(db: Session, student_id: str, settings: Settings | None = None) -> list[dict[str, Any]]:
    settings = settings or get_settings()
    student_service.get_student(db, student_id)
    return calculate_mastery_table(_records(db, student_id), min_questions=settings.mastery_min_questions,
                                   min_sessions=settings.mastery_min_sessions)

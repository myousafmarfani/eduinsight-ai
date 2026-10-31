"""Persistence for students, results, reports, tasks and chat history."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import DatabaseError, DataValidationError, NotFoundError
from app.data_engine.preprocessing import DEFAULT_EXAM_NAME, clean_results
from app.models.database_models import (
    ChatMessage,
    ExaminationRecord,
    ImprovementTask,
    ReportRecord,
    Student,
    SubjectMark,
)
from app.schemas.academic import AcademicResult, Examination, ResultsRead, SubjectResult
from app.schemas.analysis import (
    AcademicReport,
    ImprovementRecommendation,
    ImprovementTaskRead,
    Priority,
)
from app.schemas.student import StudentProfile, StudentRead

logger = logging.getLogger(__name__)


def _commit(db: Session, what: str) -> None:
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Database error while %s", what)
        raise DatabaseError(f"Could not save changes ({what}).") from exc


# ---- students -----------------------------------------------------------------------------------
def _has_results(db: Session, student_id: str) -> bool:
    return db.scalar(select(ExaminationRecord.id).where(ExaminationRecord.student_id == student_id).limit(1)) is not None


def to_read(db: Session, student: Student) -> StudentRead:
    return StudentRead(
        student_id=student.id, created_at=student.created_at, has_results=_has_results(db, student.id),
        name=student.name, board=student.board, country=student.country, grade=student.grade,
        academic_year=student.academic_year, school_name=student.school_name, goals=student.goals,
        target_percentage=student.target_percentage, difficult_subjects=student.difficult_subjects or [],
        difficult_topics=student.difficult_topics or {}, preferred_resources=student.preferred_resources or [],
        preferred_language=student.preferred_language)


def create_student(db: Session, profile: StudentProfile) -> StudentRead:
    student = Student(**profile.model_dump())
    db.add(student)
    _commit(db, "creating the student")
    return to_read(db, student)


def list_students(db: Session) -> list[StudentRead]:
    students = db.scalars(select(Student).order_by(Student.created_at.desc())).all()
    return [to_read(db, s) for s in students]


def get_student(db: Session, student_id: str) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise NotFoundError("Student not found.")
    return student


def delete_student(db: Session, student_id: str) -> None:
    student = get_student(db, student_id)
    db.delete(student)
    _commit(db, "deleting the student")


def profile_dict(student: Student) -> dict:
    """Plain dict handed to the analysis engine and agents (no ORM objects cross that boundary)."""
    return {
        "student_id": student.id, "name": student.name, "board": student.board, "country": student.country,
        "grade": student.grade, "academic_year": student.academic_year, "school_name": student.school_name,
        "goals": student.goals, "target_percentage": student.target_percentage,
        "difficult_subjects": student.difficult_subjects or [], "difficult_topics": student.difficult_topics or {},
        "preferred_resources": student.preferred_resources or [], "preferred_language": student.preferred_language,
    }


# ---- results ------------------------------------------------------------------------------------
def save_results(db: Session, student_id: str, payload: AcademicResult) -> ResultsRead:
    """Validate the submitted table with the data engine and store it grouped by examination."""
    get_student(db, student_id)
    raw = pd.DataFrame([{
        "exam": r.exam, "exam_type": r.exam_type, "exam_date": r.exam_date.isoformat() if r.exam_date else None,
        "subject": r.subject, "obtained": r.obtained, "total": r.total, "grade": r.grade,
    } for r in payload.rows])
    cleaned, report = clean_results(raw, default_total=payload.default_total)
    if not report.is_valid:
        raise DataValidationError("Some rows need correcting before the results can be saved.", report.to_dicts())

    dates: dict[str, object] = {}
    for r in payload.rows:
        name = (r.exam or "").strip() or DEFAULT_EXAM_NAME
        if r.exam_date and name not in dates:
            dates[name] = r.exam_date

    existing = db.scalars(select(ExaminationRecord).where(ExaminationRecord.student_id == student_id)).all()
    offset = 0
    if payload.replace_existing:
        for exam in existing:
            db.delete(exam)
        db.flush()
    elif existing:
        taken = {e.exam_name.lower() for e in existing}
        clash = sorted({n for n in cleaned["exam"].unique() if n.lower() in taken})
        if clash:
            raise DataValidationError(
                f"Examination(s) already saved: {', '.join(clash)}. Rename them or replace the existing results.")
        offset = max(e.sequence for e in existing) + 1

    for order, group in cleaned.groupby("exam_order", sort=True):
        name = str(group["exam"].iloc[0])
        types = [t for t in group["exam_type"] if t]
        record = ExaminationRecord(student_id=student_id, exam_name=name, exam_type=types[0] if types else None,
                                   exam_date=dates.get(name), sequence=int(order) + offset)
        for position, row in enumerate(group.itertuples()):
            record.marks.append(SubjectMark(subject=row.subject, obtained=float(row.obtained), total=float(row.total),
                                            grade=row.grade or None, position=position))
        db.add(record)
    _commit(db, "saving results")
    return get_results(db, student_id)


def get_results(db: Session, student_id: str) -> ResultsRead:
    get_student(db, student_id)
    exams = db.scalars(select(ExaminationRecord).where(ExaminationRecord.student_id == student_id)
                       .order_by(ExaminationRecord.sequence)).all()
    return ResultsRead(student_id=student_id, examinations=[
        Examination(exam_name=e.exam_name, exam_type=e.exam_type, exam_date=e.exam_date, sequence=e.sequence,
                    subjects=[SubjectResult(subject=m.subject, obtained=m.obtained, total=m.total, grade=m.grade)
                              for m in e.marks])
        for e in exams])


def load_results_df(db: Session, student_id: str) -> pd.DataFrame:
    """Stored results as a long DataFrame in chronological order (input to the analysis engine)."""
    get_student(db, student_id)
    exams = db.scalars(select(ExaminationRecord).where(ExaminationRecord.student_id == student_id)
                       .order_by(ExaminationRecord.sequence)).all()
    rows = [{"exam": e.exam_name, "exam_type": e.exam_type or "", "subject": m.subject, "obtained": m.obtained,
             "total": m.total, "grade": m.grade or "", "exam_order": e.sequence}
            for e in exams for m in e.marks]
    if not rows:
        raise DataValidationError("No academic results have been saved for this student yet.")
    return pd.DataFrame(rows)


# ---- reports & tasks ----------------------------------------------------------------------------
def save_report(db: Session, student_id: str, report: AcademicReport) -> str:
    record = ReportRecord(student_id=student_id, ai_generated=report.ai_generated, payload=report.model_dump(mode="json"))
    db.add(record)
    _commit(db, "saving the report")
    return record.id


def latest_report(db: Session, student_id: str) -> AcademicReport | None:
    get_student(db, student_id)
    record = db.scalars(select(ReportRecord).where(ReportRecord.student_id == student_id)
                        .order_by(ReportRecord.created_at.desc()).limit(1)).first()
    return AcademicReport.model_validate(record.payload) if record else None


def sync_tasks(db: Session, student_id: str, report_id: str, recommendations: list[ImprovementRecommendation],
               report_created_at: datetime | None = None) -> None:
    """Replace open tasks with the new plan; completed tasks are kept so progress is not lost."""
    db.execute(delete(ImprovementTask).where(ImprovementTask.student_id == student_id, ImprovementTask.completed.is_(False)))
    done = {(t.subject.lower(), t.description) for t in db.scalars(
        select(ImprovementTask).where(ImprovementTask.student_id == student_id))}
    from app.models.database_models import QuizSession
    quiz_after = {row.subject.lower() for row in db.scalars(select(QuizSession).where(
        QuizSession.student_id == student_id, QuizSession.status == "completed",
        QuizSession.completed_at > (report_created_at or datetime.now(UTC)))).all()}
    for rec in recommendations:
        description = "Practice quiz to collect topic-level evidence."
        if (rec.subject.lower(), description) not in done:
            db.add(ImprovementTask(student_id=student_id, report_id=report_id, subject=rec.subject,
                                   description=description, priority=rec.priority.value,
                                   completed=rec.subject.lower() in quiz_after,
                                   completed_at=datetime.now(UTC) if rec.subject.lower() in quiz_after else None))
        for action in rec.actions:
            if (rec.subject.lower(), action) not in done:
                db.add(ImprovementTask(student_id=student_id, report_id=report_id, subject=rec.subject,
                                       description=action, priority=rec.priority.value))
    _commit(db, "saving improvement tasks")


def _task_read(t: ImprovementTask) -> ImprovementTaskRead:
    return ImprovementTaskRead(id=t.id, subject=t.subject, description=t.description, priority=Priority(t.priority),
                               completed=t.completed, completed_at=t.completed_at)


def list_tasks(db: Session, student_id: str) -> list[ImprovementTaskRead]:
    get_student(db, student_id)
    order = {"high": 0, "medium": 1, "low": 2}
    tasks = db.scalars(select(ImprovementTask).where(ImprovementTask.student_id == student_id)
                       .order_by(ImprovementTask.created_at)).all()
    return [_task_read(t) for t in sorted(tasks, key=lambda t: (order.get(t.priority, 3), t.subject))]


def set_task_completed(db: Session, student_id: str, task_id: str, completed: bool) -> ImprovementTaskRead:
    task = db.get(ImprovementTask, task_id)
    if task is None or task.student_id != student_id:  # the student check keeps tasks separated per student
        raise NotFoundError("Task not found.")
    task.completed = completed
    task.completed_at = datetime.now(UTC) if completed else None
    _commit(db, "updating the task")
    return _task_read(task)


# ---- chat history -------------------------------------------------------------------------------
def add_chat_message(db: Session, student_id: str, session_id: str, role: str, content: str) -> None:
    db.add(ChatMessage(student_id=student_id, session_id=session_id, role=role, content=content))
    _commit(db, "saving the chat message")


def recent_chat_messages(db: Session, student_id: str, session_id: str, limit: int = 12) -> list[tuple[str, str]]:
    """Last `limit` (role, content) pairs of this student's session, oldest first."""
    rows = db.scalars(select(ChatMessage).where(ChatMessage.student_id == student_id, ChatMessage.session_id == session_id)
                      .order_by(ChatMessage.id.desc()).limit(limit)).all()
    return [(m.role, m.content) for m in reversed(rows)]

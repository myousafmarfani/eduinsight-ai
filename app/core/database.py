"""SQLAlchemy engine, session factory and FastAPI dependency."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Create (once) and return the SQLAlchemy engine."""
    global _engine, _session_factory
    if _engine is None:
        url = get_settings().sqlalchemy_url
        kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
        _engine = create_engine(url, future=True, **kwargs)
        if url.startswith("sqlite"):

            @event.listens_for(_engine, "connect")
            def _enable_foreign_keys(dbapi_connection, _record):  # pragma: no cover - trivial
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        _session_factory = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


def init_db() -> None:
    """Create all tables (idempotent)."""
    from app.models import database_models  # noqa: F401  (registers models on Base.metadata)

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            columns = {column["name"] for column in inspect(engine).get_columns("quiz_questions")}
            if "answer" not in columns:
                connection.execute(text("ALTER TABLE quiz_questions ADD COLUMN answer TEXT"))
            if "question_type" not in columns:
                connection.execute(text(
                    "ALTER TABLE quiz_questions ADD COLUMN question_type VARCHAR(10) NOT NULL DEFAULT 'mcq'"
                ))
            answer_columns = {column["name"] for column in inspect(engine).get_columns("quiz_answers")}
            if "selected_text" not in answer_columns:
                connection.execute(text("ALTER TABLE quiz_answers ADD COLUMN selected_text TEXT"))


def reset_engine() -> None:
    """Dispose the engine so a new DATABASE_URL takes effect (used by tests)."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()

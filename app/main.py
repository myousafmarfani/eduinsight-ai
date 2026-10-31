"""FastAPI application entry point:  uvicorn app.main:app --reload"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import (
    analysis,
    analytics,
    boards,
    chat,
    health,
    marksheets,
    performance,
    quiz,
    results,
    students,
)
from app.config import get_settings
from app.core.database import init_db
from app.core.exceptions import (
    ConflictError,
    DatabaseError,
    DataValidationError,
    ExtractionError,
    NotFoundError,
    ServiceUnavailableError,
    UnsupportedFileError,
)
from app.core.logging_config import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    for directory in (settings.upload_path, settings.report_path, settings.chart_path):
        logger.info("Storage directory ready: %s", directory)
    init_db()
    logger.info("Database ready. LLM configured: %s | Tavily configured: %s",
                settings.llm_configured, settings.tavily_configured)
    yield


app = FastAPI(
    title="AI-Powered Student Feedback Agent", version="1.0.0", lifespan=lifespan,
    description="Academic performance analysis with Pandas/NumPy, LangChain agents, Tavily resource search and a chatbot.")

app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origin_list, allow_methods=["*"], allow_headers=["*"])


def _error(status_code: int, message: str, issues: list | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": {"message": message, "issues": issues or []}})


@app.exception_handler(NotFoundError)
async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
    return _error(404, str(exc))


@app.exception_handler(DataValidationError)
async def _invalid_data(_: Request, exc: DataValidationError) -> JSONResponse:
    return _error(422, str(exc), exc.issues)


@app.exception_handler(ExtractionError)
async def _extraction(_: Request, exc: ExtractionError) -> JSONResponse:
    return _error(422, str(exc))


@app.exception_handler(UnsupportedFileError)
async def _unsupported(_: Request, exc: UnsupportedFileError) -> JSONResponse:
    return _error(400, str(exc))


@app.exception_handler(ServiceUnavailableError)
async def _unavailable(_: Request, exc: ServiceUnavailableError) -> JSONResponse:
    return _error(503, str(exc))


@app.exception_handler(ConflictError)
async def _conflict(_: Request, exc: ConflictError) -> JSONResponse:
    return _error(409, str(exc))


@app.exception_handler(DatabaseError)
@app.exception_handler(SQLAlchemyError)
async def _database(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Database failure")
    return _error(500, "A database error occurred. Please try again.")


for module in (health, boards, students, marksheets, results, performance, analysis, analytics, chat, quiz):
    app.include_router(module.router)

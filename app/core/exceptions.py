"""Domain exceptions. API exception handlers (app/main.py) translate them to HTTP responses."""
from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for expected application errors."""


class NotFoundError(AppError):
    """A requested record does not exist."""


class DataValidationError(AppError):
    """Submitted or stored academic data is invalid. `issues` lists row-level problems."""

    def __init__(self, message: str, issues: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.issues = issues or []


class ExtractionError(AppError):
    """A marksheet file could not be read or contained no usable data."""


class UnsupportedFileError(AppError):
    """Unsupported, oversized, or corrupted upload."""


class DatabaseError(AppError):
    """A database operation failed."""


class ServiceUnavailableError(AppError):
    """An optional external service (LLM, Tavily, OCR) is unavailable."""


class ConflictError(AppError):
    """The requested operation conflicts with the current resource state."""

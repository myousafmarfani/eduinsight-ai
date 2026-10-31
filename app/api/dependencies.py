"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import HTTPException

from app.core.database import get_db  # re-exported for routers
from app.utils.validators import is_valid_uuid

__all__ = ["get_db", "valid_student_id"]


def valid_student_id(student_id: str) -> str:
    """Reject malformed student identifiers before touching the database."""
    if not is_valid_uuid(student_id):
        raise HTTPException(status_code=422, detail="Invalid student identifier.")
    return student_id

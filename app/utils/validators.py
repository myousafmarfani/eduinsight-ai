"""Small, dependency-free validators."""
from __future__ import annotations

import uuid


def is_valid_uuid(value: str) -> bool:
    """True when `value` is a canonical UUID string."""
    try:
        return str(uuid.UUID(str(value))) == str(value).lower()
    except (ValueError, AttributeError, TypeError):
        return False


def validate_marks(obtained: float | None, total: float | None) -> list[str]:
    """Return human-readable problems with an (obtained, total) pair (empty list = fine)."""
    problems: list[str] = []
    if obtained is None:
        problems.append("Obtained marks are missing.")
    if total is None:
        problems.append("Total marks are missing.")
    if problems:
        return problems
    if total <= 0:
        problems.append("Total marks must be greater than zero.")
    if obtained < 0:
        problems.append("Obtained marks cannot be negative.")
    if total > 0 and obtained > total:
        problems.append("Obtained marks exceed total marks.")
    return problems

from __future__ import annotations

from fastapi import APIRouter

from app.data_engine.board_config import list_boards

router = APIRouter(tags=["boards"])


@router.get("/boards/")
def boards() -> list[dict]:
    """Registered education boards with their grading notes (drives the frontend board selector)."""
    return [{"key": b.key, "name": b.name, "country": b.country, "pass_percentage": b.pass_percentage,
             "fixed_grade_scale": b.fixed_scale, "notes": b.notes} for b in list_boards()]

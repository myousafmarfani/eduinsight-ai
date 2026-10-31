from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.config import get_settings
from app.services.document_service import ocr_available

router = APIRouter(tags=["health"])


@router.get("/health/")
def health(db: Session = Depends(get_db)) -> dict:
    """Service status including which optional integrations are configured."""
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001
        database = "unavailable"
    return {"status": "ok" if database == "ok" else "degraded", "database": database,
            "llm_configured": settings.llm_configured, "tavily_configured": settings.tavily_configured,
            "ocr_available": ocr_available()}

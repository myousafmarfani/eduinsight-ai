from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, valid_student_id
from app.config import get_settings
from app.core.security import new_upload_path
from app.schemas.academic import ExtractedMarksheet
from app.services import student_service
from app.services.document_service import extract_marksheet
from app.utils.file_handlers import validate_upload

logger = logging.getLogger(__name__)
router = APIRouter(tags=["marksheets"])


@router.post("/students/{student_id}/marksheets/upload", response_model=ExtractedMarksheet)
async def upload_marksheet(
    student_id: str = Depends(valid_student_id),
    file: UploadFile = File(...),
    default_total: float | None = Form(default=None),
    exam_name: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> ExtractedMarksheet:
    """Read a marksheet and return *proposed* rows for the student to review. Nothing is saved yet."""
    student_service.get_student(db, student_id)
    settings = get_settings()
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    filename = file.filename or "upload"
    _, file_type = validate_upload(filename, content, settings.max_upload_mb)

    path = new_upload_path(settings.upload_path, student_id, filename)
    path.write_bytes(content)
    try:
        return await run_in_threadpool(extract_marksheet, content, filename, file_type, default_total, exam_name)
    finally:
        if not settings.keep_uploaded_files:  # the marksheet is personal data; keep only what the student confirms
            path.unlink(missing_ok=True)

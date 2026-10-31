"""Filesystem safety helpers for uploads."""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.core.exceptions import UnsupportedFileError

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    """Strip directories and unsafe characters from a client-supplied filename."""
    name = Path(filename.replace("\\", "/")).name
    name = _SAFE.sub("_", name).strip("._")
    return name[:100] or "upload"


def ensure_within_directory(base: Path, target: Path) -> Path:
    """Raise if `target` escapes `base` (path traversal protection)."""
    base_resolved = base.resolve()
    target_resolved = target.resolve()
    if base_resolved != target_resolved and base_resolved not in target_resolved.parents:
        raise UnsupportedFileError("Invalid file path.")
    return target_resolved


def new_upload_path(upload_root: Path, student_id: str, filename: str) -> Path:
    """Build a unique, safe path for an uploaded file inside the student's own folder."""
    folder = upload_root / student_id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid.uuid4().hex}_{sanitize_filename(filename)}"
    return ensure_within_directory(upload_root, path)

"""Upload validation: allowed types, size, and content signatures."""
from __future__ import annotations

from pathlib import Path

from app.core.exceptions import UnsupportedFileError

ALLOWED_EXTENSIONS: dict[str, str] = {
    ".csv": "csv", ".xlsx": "xlsx", ".pdf": "pdf", ".png": "image", ".jpg": "image", ".jpeg": "image",
}
_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF",), ".png": (b"\x89PNG\r\n\x1a\n",), ".jpg": (b"\xff\xd8\xff",), ".jpeg": (b"\xff\xd8\xff",),
    ".xlsx": (b"PK\x03\x04",),
}


def detect_file_type(filename: str) -> tuple[str, str]:
    """Return (extension, logical type) or raise for unsupported extensions."""
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise UnsupportedFileError(f"Unsupported file type '{ext or 'none'}'. Allowed types: {allowed}.")
    return ext, ALLOWED_EXTENSIONS[ext]


def validate_upload(filename: str, content: bytes, max_mb: int) -> tuple[str, str]:
    """Check extension, size and file signature. Returns (extension, logical type)."""
    ext, file_type = detect_file_type(filename)
    if not content:
        raise UnsupportedFileError("The uploaded file is empty.")
    if len(content) > max_mb * 1024 * 1024:
        raise UnsupportedFileError(f"File is larger than the {max_mb} MB limit.")
    signatures = _SIGNATURES.get(ext)
    if signatures and not content.startswith(signatures):
        raise UnsupportedFileError(f"The file content does not look like a valid {ext} file (it may be corrupted).")
    if ext == ".csv" and b"\x00" in content[:4096]:
        raise UnsupportedFileError("The file does not look like a text CSV file.")
    return ext, file_type

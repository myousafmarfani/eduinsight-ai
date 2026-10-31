"""Extract proposed marks from uploaded CSV / Excel / PDF / image files.

Principles: marksheet layouts differ, so every extraction is a *proposal*; rows carry a confidence,
problems are reported as issues, and nothing is silently invented. The student reviews and edits
the rows before anything is saved or analysed.
"""
from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass

import pandas as pd

from app.core.exceptions import ExtractionError
from app.data_engine.preprocessing import DEFAULT_EXAM_NAME, clean_results
from app.schemas.academic import DataIssueModel, ExtractedMarksheet, ExtractedRow

logger = logging.getLogger(__name__)

MAX_PDF_PAGES = 10
_IGNORE_LINE = re.compile(
    r"\b(roll|seat|candidate|father|mother|dob|date of birth|issued|controller|signature|board|school|"
    r"grand total|total marks|percentage|aggregate|result)\b", re.IGNORECASE)
_SLASH_ROW = re.compile(
    r"^(?P<subject>[A-Za-z][A-Za-z0-9 &/().,'\-]{1,50}?)[\s:|\-]+(?P<obt>\d{1,4}(?:\.\d+)?)\s*(?:/|out of)\s*"
    r"(?P<tot>\d{1,4}(?:\.\d+)?)(?P<rest>.*)$", re.IGNORECASE)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_GRADE_TOKEN = re.compile(r"^[A-Fa-fU][0-9*+\-]?$")


@dataclass
class _ParsedRow:
    subject: str
    obtained: float
    total: float | None
    grade: str
    confidence: str
    source: str


def ocr_available() -> bool:
    """True when pytesseract and the Tesseract binary are both usable."""
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:  # noqa: BLE001 - any failure means OCR is not usable
        return False


def parse_marks_from_text(text: str, default_total: float | None = None) -> tuple[list[_ParsedRow], list[str]]:
    """Parse 'Subject 78/100' and 'Subject 100 78' style lines. Returns (rows, warnings)."""
    rows: list[_ParsedRow] = []
    warnings: list[str] = []
    skipped = 0
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line or len(line) > 120 or not re.search(r"[A-Za-z]", line) or not re.search(r"\d", line):
            continue
        if _IGNORE_LINE.search(line):
            continue
        m = _SLASH_ROW.match(line)
        if m:
            rest = m.group("rest").strip().split(" ")[0] if m.group("rest").strip() else ""
            grade = rest if rest and _GRADE_TOKEN.match(rest) else ""
            rows.append(_ParsedRow(m.group("subject").strip(), float(m.group("obt")), float(m.group("tot")),
                                   grade, "high", line))
            continue
        first_digit = re.search(r"\d", line)
        subject = line[: first_digit.start()].strip(" :|-")
        nums = [float(n) for n in _NUMBER.findall(line[first_digit.start():])]
        if len(subject) >= 2 and len(nums) == 2:
            rows.append(_ParsedRow(subject, min(nums), max(nums), "", "medium", line))
            warnings.append(f"'{subject}': two numbers found without a '/'; assumed the smaller is obtained marks.")
        elif len(subject) >= 2 and len(nums) == 1 and default_total:
            rows.append(_ParsedRow(subject, nums[0], float(default_total), "", "medium", line))
            warnings.append(f"'{subject}': only one number found; used your default total of {default_total:g}.")
        else:
            skipped += 1
    if skipped:
        warnings.append(f"{skipped} line(s) with numbers were skipped because they were ambiguous.")
    return rows, warnings


def _read_csv(content: bytes) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(content), sep=None, engine="python", encoding=encoding)
        except UnicodeDecodeError:
            continue
        except (pd.errors.ParserError, pd.errors.EmptyDataError, csv.Error, ValueError) as exc:
            raise ExtractionError(f"The CSV file could not be parsed: {exc}") from exc
    raise ExtractionError("The CSV file uses an unsupported text encoding.")


def _read_excel(content: bytes) -> pd.DataFrame:
    try:
        sheets = pd.read_excel(io.BytesIO(content), sheet_name=None, engine="openpyxl")
    except Exception as exc:
        raise ExtractionError(f"The Excel file could not be read: {exc}") from exc
    frames = []
    for name, frame in sheets.items():
        if frame.empty:
            continue
        has_exam = any(str(c).strip().lower() in {"exam", "examination", "exam_name", "test", "term"}
                       for c in frame.columns)
        if len(sheets) > 1 and not has_exam:
            frame = frame.assign(exam=str(name))
        frames.append(frame)
    if not frames:
        raise ExtractionError("The Excel file has no data.")
    return pd.concat(frames, ignore_index=True)


def _pdf_page_lines(page) -> list[str]:
    """Rebuild table rows from word positions so each marksheet row becomes one text line."""
    words = sorted(page.get_text("words"), key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    lines: list[list[tuple[float, str]]] = []
    last_y: float | None = None
    for x0, y0, _x1, y1, word, *_ in words:
        y = (y0 + y1) / 2
        if last_y is None or abs(y - last_y) > 3:
            lines.append([])
            last_y = y
        lines[-1].append((x0, word))
    return [" ".join(w for _, w in sorted(line)) for line in lines]


def _ocr_image(image) -> str:
    import pytesseract

    return pytesseract.image_to_string(image)


def _text_from_pdf(content: bytes) -> tuple[str, bool]:
    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz  # type: ignore[no-redef]
    except ImportError as exc:
        raise ExtractionError("PDF support needs PyMuPDF. Install it with: pip install PyMuPDF") from exc
    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        raise ExtractionError(f"The PDF could not be opened (it may be corrupted): {exc}") from exc
    if doc.page_count == 0:
        raise ExtractionError("The PDF has no pages.")
    chunks: list[str] = []
    used_ocr = False
    for index, page in enumerate(doc):
        if index >= MAX_PDF_PAGES:
            break
        lines = _pdf_page_lines(page)
        if sum(len(line) for line in lines) >= 20:
            chunks.append("\n".join(lines))
        elif ocr_available():
            from PIL import Image

            pix = page.get_pixmap(dpi=200)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            chunks.append(_ocr_image(image))
            used_ocr = True
    text = "\n".join(chunks)
    if not text.strip():
        raise ExtractionError(
            "No text found in the PDF. It looks like a scan and OCR is not available "
            "(install Tesseract and pytesseract), so please enter the marks manually.")
    return text, used_ocr


def _text_from_image(content: bytes) -> str:
    from PIL import Image, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(content))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ExtractionError("The image could not be read (it may be corrupted).") from exc
    if not ocr_available():
        raise ExtractionError(
            "Reading images needs OCR, which is not available on this server (install Tesseract and "
            "pytesseract). Please enter the marks manually or upload a CSV/Excel file.")
    return _ocr_image(image.convert("RGB"))


def extract_marksheet(
    content: bytes, filename: str, file_type: str, default_total: float | None = None,
    default_exam: str | None = None,
) -> ExtractedMarksheet:
    """Extract a reviewable table from an uploaded file. Raises ExtractionError when nothing usable is found."""
    warnings: list[str] = []
    ocr_used = False
    parsed: list[_ParsedRow] = []

    if file_type in ("csv", "xlsx"):
        table = _read_csv(content) if file_type == "csv" else _read_excel(content)
    else:
        if file_type == "pdf":
            text, ocr_used = _text_from_pdf(content)
        else:
            text, ocr_used = _text_from_image(content), True
        parsed, text_warnings = parse_marks_from_text(text, default_total)
        warnings.extend(text_warnings)
        if not parsed:
            raise ExtractionError(
                "No subject/marks rows were recognised. Marksheet layouts vary, so please enter the marks "
                "manually or upload a CSV/Excel file with subject, obtained and total columns.")
        table = pd.DataFrame([{"subject": p.subject, "obtained": p.obtained,
                               "total": p.total if p.total is not None else None} for p in parsed])
        if ocr_used:
            warnings.append("Text was read with OCR, which can misread digits. Check every value carefully.")

    cleaned, report = clean_results(table, default_total=default_total, default_exam=default_exam or DEFAULT_EXAM_NAME)
    if cleaned.empty:
        raise ExtractionError("; ".join(i.message for i in report.errors) or "No usable rows were found.")

    rows: list[ExtractedRow] = []
    for rec in cleaned.to_dict(orient="records"):
        idx = int(rec["_row"]) - 1
        meta = parsed[idx] if parsed and idx < len(parsed) else None
        rows.append(ExtractedRow(
            row=int(rec["_row"]), exam=str(rec["exam"]), exam_type=str(rec["exam_type"]), subject=str(rec["subject"]),
            obtained=None if pd.isna(rec["obtained"]) else float(rec["obtained"]),
            total=None if pd.isna(rec["total"]) else float(rec["total"]),
            grade=str(rec["grade"] or "") or (meta.grade if meta else ""),
            confidence=meta.confidence if meta else "high", source_text=meta.source if meta else None))
    return ExtractedMarksheet(
        filename=filename, file_type=file_type, rows=rows, warnings=warnings, ocr_used=ocr_used,
        issues=[DataIssueModel(**i) for i in report.to_dicts()])

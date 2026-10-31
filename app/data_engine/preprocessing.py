"""Data cleaning and validation for marksheet tables.

Canonical long format: one row per (exam, subject) with columns
`exam, exam_type, subject, obtained, total, grade, exam_order` (+ `_row`, the 1-based input row).
Nothing is ever invented: unreadable or missing values become *errors* for the user to fix.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

CANONICAL_COLUMNS = ["_row", "exam", "exam_type", "subject", "obtained", "total", "grade", "exam_order"]

COLUMN_ALIASES: dict[str, list[str]] = {
    "subject": ["subject", "subjects", "subject_name", "course", "paper", "name_of_subject"],
    "obtained": ["obtained", "obtained_marks", "marks_obtained", "marks", "score", "mark", "scored", "marks_scored"],
    "total": ["total", "total_marks", "max", "max_marks", "maximum", "maximum_marks", "out_of", "full_marks",
              "possible", "total_possible"],
    "exam": ["exam", "examination", "exam_name", "test", "term", "assessment", "exam_title"],
    "exam_type": ["exam_type", "type"],
    "grade": ["grade", "grades", "letter_grade"],
    "exam_date": ["date", "exam_date"],
}

SUBJECT_ALIASES: dict[str, str] = {
    "math": "Mathematics", "maths": "Mathematics", "mathematics": "Mathematics",
    "add maths": "Additional Mathematics", "additional maths": "Additional Mathematics",
    "additional mathematics": "Additional Mathematics",
    "phy": "Physics", "physics": "Physics", "chem": "Chemistry", "chemistry": "Chemistry",
    "bio": "Biology", "biology": "Biology",
    "eng": "English", "english": "English", "english language": "English", "english lang": "English",
    "english lit": "English Literature", "english literature": "English Literature",
    "cs": "Computer Science", "comp sci": "Computer Science", "comp science": "Computer Science",
    "computer": "Computer Science", "computer science": "Computer Science",
    "isl": "Islamiyat", "islamiat": "Islamiyat", "islamiyat": "Islamiyat",
    "pak studies": "Pakistan Studies", "pakistan studies": "Pakistan Studies",
    "econ": "Economics", "eco": "Economics", "economics": "Economics",
    "urdu": "Urdu", "sindhi": "Sindhi", "stats": "Statistics", "statistics": "Statistics",
}

SUMMARY_ROW_NAMES = {"total", "grand total", "aggregate", "percentage", "overall", "result", "gpa", "cgpa"}
DEFAULT_EXAM_NAME = "Current Examination"


@dataclass
class DataIssue:
    """One validation finding (row is the 1-based input row, or None for table-level issues)."""

    row: int | None
    field: str
    message: str
    severity: str = "error"  # "error" blocks analysis; "warning" does not

    def to_dict(self) -> dict[str, Any]:
        return {"row": self.row, "field": self.field, "message": self.message, "severity": self.severity}


@dataclass
class ValidationReport:
    issues: list[DataIssue] = field(default_factory=list)

    def add(self, row: int | None, field_name: str, message: str, severity: str = "error") -> None:
        self.issues.append(DataIssue(row, field_name, message, severity))

    @property
    def errors(self) -> list[DataIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[DataIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def is_valid(self) -> bool:
        return not self.errors

    def to_dicts(self) -> list[dict[str, Any]]:
        return [i.to_dict() for i in self.issues]


def normalize_subject_name(name: Any) -> str:
    """Canonical subject name: trims, collapses spaces, resolves common abbreviations."""
    if name is None or (isinstance(name, float) and np.isnan(name)):
        return ""
    text = re.sub(r"\s+", " ", str(name)).strip()
    if not text:
        return ""
    key = re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()
    if key in SUBJECT_ALIASES:
        return SUBJECT_ALIASES[key]
    return " ".join(w if (w.isupper() and len(w) <= 4) else w.capitalize() for w in text.split(" "))


def subject_key(name: Any) -> str:
    """Case-insensitive comparison key for subject names."""
    return normalize_subject_name(name).lower()


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename recognised columns to canonical names; unrecognised columns are dropped."""
    lookup: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            lookup.setdefault(alias, canonical)
    renamed: dict[str, str] = {}
    used: set[str] = set()
    for col in df.columns:
        key = re.sub(r"[^a-z0-9]+", "_", str(col).strip().lower()).strip("_")
        canonical = lookup.get(key)
        if canonical and canonical not in used:
            renamed[col] = canonical
            used.add(canonical)
    return df[list(renamed)].rename(columns=renamed)


def detect_missing(df: pd.DataFrame) -> dict[str, Any]:
    """Count missing/blank values per column and list the rows affected."""
    blank = df.isna() | (df.astype(str).apply(lambda s: s.str.strip()) == "")
    return {
        "per_column": {c: int(blank[c].sum()) for c in df.columns},
        "rows_with_missing": [int(i) + 1 for i in df.index[blank.any(axis=1)]],
    }


def detect_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Rows repeating an (exam, subject) pair already seen earlier."""
    if df.empty or not {"exam", "subject"} <= set(df.columns):
        return df.iloc[0:0]
    keys = df["exam"].astype(str).str.lower() + "||" + df["subject"].astype(str).str.lower()
    has_subject = df["subject"].astype(str).str.strip() != ""
    return df[keys.duplicated(keep="first") & has_subject]


def _is_blank(series: pd.Series) -> pd.Series:
    return series.isna() | (series.astype(str).str.strip() == "")


def assign_exam_order(df: pd.DataFrame, dates: pd.Series | None = None) -> pd.Series:
    """Chronological index per exam: by date when every exam has one, else first-appearance order."""
    exams = list(dict.fromkeys(df["exam"]))
    if dates is not None:
        parsed = pd.to_datetime(dates, errors="coerce")
        per_exam = parsed.groupby(df["exam"]).min()
        if len(per_exam) and per_exam.notna().all():
            exams = list(per_exam.sort_values(kind="stable").index)
    order = {e: i for i, e in enumerate(exams)}
    return df["exam"].map(order).astype(int)


def clean_results(
    df: pd.DataFrame, default_total: float | None = None, default_exam: str = DEFAULT_EXAM_NAME
) -> tuple[pd.DataFrame, ValidationReport]:
    """Normalise a raw marksheet table and validate it.

    Returns (cleaned_df, report). `cleaned_df` always has `CANONICAL_COLUMNS`; invalid values are
    left as NaN and reported as errors rather than repaired.
    """
    report = ValidationReport()
    raw = df.copy() if df is not None else pd.DataFrame()
    raw.index = range(1, len(raw) + 1)
    table = normalize_columns(raw)

    if len(raw) > 0 and table.shape[1] == 0:
        report.add(None, "table", "No recognised columns. Expected: subject, obtained, total "
                                  "(optional: exam, exam_type, grade).")
        return pd.DataFrame(columns=CANONICAL_COLUMNS), report
    if table.empty or len(raw) == 0:
        report.add(None, "table", "No rows found. Add at least one subject with obtained and total marks.")
        return pd.DataFrame(columns=CANONICAL_COLUMNS), report

    for needed in ("subject", "obtained"):
        if needed not in table.columns:
            report.add(None, needed, f"Missing a '{needed}' column.")
    if "total" not in table.columns:
        if default_total is not None and default_total > 0:
            table["total"] = float(default_total)
            report.add(None, "total", f"No total-marks column; using the default of {default_total:g} you provided.",
                       "warning")
        else:
            report.add(None, "total", "Missing a 'total' (maximum marks) column and no default total was provided.")
    if not report.is_valid:
        return pd.DataFrame(columns=CANONICAL_COLUMNS), report

    for optional, default in (("exam", None), ("exam_type", ""), ("grade", "")):
        if optional not in table.columns:
            table[optional] = default
    table["_row"] = table.index

    # drop completely empty rows
    empty = _is_blank(table["subject"]) & _is_blank(table["obtained"]) & _is_blank(table["total"])
    table = table[~empty].copy()
    if table.empty:
        report.add(None, "table", "All rows are empty.")
        return pd.DataFrame(columns=CANONICAL_COLUMNS), report

    exam_blank = table["exam"].isna() | (table["exam"].astype(str).str.strip() == "")
    table["exam"] = table["exam"].astype(object).where(~exam_blank, default_exam).astype(str).str.strip()
    table["exam_type"] = table["exam_type"].fillna("").astype(str).str.strip()
    table["grade"] = table["grade"].astype(object).fillna("").astype(str).str.strip().replace({"nan": "", "None": ""})
    table["subject"] = table["subject"].apply(normalize_subject_name)

    # ignore summary rows such as "Total"/"Percentage"
    summary = table["subject"].str.lower().isin(SUMMARY_ROW_NAMES)
    for row in table.loc[summary, "_row"]:
        report.add(int(row), "subject", "Summary row ignored (totals are calculated from subject marks).", "warning")
    table = table[~summary].copy()

    if default_total is not None and default_total > 0 and "total" in table.columns:
        missing_total = _is_blank(table["total"]) & ~_is_blank(table["obtained"])
        if missing_total.any() and not any(i.field == "total" and i.severity == "warning" for i in report.issues):
            report.add(None, "total", f"{int(missing_total.sum())} row(s) had no total marks; used the default of "
                                      f"{default_total:g} you provided.", "warning")
        table["total"] = table["total"].astype(object).where(~missing_total, float(default_total))

    for col in ("obtained", "total"):
        original = table[col]
        numeric = pd.to_numeric(original.astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce")
        blank = _is_blank(original)
        for row in table.loc[blank, "_row"]:
            report.add(int(row), col, f"Missing {col} marks.")
        for row in table.loc[~blank & numeric.isna(), "_row"]:
            report.add(int(row), col, f"'{col}' is not a number.")
        table[col] = numeric.astype(float)

    for row in table.loc[_is_blank(table["subject"]), "_row"]:
        report.add(int(row), "subject", "Missing subject name.")
    for row in table.loc[table["obtained"] < 0, "_row"]:
        report.add(int(row), "obtained", "Obtained marks cannot be negative.")
    for row in table.loc[table["total"] <= 0, "_row"]:
        report.add(int(row), "total", "Total marks must be greater than zero.")
    for row in table.loc[table["obtained"] > table["total"], "_row"]:
        report.add(int(row), "obtained", "Obtained marks exceed total marks.")
    for row in detect_duplicates(table)["_row"]:
        report.add(int(row), "subject", "Duplicate subject in the same examination.")

    table = table.reset_index(drop=True)
    dates = None
    if "exam_date" in table.columns:
        dates = table["exam_date"]
    table["exam_order"] = assign_exam_order(table, dates)
    return table[CANONICAL_COLUMNS], report


def validate_results(df: pd.DataFrame) -> ValidationReport:
    """Re-validate an already-canonical table (e.g. loaded from the database)."""
    _, report = clean_results(df)
    return report

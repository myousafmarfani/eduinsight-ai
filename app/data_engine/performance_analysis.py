"""Percentages, grades and overall performance (Pandas/NumPy; no AI-generated numbers)."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.data_engine.board_config import grade_for_percentage
from app.data_engine.statistics import descriptive_statistics


def add_percentage(df: pd.DataFrame) -> pd.DataFrame:
    """Add `percentage` = obtained / total * 100, using each row's own total as the denominator."""
    out = df.copy()
    total = out["total"].astype(float)
    out["percentage"] = np.where(total > 0, out["obtained"].astype(float) / total * 100.0, np.nan)
    return out


def current_exam(df: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    """Return (name, rows) of the most recent examination (highest `exam_order`)."""
    latest = int(df["exam_order"].max())
    subset = df[df["exam_order"] == latest]
    return str(subset["exam"].iloc[0]), subset.reset_index(drop=True)


def subject_percentages(exam_df: pd.DataFrame, board: str | None = None) -> pd.DataFrame:
    """Per-subject marks, percentage and grade (printed grade if given, else computed and flagged)."""
    out = add_percentage(exam_df)
    grades, indicative = [], []
    for pct, printed in zip(out["percentage"], out.get("grade", [""] * len(out))):
        if isinstance(printed, str) and printed.strip():
            grades.append(printed.strip())
            indicative.append(False)
        else:
            label, is_ind = grade_for_percentage(float(pct), board)
            grades.append(label)
            indicative.append(is_ind)
    out["grade"] = grades
    out["grade_is_indicative"] = indicative
    return out[["subject", "obtained", "total", "percentage", "grade", "grade_is_indicative"]].reset_index(drop=True)


def exam_overall_series(df: pd.DataFrame) -> pd.DataFrame:
    """Overall (marks-weighted) percentage for every examination in chronological order."""
    rows = []
    for order, grp in df.groupby("exam_order", sort=True):
        obtained, total = float(grp["obtained"].sum()), float(grp["total"].sum())
        rows.append({
            "exam_order": int(order), "exam": str(grp["exam"].iloc[0]), "obtained": obtained, "total": total,
            "percentage": obtained / total * 100.0 if total > 0 else np.nan, "subject_count": len(grp),
        })
    return pd.DataFrame(rows, columns=["exam_order", "exam", "obtained", "total", "percentage", "subject_count"])


def overall_performance(subjects: pd.DataFrame, exam_name: str, board: str | None = None) -> dict[str, Any]:
    """Overall metrics for one examination.

    `overall_percentage` = total obtained / total possible (weights subjects by their marks);
    `average_subject_percentage` = mean of subject percentages (weights subjects equally).
    """
    total_obtained = float(subjects["obtained"].sum())
    total_possible = float(subjects["total"].sum())
    overall_pct = total_obtained / total_possible * 100.0 if total_possible > 0 else float("nan")
    pcts = subjects["percentage"].astype(float)
    top, bottom = float(pcts.max()), float(pcts.min())
    stats = descriptive_statistics(pcts)
    grade, indicative = grade_for_percentage(overall_pct, board)
    return {
        "exam_name": exam_name,
        "subject_count": len(subjects),
        "total_obtained": round(total_obtained, 2),
        "total_possible": round(total_possible, 2),
        "overall_percentage": round(overall_pct, 2),
        "overall_grade": grade,
        "overall_grade_is_indicative": indicative,
        "average_subject_percentage": stats["mean"],
        "median_percentage": stats["median"],
        "std_dev": stats["std_dev"],
        "highest_subject": str(subjects.loc[pcts.idxmax(), "subject"]),
        "highest_percentage": round(top, 2),
        "highest_subjects_tied": [str(s) for s in subjects.loc[np.isclose(pcts, top), "subject"]],
        "lowest_subject": str(subjects.loc[pcts.idxmin(), "subject"]),
        "lowest_percentage": round(bottom, 2),
        "lowest_subjects_tied": [str(s) for s in subjects.loc[np.isclose(pcts, bottom), "subject"]],
    }

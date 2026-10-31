"""Comparison of examinations and per-subject trends."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.data_engine.performance_analysis import add_percentage, exam_overall_series


def _status(change: float, stable_band: float) -> str:
    if change > stable_band:
        return "improved"
    if change < -stable_band:
        return "declined"
    return "stable"


def subject_history(df: pd.DataFrame, subject: str) -> pd.DataFrame:
    """Chronological rows (exam, percentage) for one subject (case-insensitive match)."""
    rows = add_percentage(df)
    rows = rows[rows["subject"].str.lower() == subject.lower()]
    return rows.sort_values("exam_order")[["exam_order", "exam", "obtained", "total", "percentage"]].reset_index(drop=True)


def compare_examinations(df: pd.DataFrame, stable_band: float = 2.0) -> dict[str, Any]:
    """Previous vs current examination, overall and per subject (changes in percentage points).

    Returns {"available": False, "reason": ...} when fewer than two examinations exist.
    Subjects present in only one of the two examinations are listed separately, not compared.
    """
    series = exam_overall_series(df)
    if len(series) < 2:
        return {"available": False, "reason": "Only one examination is recorded; add a previous examination to compare."}

    cur_order, prev_order = int(series["exam_order"].iloc[-1]), int(series["exam_order"].iloc[-2])
    cur = add_percentage(df[df["exam_order"] == cur_order]).set_index("subject")
    prev = add_percentage(df[df["exam_order"] == prev_order]).set_index("subject")
    overall_change = float(series["percentage"].iloc[-1] - series["percentage"].iloc[-2])

    changes = []
    for subject in cur.index:
        if subject in prev.index:
            c, p = float(cur.loc[subject, "percentage"]), float(prev.loc[subject, "percentage"])
            changes.append({
                "subject": subject, "previous_percentage": round(p, 2), "current_percentage": round(c, 2),
                "change_points": round(c - p, 2), "status": _status(c - p, stable_band),
            })
    changes.sort(key=lambda r: r["change_points"])
    return {
        "available": True,
        "previous_exam": str(series["exam"].iloc[-2]),
        "current_exam": str(series["exam"].iloc[-1]),
        "previous_overall_percentage": round(float(series["percentage"].iloc[-2]), 2),
        "current_overall_percentage": round(float(series["percentage"].iloc[-1]), 2),
        "overall_change_points": round(overall_change, 2),
        "overall_status": _status(overall_change, stable_band),
        "stable_band_points": stable_band,
        "subject_changes": changes,
        "improved_subjects": [c["subject"] for c in changes if c["status"] == "improved"],
        "declined_subjects": [c["subject"] for c in changes if c["status"] == "declined"],
        "new_subjects": [s for s in cur.index if s not in prev.index],
        "dropped_subjects": [s for s in prev.index if s not in cur.index],
        "exam_count": len(series),
    }


def subject_trends(df: pd.DataFrame, min_points: int = 3, trend_band: float = 1.0) -> dict[str, dict[str, Any]]:
    """Linear trend (percentage points per examination) for subjects with at least `min_points` results."""
    data = add_percentage(df)
    trends: dict[str, dict[str, Any]] = {}
    for subject, grp in data.groupby("subject"):
        grp = grp.sort_values("exam_order")
        if len(grp) < min_points:
            continue
        slope = float(np.polyfit(np.arange(len(grp)), grp["percentage"].to_numpy(dtype=float), 1)[0])
        trends[str(subject)] = {
            "slope_points_per_exam": round(slope, 2),
            "points": len(grp),
            "direction": "improving" if slope > trend_band else "declining" if slope < -trend_band else "flat",
            "percentages": [round(float(v), 2) for v in grp["percentage"]],
        }
    return trends


def overall_trend(df: pd.DataFrame, min_points: int = 3, trend_band: float = 1.0) -> dict[str, Any]:
    """Trend of the overall percentage across examinations."""
    series = exam_overall_series(df)
    if len(series) < min_points:
        return {"available": False, "reason": f"At least {min_points} examinations are needed to describe a trend."}
    slope = float(np.polyfit(np.arange(len(series)), series["percentage"].to_numpy(dtype=float), 1)[0])
    return {
        "available": True,
        "slope_points_per_exam": round(slope, 2),
        "direction": "improving" if slope > trend_band else "declining" if slope < -trend_band else "flat",
        "series": [{"exam": r.exam, "percentage": round(float(r.percentage), 2)} for r in series.itertuples()],
    }

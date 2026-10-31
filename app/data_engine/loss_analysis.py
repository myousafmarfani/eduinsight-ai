"""Actionable marks-lost and planning calculations."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.data_engine.board_config import grade_for_percentage
from app.data_engine.performance_analysis import add_percentage


def _no(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def _num(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else round(float(value), 4)
    return value


def _latest(df: pd.DataFrame) -> pd.DataFrame:
    return df[df.exam_order == df.exam_order.max()].copy()


def marks_lost_pareto(df: pd.DataFrame) -> dict[str, Any]:
    current = _latest(df)
    if current.empty:
        return _no("No examination data is available.")
    total_possible = float(current["total"].sum())
    rows = current.assign(marks_lost=current["total"].astype(float) - current["obtained"].astype(float))
    rows = rows.groupby("subject", as_index=False)["marks_lost"].sum().sort_values("marks_lost", ascending=False)
    total_lost = float(rows["marks_lost"].sum())
    rows["percentage_points_lost"] = rows["marks_lost"] / total_possible * 100 if total_possible else 0
    rows["cumulative_share"] = rows["marks_lost"].cumsum() / total_lost * 100 if total_lost else 0
    cutoff = int((rows["cumulative_share"] <= 80).sum())
    if len(rows) and cutoff == 0:
        cutoff = 1
    records = [{k: _num(v) for k, v in row.items()} for row in rows.to_dict("records")]
    return {"available": True, "total_marks_lost": _num(total_lost), "subjects": records,
            "subjects_for_about_80_percent": cutoff}


def target_planner(df: pd.DataFrame, target_percentage: float) -> dict[str, Any]:
    if not 0 <= float(target_percentage) <= 100:
        raise ValueError("target_percentage must be between 0 and 100.")
    current = _latest(df)
    obtained, total = float(current.obtained.sum()), float(current.total.sum())
    current_pct = obtained / total * 100 if total else 0
    target_marks = total * float(target_percentage) / 100
    needed = max(0.0, target_marks - obtained)
    rows = []
    for row in current.itertuples():
        other_obtained = obtained - float(row.obtained)
        required = (target_marks - other_obtained) / float(row.total) * 100
        rows.append({"subject": str(row.subject), "required_percentage": _num(required),
                     "feasible": bool(required <= 100), "already_sufficient": bool(required <= float(row.obtained) / float(row.total) * 100)})
    uniform = max(0.0, float(target_percentage) - current_pct)
    return {"available": True, "current_percentage": _num(current_pct), "target_percentage": float(target_percentage),
            "marks_still_needed": _num(needed), "minimum_uniform_improvement_points": _num(uniform),
            "per_subject": rows}


def what_if(df: pd.DataFrame, changes: dict[str, float], board: str | None = None) -> dict[str, Any]:
    current = add_percentage(_latest(df))
    names = {str(s).lower(): str(s) for s in current.subject}
    unknown = [s for s in changes if s.lower() not in names]
    if unknown:
        raise ValueError(f"Unknown subject(s): {', '.join(unknown)}")
    invalid = [s for s, value in changes.items() if not 0 <= float(value) <= 100]
    if invalid:
        raise ValueError("What-if percentages must be between 0 and 100.")
    updated = current.percentage.to_numpy(float).copy()
    for subject, value in changes.items():
        updated[current.subject.str.lower().to_numpy() == subject.lower()] = float(value)
    weighted = float(np.average(updated, weights=current.total.astype(float)))
    grade, indicative = grade_for_percentage(weighted, board)
    old = float(np.average(current.percentage, weights=current.total.astype(float)))
    return {"available": True, "original_overall": _num(old), "new_overall": _num(weighted),
            "change_points": _num(weighted - old), "grade": grade, "grade_is_indicative": indicative,
            "changes": {names[k.lower()]: float(v) for k, v in changes.items()}}


def weighted_score(df: pd.DataFrame, weights: dict[str, float]) -> dict[str, Any]:
    current = add_percentage(_latest(df))
    names = {str(s).lower(): str(s) for s in current.subject}
    unknown = [s for s in weights if s.lower() not in names]
    if unknown:
        raise ValueError(f"Unknown subject(s): {', '.join(unknown)}")
    if any(float(v) < 0 for v in weights.values()):
        raise ValueError("Weights must be non-negative.")
    supplied = current.subject.map(lambda s: float(weights.get(str(s), weights.get(str(s).lower(), 0))))
    if supplied.sum() <= 0:
        raise ValueError("At least one supplied weight must be positive.")
    score = float(np.average(current.percentage, weights=supplied))
    unweighted = float(current.percentage.mean())
    return {"available": True, "weighted_percentage": _num(score), "unweighted_percentage": _num(unweighted),
            "difference_points": _num(score - unweighted),
            "normalized_weights": {str(subject): _num(weight / supplied.sum()) for subject, weight in zip(current.subject, supplied)}}

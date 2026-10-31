"""Configurable weakness / strength detection.

Every flag carries the criterion, the observed value, the threshold and a plain-language
explanation, so no subject is labelled weak by an unexplained cut-off.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from app.data_engine.comparison import subject_history


@dataclass(frozen=True)
class WeaknessConfig:
    """Thresholds (percentage points unless stated otherwise)."""

    weak_threshold: float = 50.0          # absolute: below this percentage
    strong_threshold: float = 75.0        # absolute: at or above this percentage
    relative_gap: float = 10.0            # below/above the student's own average by this much
    decline_points: float = 5.0           # drop versus the previous result
    trend_slope: float = -2.0             # points per examination, needs >= 3 results
    inconsistency_std: float = 10.0       # std-dev across >= 3 results
    target_gap: float = 10.0              # shortfall versus the student's target
    min_subjects_for_relative: int = 3    # personal-average comparison needs enough subjects
    high_score: int = 5
    medium_score: int = 3


# scoring weights for each criterion
_WEIGHTS = {"below_threshold": 3, "below_pass_mark": 2, "below_personal_average": 2, "declining": 2,
            "inconsistent": 1, "short_of_target": 1}


def _reason(criterion: str, observed: float, threshold: float, explanation: str) -> dict[str, Any]:
    return {"criterion": criterion, "observed": round(float(observed), 2), "threshold": round(float(threshold), 2),
            "explanation": explanation}


def _priority(score: int, cfg: WeaknessConfig) -> str:
    return "high" if score >= cfg.high_score else "medium" if score >= cfg.medium_score else "low"


def detect_weak_subjects(
    subjects: pd.DataFrame,
    history: pd.DataFrame | None,
    cfg: WeaknessConfig,
    pass_mark: float | None = None,
    target: float | None = None,
    reported_difficult: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Flag subjects of the current examination that meet at least one weakness criterion.

    `reported_difficult` (lower-case names the student *said* are hard) is reported alongside the
    result but never counted as evidence, because it is not calculated from marks.
    """
    reported_difficult = reported_difficult or set()
    avg = float(subjects["percentage"].mean())
    weak: list[dict[str, Any]] = []

    for row in subjects.itertuples():
        pct = float(row.percentage)
        reasons: list[dict[str, Any]] = []
        score = 0

        if pct < cfg.weak_threshold:
            reasons.append(_reason("below_threshold", pct, cfg.weak_threshold,
                                   f"{pct:.1f}% is below the {cfg.weak_threshold:g}% weak-subject threshold."))
            score += _WEIGHTS["below_threshold"]
        if pass_mark is not None and pct < pass_mark:
            reasons.append(_reason("below_pass_mark", pct, pass_mark,
                                   f"{pct:.1f}% is below this board's {pass_mark:g}% pass mark."))
            score += _WEIGHTS["below_pass_mark"]
        if len(subjects) >= cfg.min_subjects_for_relative and pct < avg - cfg.relative_gap:
            reasons.append(_reason("below_personal_average", pct, avg - cfg.relative_gap,
                                   f"{pct:.1f}% is {avg - pct:.1f} points below your own average of {avg:.1f}%."))
            score += _WEIGHTS["below_personal_average"]

        gap_to_target = None
        if target is not None:
            gap_to_target = round(target - pct, 2)
            if gap_to_target >= cfg.target_gap:
                reasons.append(_reason("short_of_target", pct, target - cfg.target_gap,
                                       f"{pct:.1f}% is {gap_to_target:.1f} points short of your {target:g}% target."))
                score += _WEIGHTS["short_of_target"]

        change = None
        slope = None
        if history is not None:
            hist = subject_history(history, row.subject)
            if len(hist) >= 2:
                change = float(hist["percentage"].iloc[-1] - hist["percentage"].iloc[-2])
                if change <= -cfg.decline_points:
                    reasons.append(_reason("declining", change, -cfg.decline_points,
                                           f"Dropped {abs(change):.1f} points since '{hist['exam'].iloc[-2]}'."))
                    score += _WEIGHTS["declining"]
            if len(hist) >= 3:
                values = hist["percentage"].to_numpy(dtype=float)
                slope = float(np.polyfit(np.arange(len(values)), values, 1)[0])
                std = float(values.std(ddof=1))
                if slope <= cfg.trend_slope and not any(r["criterion"] == "declining" for r in reasons):
                    reasons.append(_reason("declining", slope, cfg.trend_slope,
                                           f"Trend over {len(values)} examinations is {slope:.1f} points per exam."))
                    score += _WEIGHTS["declining"]
                if std >= cfg.inconsistency_std:
                    reasons.append(_reason("inconsistent", std, cfg.inconsistency_std,
                                           f"Results vary widely across {len(values)} examinations (std-dev {std:.1f})."))
                    score += _WEIGHTS["inconsistent"]

        if not reasons:
            continue
        weak.append({
            "subject": row.subject,
            "percentage": round(pct, 2),
            "obtained": float(row.obtained),
            "total": float(row.total),
            "priority": _priority(score, cfg),
            "score": score,
            "reasons": reasons,
            "gap_to_target": gap_to_target,
            "change_since_previous": None if change is None else round(change, 2),
            "trend_slope": None if slope is None else round(slope, 2),
            "student_reported_difficulty": row.subject.lower() in reported_difficult,
        })

    weak.sort(key=lambda w: (-w["score"], w["percentage"]))
    return weak


def detect_strong_subjects(subjects: pd.DataFrame, cfg: WeaknessConfig) -> list[dict[str, Any]]:
    """Subjects at/above the strong threshold, or clearly above the student's own average."""
    avg = float(subjects["percentage"].mean())
    strong = []
    for row in subjects.itertuples():
        pct = float(row.percentage)
        reasons = []
        if pct >= cfg.strong_threshold:
            reasons.append(_reason("above_threshold", pct, cfg.strong_threshold,
                                   f"{pct:.1f}% meets the {cfg.strong_threshold:g}% strong-subject threshold."))
        if len(subjects) >= cfg.min_subjects_for_relative and pct > avg + cfg.relative_gap:
            reasons.append(_reason("above_personal_average", pct, avg + cfg.relative_gap,
                                   f"{pct:.1f}% is {pct - avg:.1f} points above your own average of {avg:.1f}%."))
        if reasons:
            strong.append({"subject": row.subject, "percentage": round(pct, 2), "obtained": float(row.obtained),
                           "total": float(row.total), "reasons": reasons})
    strong.sort(key=lambda s: -s["percentage"])
    return strong

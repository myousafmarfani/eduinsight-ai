"""Pure topic-mastery and adaptive-practice calculations.

Recency weighting uses session weights 1.0 for the newest session, 0.8 for
the previous, then 0.8**age for older sessions. Question-level flags and
unfinished sessions must be excluded by the service before calling here.
"""
from __future__ import annotations

from typing import Any

import numpy as np


def adaptive_difficulty_mix(recent_accuracy: float | None, n_questions: int) -> dict[str, int]:
    """Choose deterministic easy/medium/hard counts from recent accuracy."""
    if n_questions not in (5, 10, 15):
        raise ValueError("n_questions must be 5, 10, or 15")
    if recent_accuracy is None or recent_accuracy < 50:
        ratios = (0.6, 0.3, 0.1)
    elif recent_accuracy <= 75:
        ratios = (0.3, 0.5, 0.2)
    else:
        ratios = (0.1, 0.3, 0.6)
    counts = [int(n_questions * ratio) for ratio in ratios]
    counts[1] += n_questions - sum(counts)
    return dict(zip(("easy", "medium", "hard"), counts))


def _not_enough(attempts: int, sessions: int, min_questions: int, min_sessions: int) -> str:
    missing_questions = max(0, min_questions - attempts)
    missing_sessions = max(0, min_sessions - sessions)
    return (f"Not enough data yet: {attempts} answered questions across {sessions} quiz session(s); "
            f"need {missing_questions} more question(s) and {missing_sessions} more session(s) "
            "for a mastery verdict.")


def calculate_mastery(
    records: list[dict[str, Any]], *, min_questions: int = 8, min_sessions: int = 2,
) -> dict[str, Any]:
    """Calculate one topic's mastery from completed, unflagged answer records."""
    sessions: dict[str, list[int]] = {}
    for record in records:
        if record.get("flagged") or not record.get("answered", True):
            continue
        sessions.setdefault(str(record["session_id"]), []).append(1 if record["is_correct"] else 0)
    ordered = list(sessions.values())
    attempts = sum(len(values) for values in ordered)
    session_count = len(ordered)
    correct = sum(sum(values) for values in ordered)
    accuracy = round(correct / attempts * 100, 2) if attempts else 0.0
    weighted_total = weighted_correct = 0.0
    for age, values in enumerate(reversed(ordered)):
        weight = 0.8 ** age
        weighted_total += len(values) * weight
        weighted_correct += sum(values) * weight
    recency_accuracy = round(weighted_correct / weighted_total * 100, 2) if weighted_total else 0.0
    session_accuracy = [sum(values) / len(values) * 100 for values in ordered if values]
    trend: float | None = None
    if len(session_accuracy) >= 3:
        trend = round(float(np.polyfit(np.arange(len(session_accuracy)), session_accuracy, 1)[0]), 2)
    enough = attempts >= min_questions and session_count >= min_sessions
    level = None if not enough else ("low" if recency_accuracy < 50 else "developing" if recency_accuracy <= 75 else "strong")
    return {
        "attempts": attempts, "correct": correct, "sessions": session_count,
        "accuracy": accuracy, "recency_weighted_accuracy": recency_accuracy,
        "trend": trend, "trend_label": ("not enough data" if len(session_accuracy) < 3
                                         else "improving" if trend > 1 else "declining" if trend < -1 else "stable"),
        "mastery_level": level,
        "confidence_note": _not_enough(attempts, session_count, min_questions, min_sessions)
        if not enough else ("Confidence is based on the minimum evidence threshold." if attempts < 20
                            else "Confidence is supported by a larger answer sample."),
        "evidence": (f"Answered {correct} of {attempts} questions correctly ({accuracy:.0f}%) "
                     f"over {session_count} quiz session(s)."),
        "enough_data": enough,
    }


def calculate_mastery_table(
    records: list[dict[str, Any]], *, min_questions: int = 8, min_sessions: int = 2,
) -> list[dict[str, Any]]:
    """Group records by subject/topic and calculate JSON-safe mastery rows."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        groups.setdefault((str(record["subject"]), str(record["topic"])), []).append(record)
    return [
        {"subject": subject, "topic": topic, **calculate_mastery(values, min_questions=min_questions,
                                                                  min_sessions=min_sessions)}
        for (subject, topic), values in sorted(groups.items())
    ]

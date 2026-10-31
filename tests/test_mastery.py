from __future__ import annotations

from app.data_engine.mastery import adaptive_difficulty_mix, calculate_mastery


def _records(values: list[list[bool]]) -> list[dict]:
    return [
        {"session_id": f"s{session}", "subject": "Mathematics", "topic": "Algebra",
         "is_correct": value, "flagged": False}
        for session, answers in enumerate(values, 1)
        for value in answers
    ]


def test_mastery_minimum_sample_and_evidence():
    result = calculate_mastery(_records([[True, False, True]]))
    assert result["attempts"] == 3 and not result["enough_data"]
    assert result["mastery_level"] is None and "need 5 more" in result["confidence_note"]


def test_mastery_recency_weighting_and_three_session_trend():
    result = calculate_mastery(_records([[False, False, False], [True, True, True], [True, True, True]]))
    assert result["enough_data"] and result["recency_weighted_accuracy"] > result["accuracy"]
    assert result["trend"] > 0 and result["trend_label"] == "improving"


def test_two_sessions_have_no_trend():
    result = calculate_mastery(_records([[True] * 4, [False] * 4]))
    assert result["enough_data"] and result["trend"] is None
    assert result["trend_label"] == "not enough data"


def test_flagged_questions_are_excluded_by_mastery_input():
    records = _records([[True] * 8, [False] * 8])
    records[-1]["flagged"] = True
    result = calculate_mastery(records)
    assert result["attempts"] == 15


def test_adaptive_difficulty_thresholds():
    assert adaptive_difficulty_mix(40, 10) == {"easy": 6, "medium": 3, "hard": 1}
    assert adaptive_difficulty_mix(60, 10) == {"easy": 3, "medium": 5, "hard": 2}
    assert adaptive_difficulty_mix(80, 10) == {"easy": 1, "medium": 3, "hard": 6}

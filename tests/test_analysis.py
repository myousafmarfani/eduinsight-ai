"""Data engine tests: no LLM, API key or web framework needed."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from app.core.exceptions import DataValidationError
from app.data_engine import comparison as cmp
from app.data_engine.analyzer import StudentAnalyzer, SubjectNotFoundError
from app.data_engine.board_config import get_board, grade_for_percentage
from app.data_engine.performance_analysis import (
    add_percentage,
    overall_performance,
    subject_percentages,
)
from app.data_engine.preprocessing import clean_results, normalize_subject_name
from app.data_engine.statistics import descriptive_statistics, performance_distribution
from app.data_engine.weakness_detection import WeaknessConfig, detect_weak_subjects


def table(rows, **kw):
    return pd.DataFrame(rows, columns=["exam", "subject", "obtained", "total"])


# ---- preprocessing --------------------------------------------------------------------------------
def test_clean_valid_sample(sample_raw):
    cleaned, report = clean_results(sample_raw)
    assert report.is_valid and len(cleaned) == 21
    assert cleaned["exam_order"].tolist()[:1] == [0] and cleaned["exam_order"].max() == 2


def test_subject_normalization():
    assert normalize_subject_name("  maths ") == "Mathematics"
    assert normalize_subject_name("COMP  sci") == "Computer Science"
    assert normalize_subject_name("art and design") == "Art And Design"


def test_obtained_exceeds_total_is_error():
    _, report = clean_results(table([("E1", "Math", 120, 100)]))
    assert not report.is_valid
    assert any("exceed" in i.message for i in report.errors)


def test_missing_and_non_numeric_marks():
    df = pd.DataFrame({"subject": ["Math", "Physics", ""], "obtained": [None, "abc", 50], "total": [100, 100, 100]})
    _, report = clean_results(df)
    messages = " ".join(i.message for i in report.errors)
    assert "Missing obtained" in messages and "not a number" in messages and "Missing subject" in messages


def test_duplicate_subject_same_exam():
    _, report = clean_results(table([("E1", "Math", 50, 100), ("E1", "maths", 60, 100)]))
    assert any("Duplicate" in i.message for i in report.errors)


def test_same_subject_different_exams_is_fine():
    _, report = clean_results(table([("E1", "Math", 50, 100), ("E2", "Math", 60, 100)]))
    assert report.is_valid


def test_empty_table():
    _, report = clean_results(pd.DataFrame())
    assert not report.is_valid


def test_missing_total_column_needs_default():
    df = pd.DataFrame({"subject": ["Math"], "obtained": [50]})
    _, report = clean_results(df)
    assert not report.is_valid
    cleaned, report = clean_results(df, default_total=100)
    assert report.is_valid and cleaned["total"].iloc[0] == 100
    assert report.warnings  # the assumption is disclosed, never silent


def test_summary_rows_ignored_with_warning():
    cleaned, report = clean_results(table([("E1", "Math", 50, 100), ("E1", "Total", 50, 100)]))
    assert len(cleaned) == 1 and report.warnings


def test_zero_total_and_negative_marks():
    _, report = clean_results(table([("E1", "Math", -1, 100), ("E1", "Physics", 5, 0)]))
    assert len(report.errors) >= 2


def test_exam_order_by_date():
    df = pd.DataFrame({"exam": ["B", "A"], "subject": ["Math", "Math"], "obtained": [50, 60], "total": [100, 100],
                       "exam_date": ["2026-05-01", "2025-05-01"]})
    cleaned, _ = clean_results(df)
    assert cleaned.set_index("exam")["exam_order"].to_dict() == {"A": 0, "B": 1}


# ---- percentages ----------------------------------------------------------------------------------
def test_percentage_uses_each_rows_denominator():
    df = pd.DataFrame({"obtained": [45, 18], "total": [75, 20]})
    assert add_percentage(df)["percentage"].round(2).tolist() == [60.0, 90.0]


def test_overall_is_weighted_average_is_not():
    cleaned, _ = clean_results(table([("E1", "Math", 45, 75), ("E1", "Art", 18, 20)]))
    subjects = subject_percentages(cleaned, "FBISE")
    overall = overall_performance(subjects, "E1", "FBISE")
    assert overall["overall_percentage"] == pytest.approx(63 / 95 * 100, abs=0.01)
    assert overall["average_subject_percentage"] == pytest.approx(75.0)
    assert overall["total_possible"] == 95


def test_printed_grade_beats_computed_grade():
    df = pd.DataFrame({"exam": ["E1"], "subject": ["Math"], "obtained": [95], "total": [100], "grade": ["A-One"]})
    cleaned, _ = clean_results(df)
    out = subject_percentages(cleaned, "CAMBRIDGE")
    assert out["grade"].iloc[0] == "A-One" and not out["grade_is_indicative"].iloc[0]


def test_board_grades_differ_and_flag_indicative():
    assert grade_for_percentage(85, "PUNJAB") == ("A1", False)
    assert grade_for_percentage(85, "CAMBRIDGE") == ("A", True)
    assert get_board("not a board").key == "OTHER"
    assert get_board("akuEB").key == "AKU-EB"


# ---- statistics -----------------------------------------------------------------------------------
def test_statistics_and_distribution():
    stats = descriptive_statistics([40, 60, 80])
    assert stats["mean"] == 60 and stats["median"] == 60 and stats["std_dev"] == 20.0
    dist = performance_distribution([39, 40, 100, 100])
    assert dist[0]["count"] == 1 and dist[1]["count"] == 1 and dist[-1]["count"] == 2
    assert descriptive_statistics([])["count"] == 0
    assert descriptive_statistics([50])["std_dev"] == 0.0


# ---- weakness detection ---------------------------------------------------------------------------
def test_weak_subject_has_explained_reasons(sample_clean, profile):
    analyzer = StudentAnalyzer(sample_clean, profile)
    weak = analyzer.identify_weak_subjects()
    maths = next(w for w in weak["weak_subjects"] if w["subject"] == "Mathematics")
    assert maths["priority"] == "high"
    criteria = {r["criterion"] for r in maths["reasons"]}
    assert {"below_threshold", "declining"} <= criteria
    assert all(r["explanation"] for r in maths["reasons"])
    assert maths["student_reported_difficulty"] is True
    assert "pass mark" in weak["threshold_explanation"]


def test_custom_threshold_changes_result(sample_clean, profile):
    analyzer = StudentAnalyzer(sample_clean, {**profile, "target_percentage": None})
    assert analyzer.identify_weak_subjects(threshold=30)["weak_subjects"] == [] or \
        all(w["percentage"] >= 30 for w in analyzer.identify_weak_subjects(threshold=30)["weak_subjects"])
    names = {w["subject"] for w in analyzer.identify_weak_subjects(threshold=70)["weak_subjects"]}
    assert {"Mathematics", "Physics", "Urdu"} <= names


def test_relative_rule_skipped_with_fewer_than_three_subjects():
    cleaned, _ = clean_results(table([("E1", "Math", 60, 100), ("E1", "Art", 95, 100)]))
    subjects = subject_percentages(cleaned, "OTHER")
    weak = detect_weak_subjects(subjects, None, WeaknessConfig(weak_threshold=50))
    assert weak == []  # 60% is not weak; no personal-average comparison with 2 subjects


def test_single_exam_has_no_decline_flag(profile):
    cleaned, _ = clean_results(table([("E1", "Math", 60, 100), ("E1", "Art", 70, 100), ("E1", "Bio", 80, 100)]))
    analyzer = StudentAnalyzer(cleaned, {**profile, "target_percentage": None})
    for w in analyzer.identify_weak_subjects()["weak_subjects"]:
        assert all(r["criterion"] != "declining" for r in w["reasons"])


def test_inconsistent_subject_needs_three_results(profile):
    rows = [("E1", "Math", 90, 100), ("E2", "Math", 40, 100), ("E3", "Math", 85, 100),
            ("E1", "Art", 70, 100), ("E2", "Art", 70, 100), ("E3", "Art", 70, 100)]
    analyzer = StudentAnalyzer(clean_results(table(rows))[0], {**profile, "target_percentage": None, "difficult_subjects": []})
    math = analyzer.get_subject_performance_details("Math")
    assert math["weakness"] is None or "inconsistent" in {r["criterion"] for r in math["weakness"]["reasons"]}


# ---- comparison -----------------------------------------------------------------------------------
def test_comparison_unavailable_for_one_exam():
    cleaned, _ = clean_results(table([("E1", "Math", 60, 100)]))
    result = cmp.compare_examinations(cleaned)
    assert result["available"] is False and "previous" in result["reason"]


def test_comparison_changes(sample_clean):
    result = cmp.compare_examinations(sample_clean)
    assert result["available"] and result["previous_exam"] == "Pre-Board 2025" and result["current_exam"] == "Final 2026"
    maths = next(c for c in result["subject_changes"] if c["subject"] == "Mathematics")
    assert maths["change_points"] == -8 and maths["status"] == "declined"
    assert "Mathematics" in result["declined_subjects"]


def test_comparison_handles_new_and_dropped_subjects():
    rows = [("E1", "Math", 50, 100), ("E1", "Art", 60, 100), ("E2", "Math", 70, 100), ("E2", "Bio", 80, 100)]  # "Bio" is normalised to "Biology"
    result = cmp.compare_examinations(clean_results(table(rows))[0])
    assert result["new_subjects"] == ["Biology"] and result["dropped_subjects"] == ["Art"]
    assert [c["subject"] for c in result["subject_changes"]] == ["Mathematics"]


def test_trends_need_three_points(sample_clean):
    trends = cmp.subject_trends(sample_clean)
    assert trends["Mathematics"]["direction"] == "declining" and trends["Mathematics"]["points"] == 3
    assert cmp.subject_trends(sample_clean[sample_clean.exam_order < 2]) == {}
    assert cmp.overall_trend(sample_clean[sample_clean.exam_order < 2])["available"] is False


# ---- analyzer facade ------------------------------------------------------------------------------
def test_analyzer_rejects_invalid_data(profile):
    bad = pd.DataFrame({"exam": ["E1"], "subject": ["Math"], "obtained": [150], "total": [100]})
    with pytest.raises(DataValidationError) as err:
        StudentAnalyzer(bad, profile)
    assert err.value.issues


def test_all_outputs_are_json_serializable(sample_clean, profile):
    snapshot = StudentAnalyzer(sample_clean, profile).full_snapshot()
    json.dumps(snapshot)  # raises on numpy types / NaN-unsafe structures
    assert not any(isinstance(v, float) and np.isnan(v) for v in snapshot["overall"].values() if isinstance(v, float))


def test_subject_lookup_is_forgiving_and_errors_clearly(sample_clean, profile):
    analyzer = StudentAnalyzer(sample_clean, profile)
    assert analyzer.get_subject_performance_details("maths")["subject"] == "Mathematics"
    with pytest.raises(SubjectNotFoundError):
        analyzer.get_subject_performance_details("Astrology")


def test_current_exam_is_latest_and_students_do_not_mix(sample_clean, profile):
    a = StudentAnalyzer(sample_clean, profile)
    b = StudentAnalyzer(sample_clean[sample_clean.exam_order == 0], {**profile, "name": "Other"})
    assert a.exam_name == "Final 2026" and b.exam_name == "Mid-Term 2025"
    assert a.get_student_profile()["name"] == "Test Student" and b.get_student_profile()["name"] == "Other"


def test_priorities_are_ranked_with_evidence(sample_clean, profile):
    pr = StudentAnalyzer(sample_clean, profile).get_academic_improvement_priorities()["priorities"]
    assert pr[0]["subject"] == "Mathematics" and pr[0]["rank"] == 1 and pr[0]["evidence"]


# ---- charts ---------------------------------------------------------------------------------------
def test_charts_render_and_skip_unsupported(sample_clean, profile, tmp_path):
    from app.visualizations.visualization_service import generate_charts

    full = generate_charts(StudentAnalyzer(sample_clean, profile).generate_visualization_data(), tmp_path / "full")
    assert all(c.available and c.path.stat().st_size > 1000 for c in full)
    single = generate_charts(StudentAnalyzer(sample_clean[sample_clean.exam_order == 2], profile).generate_visualization_data(),
                             tmp_path / "single")
    status = {c.id: c.available for c in single}
    assert status["subject_percentages"] and not status["exam_comparison"] and not status["trend"]
    assert all(c.reason for c in single if not c.available)


def test_default_total_fills_blank_rows_and_is_disclosed():
    raw = pd.DataFrame({"subject": ["Math", "Physics"], "obtained": [40.0, 50], "total": [None, 100]})
    cleaned, report = clean_results(raw, default_total=100)
    assert report.is_valid and cleaned["total"].tolist() == [100.0, 100.0] and report.warnings
    _, strict = clean_results(raw)
    assert not strict.is_valid  # without a default the blank total is an error, never a guess

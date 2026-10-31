"""StudentAnalyzer: the LLM-independent facade over the data engine.

Every method returns plain JSON-compatible dicts/lists. The LangChain tools (app/agents/tools.py)
and the REST endpoints are thin wrappers around these methods, so all numbers come from
Pandas/NumPy and can be tested without an LLM.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.core.exceptions import DataValidationError
from app.data_engine import comparison as cmp
from app.data_engine.board_config import get_board
from app.data_engine.performance_analysis import (
    add_percentage,
    current_exam,
    exam_overall_series,
    overall_performance,
    subject_percentages,
)
from app.data_engine.preprocessing import clean_results, normalize_subject_name
from app.data_engine.statistics import descriptive_statistics, performance_distribution
from app.data_engine.weakness_detection import (
    WeaknessConfig,
    detect_strong_subjects,
    detect_weak_subjects,
)


class SubjectNotFoundError(KeyError):
    """Requested subject is not in the student's current examination."""


class StudentAnalyzer:
    """Analyse one student's results. Instances hold only that student's data (no cross-student state)."""

    def __init__(self, results: pd.DataFrame, profile: dict[str, Any],
                 config: WeaknessConfig | None = None, topic_mastery: list[dict[str, Any]] | None = None):
        ordered = results.sort_values("exam_order", kind="stable") if "exam_order" in results.columns else results
        self.history, report = clean_results(ordered)
        if not report.is_valid:
            raise DataValidationError("Academic data is invalid or incomplete; analysis was not run.",
                                      report.to_dicts())
        self.profile = dict(profile)
        self.board = get_board(self.profile.get("board"))
        self.cfg = config or WeaknessConfig()
        self.target = self.profile.get("target_percentage")
        self.exam_name, current = current_exam(self.history)
        self.subjects = subject_percentages(current, self.profile.get("board"))
        self.history_pct = add_percentage(self.history)
        self.reported_difficult = {normalize_subject_name(s).lower() for s in self.profile.get("difficult_subjects", [])}
        self._weak: list[dict] | None = None
        self.topic_mastery = topic_mastery or []

    # ---- helpers -------------------------------------------------------------------------------
    def _find_subject(self, name: str) -> str:
        wanted = normalize_subject_name(name).lower()
        for subject in self.subjects["subject"]:
            if subject.lower() == wanted:
                return subject
        raise SubjectNotFoundError(f"Subject '{name}' not found. Available: {', '.join(self.subjects['subject'])}")

    @staticmethod
    def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
        """DataFrame -> list of JSON-safe dicts (numpy types converted, floats rounded)."""
        def py(value: Any) -> Any:
            if isinstance(value, (bool, np.bool_)):
                return bool(value)
            if isinstance(value, (float, np.floating)):
                return round(float(value), 2)
            if isinstance(value, np.integer):
                return int(value)
            return value

        return [{k: py(v) for k, v in rec.items()} for rec in df.astype(object).to_dict(orient="records")]

    # ---- the 12 analysis operations (wrapped as tools in app/agents/tools.py) ---------------------
    def get_student_profile(self) -> dict[str, Any]:
        keys = ["student_id", "name", "board", "country", "grade", "academic_year", "school_name", "goals",
                "target_percentage", "difficult_subjects", "difficult_topics", "preferred_resources",
                "preferred_language"]
        profile = {k: self.profile.get(k) for k in keys}
        profile["board_notes"] = self.board.notes
        profile["board_pass_percentage"] = self.board.pass_percentage
        profile["current_exam"] = self.exam_name
        profile["examinations_recorded"] = int(self.history["exam_order"].nunique())
        return profile

    def get_student_subjects(self) -> dict[str, Any]:
        return {"exam_name": self.exam_name, "subjects": [str(s) for s in self.subjects["subject"]],
                "count": len(self.subjects)}

    def calculate_overall_performance(self) -> dict[str, Any]:
        return overall_performance(self.subjects, self.exam_name, self.profile.get("board"))

    def calculate_subject_percentages(self) -> dict[str, Any]:
        return {"exam_name": self.exam_name,
                "denominator_note": "Each percentage = obtained / that subject's total marks * 100.",
                "subjects": self._records(self.subjects)}

    def identify_weak_subjects(self, threshold: float | None = None) -> dict[str, Any]:
        cfg = self.cfg if threshold is None else WeaknessConfig(**{**self.cfg.__dict__, "weak_threshold": threshold})
        weak = self._weak_cached() if threshold is None else self._compute_weak(cfg)
        return {"weak_threshold_percent": cfg.weak_threshold, "pass_mark_percent": self.board.pass_percentage,
                "target_percentage": self.target, "count": len(weak), "weak_subjects": weak,
                "weak_topics": self.get_topic_mastery()["weak_topics"],
                "threshold_explanation": (
                    f"A subject is flagged when it meets any criterion: below {cfg.weak_threshold:g}%, below the "
                    f"board pass mark ({self.board.pass_percentage:g}%), more than {cfg.relative_gap:g} points "
                    f"under the student's own average, a decline of {cfg.decline_points:g}+ points, "
                    f"inconsistent results, or {cfg.target_gap:g}+ points short of the target. "
                    "Priority reflects how many criteria are met.")}

    def get_topic_mastery(self, subject: str | None = None) -> dict[str, Any]:
        """Return quiz-derived topic evidence without changing subject-level rules."""
        rows = [row for row in self.topic_mastery
                if subject is None or row["subject"].lower() == subject.lower()]
        weak = [row for row in rows if row.get("enough_data") and row.get("mastery_level") == "low"]
        return {"mastery": rows, "weak_topics": weak,
                "note": "Topic mastery requires completed, unflagged quiz evidence; marks alone do not identify topics."}

    def identify_strong_subjects(self) -> dict[str, Any]:
        strong = detect_strong_subjects(self.subjects, self.cfg)
        return {"strong_threshold_percent": self.cfg.strong_threshold, "count": len(strong), "strong_subjects": strong}

    def compare_examinations(self) -> dict[str, Any]:
        result = cmp.compare_examinations(self.history)
        result["overall_trend"] = cmp.overall_trend(self.history)
        result["subject_trends"] = cmp.subject_trends(self.history)
        return result

    def calculate_performance_statistics(self) -> dict[str, Any]:
        pcts = self.subjects["percentage"]
        return {"exam_name": self.exam_name, "statistics": descriptive_statistics(pcts),
                "distribution": performance_distribution(pcts),
                "std_dev_method": "sample standard deviation (ddof=1)"}

    def get_subject_performance_details(self, subject: str) -> dict[str, Any]:
        name = self._find_subject(subject)
        row = self.subjects[self.subjects["subject"] == name].iloc[0]
        ranked = self.subjects.sort_values("percentage", ascending=False)["subject"].tolist()
        avg = float(self.subjects["percentage"].mean())
        hist = cmp.subject_history(self.history, name)
        weak = next((w for w in self._weak_cached() if w["subject"] == name), None)
        strong = next((s for s in detect_strong_subjects(self.subjects, self.cfg) if s["subject"] == name), None)
        return {
            "subject": name, "exam_name": self.exam_name, "obtained": float(row["obtained"]),
            "total": float(row["total"]), "percentage": round(float(row["percentage"]), 2), "grade": row["grade"],
            "grade_is_indicative": bool(row["grade_is_indicative"]),
            "rank_among_subjects": ranked.index(name) + 1, "subjects_count": len(ranked),
            "difference_from_own_average": round(float(row["percentage"]) - avg, 2),
            "history": [{"exam": r.exam, "percentage": round(float(r.percentage), 2)} for r in hist.itertuples()],
            "weakness": weak, "strength": strong,
            "student_reported_difficulty": name.lower() in self.reported_difficult,
        }

    def generate_performance_summary(self) -> dict[str, Any]:
        overall = self.calculate_overall_performance()
        weak = self._weak_cached()
        strong = detect_strong_subjects(self.subjects, self.cfg)
        comparison = cmp.compare_examinations(self.history)
        lines = [
            (f"{self.exam_name}: {overall['total_obtained']:g}/{overall['total_possible']:g} marks "
            f"({overall['overall_percentage']:.1f}%) across {overall['subject_count']} subjects."),
            (f"Highest: {overall['highest_subject']} ({overall['highest_percentage']:.1f}%). "
            f"Lowest: {overall['lowest_subject']} ({overall['lowest_percentage']:.1f}%)."),
        ]
        if weak:
            lines.append("Needs attention: " + ", ".join(f"{w['subject']} ({w['percentage']:.1f}%)" for w in weak) + ".")
        else:
            lines.append("No subject met any weakness criterion.")
        if strong:
            lines.append("Strong: " + ", ".join(f"{s['subject']} ({s['percentage']:.1f}%)" for s in strong) + ".")
        if comparison["available"]:
            lines.append(f"Overall change versus '{comparison['previous_exam']}': "
                         f"{comparison['overall_change_points']:+.1f} points ({comparison['overall_status']}).")
        else:
            lines.append("No previous examination available for comparison.")
        return {"headline": lines[0], "lines": lines, "summary_text": " ".join(lines)}

    def generate_visualization_data(self) -> dict[str, Any]:
        series = exam_overall_series(self.history)
        weak = self._weak_cached()
        strong = detect_strong_subjects(self.subjects, self.cfg)
        overall = self.calculate_overall_performance()
        histories = {
            str(s): [{"exam": r.exam, "percentage": round(float(r.percentage), 2)}
                     for r in cmp.subject_history(self.history, s).itertuples()]
            for s in self.subjects["subject"]
        }
        return {
            "exam_name": self.exam_name,
            "subjects": self._records(self.subjects[["subject", "obtained", "total", "percentage", "grade"]]),
            "overall_percentage": overall["overall_percentage"],
            "average_percentage": overall["average_subject_percentage"],
            "pass_mark": self.board.pass_percentage,
            "target_percentage": self.target,
            "weak_threshold": self.cfg.weak_threshold,
            "strong_threshold": self.cfg.strong_threshold,
            "weak_subjects": [w["subject"] for w in weak],
            "strong_subjects": [s["subject"] for s in strong],
            "distribution": performance_distribution(self.subjects["percentage"]),
            "exams": [{"exam": r.exam, "percentage": round(float(r.percentage), 2), "obtained": r.obtained,
                       "total": r.total} for r in series.itertuples()],
            "comparison": cmp.compare_examinations(self.history),
            "subject_history": histories,
            "trends": cmp.subject_trends(self.history),
        }

    def get_academic_improvement_priorities(self) -> dict[str, Any]:
        items = []
        for rank, w in enumerate(self._weak_cached(), start=1):
            focus = {"high": "Immediate attention", "medium": "Targeted practice", "low": "Monitor and reinforce"}[w["priority"]]
            items.append({"rank": rank, "subject": w["subject"], "priority": w["priority"], "score": w["score"],
                          "current_percentage": w["percentage"], "target_percentage": self.target,
                          "gap_to_target": w["gap_to_target"], "focus": focus,
                          "evidence": [r["explanation"] for r in w["reasons"]],
                          "student_reported_difficulty": w["student_reported_difficulty"]})
        return {"priorities": items, "count": len(items),
                "note": "Ordered by number of weakness criteria met, then by lowest percentage."}

    # ---- insights & snapshot ------------------------------------------------------------------------
    def generate_insights(self) -> list[dict[str, Any]]:
        """Structured insights; every statement carries the numbers it is based on."""
        insights: list[dict[str, Any]] = []
        overall = self.calculate_overall_performance()
        for s in detect_strong_subjects(self.subjects, self.cfg):
            insights.append({"category": "strength", "title": f"Strong in {s['subject']}",
                             "statement": s["reasons"][0]["explanation"],
                             "evidence": {"subject": s["subject"], "percentage": s["percentage"]}})
        for w in self._weak_cached():
            cat = "attention" if w["priority"] == "high" else "improvement_area"
            insights.append({"category": cat, "title": f"{w['subject']} needs {'immediate attention' if cat == 'attention' else 'improvement'}",
                             "statement": " ".join(r["explanation"] for r in w["reasons"]),
                             "evidence": {"subject": w["subject"], "percentage": w["percentage"],
                                          "criteria": [r["criterion"] for r in w["reasons"]]}})
        comp = cmp.compare_examinations(self.history)
        if comp["available"]:
            for c in comp["subject_changes"]:
                if c["status"] == "improved":
                    insights.append({"category": "progress", "title": f"{c['subject']} improved",
                                     "statement": f"{c['subject']} rose from {c['previous_percentage']:.1f}% to "
                                                  f"{c['current_percentage']:.1f}% ({c['change_points']:+.1f} points).",
                                     "evidence": c})
        for i, p in enumerate(self.get_academic_improvement_priorities()["priorities"][:3], start=1):
            insights.append({"category": "priority", "title": f"Study priority {i}: {p['subject']}",
                             "statement": f"{p['subject']} is ranked {i} because: " + " ".join(p["evidence"]),
                             "evidence": {"subject": p["subject"], "rank": i, "score": p["score"]}})
        if not insights:
            insights.append({"category": "strength", "title": "Balanced results",
                             "statement": f"No subject met a weakness or strength criterion; overall result is "
                                          f"{overall['overall_percentage']:.1f}%.",
                             "evidence": {"overall_percentage": overall["overall_percentage"]}})
        return insights

    def full_snapshot(self) -> dict[str, Any]:
        """Everything the REST API / agents need, calculated in one place."""
        return {
            "profile": self.get_student_profile(),
            "overall": self.calculate_overall_performance(),
            "subjects": self.calculate_subject_percentages()["subjects"],
            "statistics": self.calculate_performance_statistics(),
            "weak": self.identify_weak_subjects(),
            "topic_mastery": self.get_topic_mastery(),
            "strong": self.identify_strong_subjects(),
            "comparison": self.compare_examinations(),
            "priorities": self.get_academic_improvement_priorities(),
            "insights": self.generate_insights(),
            "summary": self.generate_performance_summary(),
        }

    # ---- internals -----------------------------------------------------------------------------------
    def _compute_weak(self, cfg: WeaknessConfig) -> list[dict]:
        has_history = self.history["exam_order"].nunique() > 1
        return detect_weak_subjects(self.subjects, self.history if has_history else None, cfg,
                                    pass_mark=self.board.pass_percentage, target=self.target,
                                    reported_difficult=self.reported_difficult)

    def _weak_cached(self) -> list[dict]:
        if self._weak is None:
            self._weak = self._compute_weak(self.cfg)
        return self._weak

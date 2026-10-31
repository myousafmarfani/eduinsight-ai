"""Rule-based chatbot used when no LLM is available (or the LLM fails).

Answers are assembled only from `StudentAnalyzer` outputs and the stored report, so they are as
factual as the LLM mode; they are just less conversational.
"""
from __future__ import annotations

import re
from typing import Any

from app.data_engine.analyzer import StudentAnalyzer
from app.schemas.analysis import AcademicReport

_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
_WEIGHT = {"high": 3, "medium": 2, "low": 1}


def _mentioned_subjects(message: str, analyzer: StudentAnalyzer) -> list[str]:
    text = message.lower()
    found = []
    for subject in analyzer.subjects["subject"]:
        short = {"mathematics": "math", "computer science": "computer"}.get(subject.lower(), subject.lower())
        if subject.lower() in text or re.search(rf"\b{re.escape(short)}", text):
            found.append(subject)
    return found


def _has(message: str, *words: str) -> bool:
    text = message.lower()
    return any(w in text for w in words)


def _subject_line(d: dict[str, Any]) -> str:
    return f"{d['subject']}: {d['obtained']:g}/{d['total']:g} ({d['percentage']:.1f}%, grade {d['grade']})"


def _compare_two(analyzer: StudentAnalyzer, a: str, b: str) -> str:
    da, db_ = analyzer.get_subject_performance_details(a), analyzer.get_subject_performance_details(b)
    diff = da["percentage"] - db_["percentage"]
    lines = ["**What your marks show**", f"- {_subject_line(da)}", f"- {_subject_line(db_)}",
             f"- Difference: {abs(diff):.1f} points in favour of {a if diff > 0 else b}."]
    for d in (da, db_):
        if d["weakness"]:
            lines.append(f"- {d['subject']} was flagged because: " + " ".join(r["explanation"] for r in d["weakness"]["reasons"]))
        if len(d["history"]) > 1:
            lines.append(f"- {d['subject']} history: " + " -> ".join(f"{h['percentage']:.0f}%" for h in d["history"]))
    lines.append("\nMarks alone cannot explain *why* one subject is lower (for example topics, study time or exam technique). "
                 "A good next step is to look at the questions you lost marks on in the lower subject.")
    return "\n".join(lines)


def _study_plan(analyzer: StudentAnalyzer) -> str:
    items = analyzer.get_academic_improvement_priorities()["priorities"]
    if not items:
        low = analyzer.subjects.sort_values("percentage").iloc[0]
        items = [{"subject": low["subject"], "priority": "low", "current_percentage": float(low["percentage"])}]
    slots = [i["subject"] for i in items for _ in range(_WEIGHT[i["priority"]])]
    plan = [f"- **{day}**: {slots[n % len(slots)]} - 45 min practice on one topic, then check and log mistakes"
            for n, day in enumerate(_DAYS)]
    plan.append("- **Sunday**: Short timed quiz on this week's weakest subject, review the mistake log, rest.")
    basis = ", ".join(f"{i['subject']} ({i['current_percentage']:.1f}%, {i['priority']})" for i in items)
    return ("**Basis (from your marks):** " + basis + ".\n\n**Suggested weekly plan** (a general template weighted toward "
            "your higher-priority subjects; adjust it to your timetable):\n" + "\n".join(plan))


def rule_based_reply(message: str, analyzer: StudentAnalyzer, report: AcademicReport | None) -> tuple[str, list[str]]:
    """Return (reply, tools_used)."""
    subjects = _mentioned_subjects(message, analyzer)

    if _has(message, "topic") and _has(message, "weak", "struggl", "worst", "lowest"):
        data = analyzer.get_topic_mastery()
        if not data["mastery"]:
            return "No quiz topic evidence is available yet. Take a practice quiz to identify topic-level weaknesses.", ["get_topic_mastery"]
        weak = data["weak_topics"]
        if not weak:
            return "No topic has reached the minimum evidence threshold as weak yet. " + data["note"], ["get_topic_mastery"]
        return "\n".join(f"- **{row['topic']}** ({row['subject']}): {row['evidence']}" for row in weak), ["get_topic_mastery"]

    if _has(message, "why", "compare", "lower than", "higher than", "versus", " vs ") and len(subjects) >= 2:
        return _compare_two(analyzer, subjects[0], subjects[1]), ["get_subject_performance_details"]

    if _has(message, "study plan", "weekly plan", "schedule", "timetable"):
        return _study_plan(analyzer), ["get_academic_improvement_priorities"]

    if _has(message, "resource", "video", "lecture", "youtube", "website", "practice question", "past paper"):
        if report is None or not report.resources:
            reason = report.resource_search_status if report else "Run the analysis from the dashboard first to generate resources."
            return f"I don't have learning resources saved yet. {reason}", []
        target = subjects[0] if subjects else (report.weaknesses[0].subject if report.weaknesses else None)
        picks = [r for r in report.resources if target is None or r.subject.lower() == target.lower()][:6] or report.resources[:6]
        lines = [f"- [{r.title}]({r.url}) ({r.resource_type.value}, {r.subject})" for r in picks]
        return "Resources found by web search for your report (check they match your syllabus):\n" + "\n".join(lines), []

    if _has(message, "chart", "graph", "plot", "radar", "visual"):
        viz = analyzer.generate_visualization_data()
        lines = [(f"- The percentage bar chart shows {len(viz['subjects'])} subjects from {viz['pass_mark']:g}% (board pass mark) "
                 f"up to the best at {max(s['percentage'] for s in viz['subjects']):.1f}%. Red bars are subjects flagged weak "
                 f"({', '.join(viz['weak_subjects']) or 'none'}); teal bars are strong ({', '.join(viz['strong_subjects']) or 'none'})."),
                 f"- Your overall result is {viz['overall_percentage']:.1f}%; your average subject percentage is {viz['average_percentage']:.1f}%."]
        comp = viz["comparison"]
        lines.append(f"- The comparison charts show change since '{comp['previous_exam']}'." if comp["available"]
                     else "- Comparison and trend charts need more than one examination, so they are not shown yet.")
        return "\n".join(lines), ["generate_visualization_data"]

    if _has(message, "prioriti", "focus", "first", "before my next", "improve", "what should i"):
        pr = analyzer.get_academic_improvement_priorities()["priorities"]
        if not pr:
            return "No subject met a weakness criterion, so there is no urgent priority. To stretch yourself, keep practising your lowest subject.", ["get_academic_improvement_priorities"]
        lines = [f"{p['rank']}. **{p['subject']}** ({p['current_percentage']:.1f}%, {p['priority']} priority): " + " ".join(p["evidence"]) for p in pr[:4]]
        return "Priorities, ranked from your marks:\n" + "\n".join(lines), ["get_academic_improvement_priorities"]

    if _has(message, "weak", "struggl", "worst", "lowest", "bad"):
        data = analyzer.identify_weak_subjects()
        if not data["weak_subjects"]:
            return "No subject met a weakness criterion. " + data["threshold_explanation"], ["identify_weak_subjects"]
        lines = [f"- **{w['subject']}** ({w['percentage']:.1f}%): " + " ".join(r["explanation"] for r in w["reasons"]) for w in data["weak_subjects"]]
        return "\n".join(lines) + f"\n\n*How subjects are flagged:* {data['threshold_explanation']}", ["identify_weak_subjects"]

    if _has(message, "strong", "best", "good at", "strength"):
        strong = analyzer.identify_strong_subjects()["strong_subjects"]
        if not strong:
            return "No subject met a strength criterion yet.", ["identify_strong_subjects"]
        return "\n".join(f"- **{s['subject']}** ({s['percentage']:.1f}%): {s['reasons'][0]['explanation']}" for s in strong), ["identify_strong_subjects"]

    if _has(message, "change", "progress", "trend", "previous", "last exam", "compared"):
        comp = analyzer.compare_examinations()
        if not comp["available"]:
            return comp["reason"], ["compare_examinations"]
        lines = [(f"Overall: {comp['previous_overall_percentage']:.1f}% -> {comp['current_overall_percentage']:.1f}% "
                 f"({comp['overall_change_points']:+.1f} points, {comp['overall_status']}).")]
        lines += [f"- {c['subject']}: {c['previous_percentage']:.1f}% -> {c['current_percentage']:.1f}% ({c['change_points']:+.1f})"
                  for c in comp["subject_changes"]]
        return "\n".join(lines), ["compare_examinations"]

    if subjects:
        return _subject_line(analyzer.get_subject_performance_details(subjects[0])) + _history_text(analyzer, subjects[0]), ["get_subject_performance_details"]

    if _has(message, "overall", "total", "percentage", "result", "how did i", "summary", "performance"):
        return analyzer.generate_performance_summary()["summary_text"], ["generate_performance_summary"]

    return ("I can answer questions about your marks, weak and strong subjects, progress, study priorities, a weekly study plan, "
            "your charts and the resources in your report. Here is where you stand now: "
            + analyzer.generate_performance_summary()["headline"]), ["generate_performance_summary"]


def _history_text(analyzer: StudentAnalyzer, subject: str) -> str:
    hist = analyzer.get_subject_performance_details(subject)["history"]
    return "" if len(hist) < 2 else "\nHistory: " + " -> ".join(f"{h['percentage']:.0f}%" for h in hist)

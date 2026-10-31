"""Agent 2 - Academic Improvement Advisor.

Turns the analyst's findings and the engine's priority ranking into subject-specific study plans.
Evidence always comes from the engine; actions/goals are advice (templated, or LLM-written and
flagged `ai_generated`). The LLM can only advise on subjects the engine actually flagged.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.agents.academic_analyst import AnalystFindings
from app.data_engine.analyzer import StudentAnalyzer
from app.schemas.analysis import ImprovementRecommendation, Priority

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an Academic Improvement Advisor for school students.
You receive calculated evidence about a student's weakest subjects. For EACH listed subject write:
- 3 to 5 concrete, realistic study actions suited to the student's board and grade (practice, review of mistakes, weekly self-assessment, asking a teacher, etc.)
- one measurable goal for the next examination.
Rules: only advise on the subjects provided; do not state marks other than those given; do not claim to know which
topics the student finds hard unless the profile lists them; keep advice age-appropriate and encouraging."""

MAX_SUBJECTS = 5


class AdvisorRecommendation(BaseModel):
    subject: str
    actions: list[str] = Field(min_length=1, max_length=6)
    goal: str


class AdvisorPlan(BaseModel):
    recommendations: list[AdvisorRecommendation]


def standard_actions(subject: str, priority: str, topics: list[str] | None = None) -> list[str]:
    """Generic study strategy used when no LLM is available (clearly not derived from the marks)."""
    actions = [
        f"Review your {subject} class notes and textbook chapters, listing the concepts you cannot yet explain in your own words.",
        f"Do 10-15 {subject} practice questions on one topic at a time, then check every answer.",
        f"Keep a mistake log for {subject}: write what went wrong and the correct method for each error.",
        f"Take a short timed {subject} quiz at the end of each week and note your score to see progress.",
    ]
    if topics:
        actions.insert(0, f"Start with the topics you named as difficult: {', '.join(topics)}.")
    if priority == "high":
        actions.append(f"Ask your {subject} teacher or a classmate to go through the questions you keep getting wrong.")
    return actions[:5]


def _goal(pct: float, target: float | None) -> str:
    step = min(100.0, round(pct + 10))
    if target is not None and target > pct:
        step = min(step, round(target))
    return (f"Suggested goal: raise this subject from {pct:.0f}% to about {step:.0f}% by the next examination "
            "(a step of up to 10 points, capped at your target when you set one).")


def _items(analyzer: StudentAnalyzer) -> list[dict[str, Any]]:
    """Priority items for recommendations; falls back to the lowest subject when nothing is flagged."""
    items = analyzer.get_academic_improvement_priorities()["priorities"][:MAX_SUBJECTS]
    if items:
        return items
    low = analyzer.subjects.sort_values("percentage").iloc[0]
    return [{"subject": str(low["subject"]), "priority": "low", "current_percentage": round(float(low["percentage"]), 2),
             "evidence": [(f"No subject met a weakness criterion; {low['subject']} is your lowest at "
                          f"{float(low['percentage']):.1f}%.")]}]


def _topics_for(analyzer: StudentAnalyzer, subject: str) -> list[str]:
    topics = analyzer.profile.get("difficult_topics") or {}
    for name, values in topics.items():
        if name.strip().lower() == subject.lower():
            return list(values)
    return []


def deterministic_recommendations(analyzer: StudentAnalyzer) -> list[ImprovementRecommendation]:
    recs = []
    for item in _items(analyzer):
        recs.append(ImprovementRecommendation(
            subject=item["subject"], priority=Priority(item["priority"]), evidence=" ".join(item["evidence"]),
            actions=standard_actions(item["subject"], item["priority"], _topics_for(analyzer, item["subject"])),
            goal=_goal(float(item["current_percentage"]), analyzer.target), ai_generated=False))
    return recs


def run_improvement_advisor(analyzer: StudentAnalyzer, findings: AnalystFindings, llm: Any | None) -> list[ImprovementRecommendation]:
    """Return one recommendation per prioritised subject. Raises on LLM failure (caller falls back)."""
    base = deterministic_recommendations(analyzer)
    if llm is None:
        return base

    from langchain_core.messages import HumanMessage, SystemMessage

    payload = {
        "student": {k: analyzer.profile.get(k) for k in ("board", "grade", "goals", "target_percentage",
                                                           "difficult_topics", "preferred_language")},
        "analyst_summary": findings.summary,
        "subjects_to_advise": [{"subject": r.subject, "priority": r.priority.value, "evidence": r.evidence} for r in base],
    }
    plan: AdvisorPlan = llm.with_structured_output(AdvisorPlan, method="function_calling").invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=json.dumps(payload, default=str))])
    by_subject = {r.subject.lower(): r for r in plan.recommendations if r.actions}

    merged = []
    for rec in base:
        ai = by_subject.get(rec.subject.lower())
        if ai is None:
            merged.append(rec)  # the model skipped it: keep the standard plan rather than leave a gap
        else:
            merged.append(ImprovementRecommendation(
                subject=rec.subject, priority=rec.priority, evidence=rec.evidence,
                actions=[a.strip() for a in ai.actions if a.strip()][:6] or rec.actions,
                goal=ai.goal.strip() or rec.goal, ai_generated=True))
    return merged

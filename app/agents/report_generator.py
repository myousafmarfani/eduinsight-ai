"""Agent 4 - Academic Report Generator.

Assembles the structured outputs of the previous agents into an `AcademicReport`. The calculated
sections are always rendered deterministically; the optional AI summary is an interpretation
labelled as such.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.agents.academic_analyst import AnalystFindings
from app.schemas.analysis import (
    AcademicInsight,
    AcademicReport,
    EducationalResource,
    ImprovementRecommendation,
    PerformanceMetrics,
    StrongSubject,
    WeakSubject,
)
from app.services.report_service import render_markdown

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You write the summary paragraph of a school progress report addressed to the student.
Write 2-3 short paragraphs in plain, encouraging, honest language.
Rules: use ONLY numbers that appear in the provided JSON; do not invent marks, topics, causes or resources;
say clearly when data is limited (e.g. one exam only); distinguish what the marks show from suggestions;
do not use headings or bullet lists."""


def generate_ai_summary(llm: Any, snapshot: dict[str, Any], findings: AnalystFindings,
                        recommendations: list[ImprovementRecommendation]) -> str:
    from langchain_core.messages import HumanMessage, SystemMessage

    from app.agents.runner import message_text

    payload = {
        "overall": snapshot["overall"], "weak_subjects": [{"subject": w["subject"], "percentage": w["percentage"],
                   "priority": w["priority"], "reasons": [r["explanation"] for r in w["reasons"]]}
                  for w in snapshot["weak"]["weak_subjects"]],
        "strong_subjects": [{"subject": s["subject"], "percentage": s["percentage"]} for s in snapshot["strong"]["strong_subjects"]],
        "comparison": {k: snapshot["comparison"].get(k) for k in ("available", "reason", "previous_exam", "current_exam",
                       "overall_change_points", "overall_status", "improved_subjects", "declined_subjects")},
        "analyst_caveats": findings.caveats,
        "priorities": [{"subject": r.subject, "priority": r.priority.value} for r in recommendations],
    }
    reply = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=json.dumps(payload, default=str))])
    return message_text(reply.content).strip()


def generate_report(
    student_id: str, snapshot: dict[str, Any], findings: AnalystFindings,
    recommendations: list[ImprovementRecommendation], resources: list[EducationalResource],
    resource_status: str, ai_notes: list[str], llm: Any | None,
) -> AcademicReport:
    """Build the final report from validated data. The caller guarantees the data passed validation."""
    notes = list(ai_notes)
    ai_summary: str | None = None
    if llm is not None:
        try:
            ai_summary = generate_ai_summary(llm, snapshot, findings, recommendations) or None
        except Exception as exc:  # noqa: BLE001
            logger.warning("AI summary failed: %s", type(exc).__name__)
            notes.append("The AI summary was unavailable; the calculated report is complete without it.")
    parts = {
        "overview": PerformanceMetrics(**snapshot["overall"]),
        "subjects": snapshot["subjects"],
        "strengths": [StrongSubject(**s) for s in snapshot["strong"]["strong_subjects"]],
        "weaknesses": [WeakSubject(**w) for w in snapshot["weak"]["weak_subjects"]],
        "weak_topics": snapshot["topic_mastery"]["weak_topics"],
        "comparison": snapshot["comparison"],
        "recommendations": recommendations,
        "resources": resources,
        "resource_status": resource_status,
        "ai_notes": notes + [f"Analyst caveat: {c}" for c in findings.caveats],
    }
    return AcademicReport(
        student_id=student_id, generated_at=datetime.now(UTC),
        ai_generated=bool(findings.ai_generated or ai_summary or any(r.ai_generated for r in recommendations)),
        ai_notes=parts["ai_notes"], overview=parts["overview"], strengths=parts["strengths"],
        weaknesses=parts["weaknesses"], insights=[AcademicInsight(**i) for i in snapshot["insights"]],
        weak_topics=parts["weak_topics"],
        comparison=snapshot["comparison"], recommendations=recommendations, resources=resources,
        resource_search_status=resource_status, narrative_markdown=render_markdown(parts, ai_summary))

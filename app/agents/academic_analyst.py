"""Agent 1 - Academic Data Analyst.

Investigates the student's results by *calling the analysis tools* (LLM mode) and returns structured
findings. Without an LLM it returns a deterministic summary built from the same tools' outputs.
"""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from app.data_engine.analyzer import StudentAnalyzer

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an Academic Data Analyst. Investigate one student's exam results using the provided tools.
Rules:
- Call tools to get facts; never calculate or guess marks yourself.
- Cover: overall performance, weak and strong subjects, statistics, and the comparison with earlier exams (if any).
- Quote only numbers returned by tools. If a tool says data is unavailable (e.g. no previous exam), say so.
- Marks cannot reveal which topics a student finds hard; do not invent topic-level weaknesses."""


class AnalystFindings(BaseModel):
    """Structured output of the analyst agent."""

    summary: str = Field(description="3-5 sentence factual summary of the student's performance")
    key_observations: list[str] = Field(description="Specific observations, each citing numbers from the tools")
    caveats: list[str] = Field(default_factory=list, description="Limits of the data, e.g. only one exam recorded")
    ai_generated: bool = False
    tools_used: list[str] = Field(default_factory=list)


def deterministic_findings(analyzer: StudentAnalyzer) -> AnalystFindings:
    summary = analyzer.generate_performance_summary()
    insights = analyzer.generate_insights()
    caveats = []
    comparison = analyzer.compare_examinations()
    if not comparison["available"]:
        caveats.append(comparison["reason"])
    if analyzer.subjects.shape[0] < 3:
        caveats.append("Fewer than 3 subjects: comparisons against your own average are not meaningful.")
    return AnalystFindings(summary=summary["summary_text"], key_observations=[i["statement"] for i in insights],
                           caveats=caveats, ai_generated=False)


def run_academic_analyst(analyzer: StudentAnalyzer, llm: Any | None) -> AnalystFindings:
    """Run the analyst. Raises on LLM failure so the orchestrator can record a note and fall back."""
    if llm is None:
        return deterministic_findings(analyzer)

    from app.agents.runner import run_tool_loop
    from app.agents.tools import build_student_tools

    result = run_tool_loop(
        llm, build_student_tools(analyzer), SYSTEM_PROMPT,
        "Analyse this student's current academic performance and report your findings.",
        output_model=AnalystFindings,
        final_instruction="Return your findings in the required structure, using only numbers from the tool results.",
    )
    findings: AnalystFindings = result.parsed
    findings.ai_generated = True
    findings.tools_used = sorted(set(result.tools_used))
    return findings

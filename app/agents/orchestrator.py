"""Central orchestrator: a deterministic pipeline in which LLM agents add value step by step.

    validate data -> numeric analysis (Pandas/NumPy)  [always deterministic]
      -> Agent 1 Analyst (tool calling)  -> Agent 2 Advisor (structured output)
      -> Agent 3 Researcher (Tavily)     -> Agent 4 Report generator

Every LLM step is optional: on any failure the step falls back to its deterministic version, a
note is recorded in the report, and the LLM is disabled for the remaining steps so one outage
does not cause a chain of timeouts.
"""
from __future__ import annotations

import logging
from typing import Any

from app.agents.academic_analyst import (
    deterministic_findings,
    run_academic_analyst,
)
from app.agents.improvement_advisor import (
    deterministic_recommendations,
    run_improvement_advisor,
)
from app.agents.llm import get_llm
from app.agents.report_generator import generate_report
from app.agents.resource_researcher import run_resource_researcher
from app.config import Settings, get_settings
from app.data_engine.analyzer import StudentAnalyzer
from app.schemas.analysis import AcademicReport
from app.services.resource_search import ResourceSearcher

logger = logging.getLogger(__name__)
_UNSET: Any = object()


class AcademicOrchestrator:
    def __init__(self, settings: Settings | None = None, llm: Any = _UNSET, searcher: ResourceSearcher | None = None):
        self.settings = settings or get_settings()
        self.llm = get_llm(self.settings) if llm is _UNSET else llm
        self.searcher = searcher or ResourceSearcher(self.settings.tavily_api_key, self.settings.tavily_timeout_seconds)

    def run(self, student_id: str, analyzer: StudentAnalyzer) -> AcademicReport:
        """Run the full workflow. `analyzer` can only exist for validated data (it validates on creation)."""
        notes: list[str] = []
        llm = self.llm
        if llm is None:
            notes.append("No AI model is configured, so advice uses standard templates. "
                         "All figures are still calculated from your marks.")

        snapshot = analyzer.full_snapshot()

        try:
            findings = run_academic_analyst(analyzer, llm)
        except Exception as exc:
            logger.warning("Analyst agent failed: %s: %s", type(exc).__name__, exc, exc_info=True)
            findings, llm = deterministic_findings(analyzer), None
            notes.append(f"The AI analyst was unavailable ({type(exc).__name__}: {str(exc)[:160]}); "
                         "a standard analysis summary was used.")

        try:
            recommendations = run_improvement_advisor(analyzer, findings, llm)
        except Exception as exc:
            logger.warning("Advisor agent failed: %s: %s", type(exc).__name__, exc, exc_info=True)
            recommendations, llm = deterministic_recommendations(analyzer), None
            notes.append(f"The AI advisor was unavailable ({type(exc).__name__}: {str(exc)[:160]}); "
                         "standard study strategies were used.")

        resources, resource_status, research_notes = run_resource_researcher(
            analyzer.profile, recommendations, self.searcher, llm, self.settings,
            weak_topics=analyzer.get_topic_mastery()["weak_topics"])
        notes.extend(research_notes)

        return generate_report(student_id, snapshot, findings, recommendations, resources, resource_status, notes, llm)
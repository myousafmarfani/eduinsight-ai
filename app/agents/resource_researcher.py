"""Agent 3 - Educational Resource Researcher (Tavily).

Builds targeted queries (board + grade + subject [+ topic] [+ language]) for the highest-priority
subjects, runs them through `ResourceSearcher`, and returns de-duplicated, validated results with a
human-readable status. The LLM, when available, may sharpen the queries; it never supplies resources.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.config import Settings
from app.schemas.analysis import EducationalResource, ImprovementRecommendation
from app.services.resource_search import (
    ResourceSearcher,
    SearchStatus,
    dedupe_resources,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You write web-search queries to find study resources for a school student.
For each subject given, write up to 3 queries: one for video lectures, one for practice questions / past papers, one for a study guide or notes.
Include the education board, class/grade and subject. If specific difficult topics are listed for that subject, include the topic.
If a preferred language other than English is given, include it. Do not invent topics. Return queries only."""


class SearchQuery(BaseModel):
    subject: str
    query: str = Field(min_length=3, max_length=200)
    kind: Literal["video", "practice", "guide"]


class ResearchPlan(BaseModel):
    queries: list[SearchQuery]


def _preferred_kinds(preferred: list[str]) -> list[str]:
    text = " ".join(preferred).lower()
    kinds = []
    if any(w in text for w in ("video", "lecture", "youtube")):
        kinds.append("video")
    if any(w in text for w in ("practice", "question", "past paper", "exercise", "quiz")):
        kinds.append("practice")
    if any(w in text for w in ("read", "note", "book", "article", "guide", "text")):
        kinds.append("guide")
    return kinds or ["video", "practice", "guide"]


def deterministic_queries(profile: dict[str, Any], subjects: list[str],
                          weak_topics: dict[str, list[str]] | None = None) -> list[SearchQuery]:
    context = f"{profile.get('board', '')} {profile.get('grade', '')}".strip()
    language = (profile.get("preferred_language") or "").strip()
    language_part = f" in {language}" if language and language.lower() != "english" else ""
    topics_by_subject = {k.strip().lower(): v for k, v in (profile.get("difficult_topics") or {}).items()}
    suffix = {"video": "detailed lectures", "practice": "practice questions past papers", "guide": "study guide notes"}
    queries = []
    for subject in subjects:
        topics = (weak_topics or {}).get(subject.lower()) or topics_by_subject.get(subject.lower()) or [""]
        for kind in _preferred_kinds(profile.get("preferred_resources") or []):
            topic = topics[0]
            queries.append(SearchQuery(subject=subject, kind=kind,
                                       query=f"{context} {subject} {topic} {suffix[kind]}{language_part}".replace("  ", " ").strip()))
    return queries


def _llm_queries(llm: Any, profile: dict[str, Any], subjects: list[str], fallback: list[SearchQuery]) -> list[SearchQuery]:
    from langchain_core.messages import HumanMessage, SystemMessage

    payload = {"board": profile.get("board"), "grade": profile.get("grade"), "subjects": subjects,
               "difficult_topics": profile.get("difficult_topics") or {},
               "preferred_language": profile.get("preferred_language"),
               "preferred_resource_types": profile.get("preferred_resources") or []}
    plan: ResearchPlan = llm.with_structured_output(ResearchPlan, method="function_calling").invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=json.dumps(payload))])
    allowed = {s.lower(): s for s in subjects}
    cleaned, per_subject = [], {}
    for q in plan.queries:
        subject = allowed.get(q.subject.strip().lower())
        if not subject or per_subject.get(subject, 0) >= 3:
            continue
        per_subject[subject] = per_subject.get(subject, 0) + 1
        cleaned.append(SearchQuery(subject=subject, query=q.query.strip(), kind=q.kind))
    return cleaned or fallback


def run_resource_researcher(
    profile: dict[str, Any], recommendations: list[ImprovementRecommendation], searcher: ResourceSearcher,
    llm: Any | None, settings: Settings, weak_topics: list[dict[str, Any]] | None = None,
) -> tuple[list[EducationalResource], str, list[str]]:
    """Return (resources, status message, notes). Never raises for search problems."""
    notes: list[str] = []
    subjects = [r.subject for r in recommendations][: settings.max_resource_subjects]
    if not searcher.configured:
        return [], "Learning resources were skipped because TAVILY_API_KEY is not configured.", notes
    if not subjects:
        return [], "No subjects to search resources for.", notes

    topic_map: dict[str, list[str]] = {}
    for row in weak_topics or []:
        topic_map.setdefault(row["subject"].lower(), []).append(row["topic"])
    queries = deterministic_queries(profile, subjects, topic_map)
    if llm is not None:
        try:
            queries = _llm_queries(llm, profile, subjects, queries)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM query planning failed: %s", type(exc).__name__)
            notes.append("AI query planning was unavailable; standard search queries were used.")

    context = f"{profile.get('board', '')} {profile.get('grade', '')}".strip()
    resources: list[EducationalResource] = []
    problems: dict[SearchStatus, int] = {}
    for q in queries:
        outcome = searcher.search(q.query, q.subject, q.kind, settings.max_results_per_search, context)
        quiz_topics = topic_map.get(q.subject.lower(), [])
        if quiz_topics:
            outcome.resources = [
                resource.model_copy(update={
                    "why_recommended": (
                        f"{resource.why_recommended} Quiz evidence identifies {', '.join(quiz_topics)} "
                        "as a topic needing practice."
                    )
                })
                for resource in outcome.resources
            ]
        resources.extend(outcome.resources)
        if outcome.status is not SearchStatus.OK:
            problems[outcome.status] = problems.get(outcome.status, 0) + 1
        if outcome.status in (SearchStatus.RATE_LIMITED, SearchStatus.NO_API_KEY):
            break  # stop hammering a service that told us to stop

    resources = dedupe_resources(resources)
    if resources and not problems:
        status = f"Found {len(resources)} resources from {len(queries)} searches."
    elif resources:
        status = f"Found {len(resources)} resources; some searches did not succeed ({_describe(problems)})."
    elif SearchStatus.RATE_LIMITED in problems:
        status = "Resource search hit a rate or usage limit. Try again later."
    elif SearchStatus.FAILED in problems:
        status = "Resource search is currently unavailable. The rest of the report is unaffected."
    else:
        status = "The searches returned no results."
    return resources, status, notes


def _describe(problems: dict[SearchStatus, int]) -> str:
    return ", ".join(f"{count} {status.value.replace('_', ' ')}" for status, count in problems.items())

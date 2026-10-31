"""Academic chatbot: LangChain tool-calling when an LLM is configured, rule-based otherwise.

Isolation: the analyzer, tools and history are rebuilt from the database for the requesting
student on every call; nothing student-specific is cached in this module.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.llm import get_llm
from app.chatbot.prompts import CHAT_SYSTEM_PROMPT
from app.chatbot.rules import rule_based_reply
from app.config import Settings, get_settings
from app.schemas.analysis import AcademicReport
from app.schemas.chatbot import ChatResponse
from app.services import student_service
from app.services.analysis_service import build_analyzer

logger = logging.getLogger(__name__)
_UNSET: Any = object()


def _resources_tool(report: AcademicReport | None):
    """Tool exposing the resources stored in the student's latest report (the LLM cannot invent any)."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    class ResourcesInput(BaseModel):
        subject: str | None = Field(default=None, description="Optional subject to filter by")

    def get_recommended_resources(subject: str | None = None) -> dict[str, Any]:
        if report is None:
            return {"available": False, "reason": "No report yet. The student must run the analysis on the dashboard first."}
        items = [r for r in report.resources if not subject or r.subject.lower() == subject.lower()]
        return {"available": bool(items), "search_status": report.resource_search_status,
                "resources": [r.model_dump(mode="json") for r in items[:8]]}

    return StructuredTool.from_function(
        func=get_recommended_resources, name="get_recommended_resources", args_schema=ResourcesInput,
        description="Learning resources (title, URL, type, subject) found for this student by web search.")


class ChatService:
    def __init__(self, settings: Settings | None = None, llm: Any = _UNSET):
        self.settings = settings or get_settings()
        self.llm = get_llm(self.settings) if llm is _UNSET else llm

    def reply(self, db: Session, student_id: str, message: str, session_id: str | None = None) -> ChatResponse:
        analyzer = build_analyzer(db, student_id, self.settings)  # raises 404/422 for unknown student / no data
        session = session_id or str(uuid.uuid4())
        history = student_service.recent_chat_messages(db, student_id, session)
        report = student_service.latest_report(db, student_id)

        text, tools_used, ai, note = "", [], False, None
        if self.llm is not None:
            try:
                text, tools_used = self._llm_reply(analyzer, report, history, message)
                ai = True
            except Exception as exc:
                logger.warning("Chat LLM failed: %s: %s", type(exc).__name__, exc, exc_info=True)
                note = (f"The AI model was unavailable ({type(exc).__name__}: {str(exc)[:160]}), "
                        "so this answer comes from the built-in rules.")
        if not ai:
            text, tools_used = rule_based_reply(message, analyzer, report)
            note = note or "No AI model is configured; answers are generated from your calculated results by built-in rules."

        student_service.add_chat_message(db, student_id, session, "user", message)
        student_service.add_chat_message(db, student_id, session, "assistant", text)
        return ChatResponse(reply=text, session_id=session, tools_used=sorted(set(tools_used)), ai_generated=ai, note=note)

    def _llm_reply(self, analyzer, report, history, message) -> tuple[str, list[str]]:
        from langchain_core.messages import AIMessage, HumanMessage

        from app.agents.runner import run_tool_loop
        from app.agents.tools import build_student_tools

        overall = analyzer.calculate_overall_performance()
        profile = analyzer.get_student_profile()
        system = CHAT_SYSTEM_PROMPT.format(name=profile["name"], board=profile["board"], grade=profile["grade"],
                                           exam=overall["exam_name"], overall=overall["overall_percentage"])
        past = [HumanMessage(content=c) if r == "user" else AIMessage(content=c) for r, c in history]
        tools = build_student_tools(analyzer) + [_resources_tool(report)]
        result = run_tool_loop(self.llm, tools, system, message, history=past)
        if not result.text.strip():
            raise RuntimeError("empty model reply")
        return result.text.strip(), result.tools_used
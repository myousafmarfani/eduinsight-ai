"""Agent tool, orchestrator, resource-search and chatbot-rule tests. No network or API keys are used."""
from __future__ import annotations

import json

import pytest

from app.data_engine.analyzer import StudentAnalyzer

pytest.importorskip("pydantic")


@pytest.fixture
def analyzer(sample_clean, profile):
    return StudentAnalyzer(sample_clean, profile)


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status_code, self._payload = status, payload or {}

    def json(self):
        return self._payload


def searcher_with(response=None, error=None, key="k"):
    from app.services.resource_search import ResourceSearcher

    def post(url, headers, json, timeout):
        if error:
            raise error
        return response

    return ResourceSearcher(key, post=post)


# ---- resource search failure handling ---------------------------------------------------------------
def test_search_without_api_key():
    from app.services.resource_search import SearchStatus

    out = searcher_with(key="").search("q", "Math")
    assert out.status is SearchStatus.NO_API_KEY and out.resources == []


@pytest.mark.parametrize("status,expected", [(429, "rate_limited"), (401, "failed"), (500, "failed")])
def test_search_http_errors(status, expected):
    assert searcher_with(FakeResponse(status)).search("q", "Math").status.value == expected


def test_search_network_error_does_not_raise():
    assert searcher_with(error=TimeoutError("boom")).search("q", "Math").status.value == "failed"


def test_search_empty_results():
    assert searcher_with(FakeResponse(200, {"results": []})).search("q", "Math").status.value == "empty"


def test_search_filters_invalid_urls_and_dedupes():
    payload = {"results": [
        {"title": "Lecture 1", "url": "https://www.youtube.com/watch?v=abc", "content": "intro"},
        {"title": "Lecture 1 again", "url": "https://youtube.com/watch?v=abc&utm_source=x", "content": "dup"},
        {"title": "Bad", "url": "javascript:alert(1)", "content": "x"},
        {"title": "", "url": "https://example.com/a", "content": "no title"},
        {"title": "Notes", "url": "https://example.edu/notes.pdf", "content": "n" * 500},
    ]}
    out = searcher_with(FakeResponse(200, payload)).search("trig lectures", "Mathematics", "video", context="AKU-EB")
    assert out.status.value == "ok" and len(out.resources) == 2
    assert out.resources[0].resource_type.value == "video"
    assert out.resources[1].description.endswith("...") and len(out.resources[1].description) <= 245
    assert all(r.subject == "Mathematics" and r.why_recommended for r in out.resources)


# ---- orchestrator without an LLM --------------------------------------------------------------------
def test_orchestrator_without_llm_or_tavily(analyzer):
    from app.agents.orchestrator import AcademicOrchestrator
    from app.config import Settings

    report = AcademicOrchestrator(Settings(openrouter_api_key="", tavily_api_key=""), llm=None).run("s1", analyzer).model_dump()
    assert report["ai_generated"] is False
    assert report["weaknesses"][0]["subject"] == "Mathematics"
    assert report["recommendations"][0]["subject"] == "Mathematics" and report["recommendations"][0]["ai_generated"] is False
    assert "TAVILY_API_KEY" in report["resource_search_status"] and report["resources"] == []
    assert "Mathematics" in report["narrative_markdown"] and "trigonometric identities" in " ".join(
        report["recommendations"][0]["actions"])


def test_orchestrator_uses_search_results(analyzer):
    from app.agents.orchestrator import AcademicOrchestrator
    from app.config import Settings

    payload = {"results": [{"title": "Trig identities", "url": "https://example.org/trig", "content": "lesson"}]}
    orch = AcademicOrchestrator(Settings(tavily_api_key="k"), llm=None, searcher=searcher_with(FakeResponse(200, payload)))
    report = orch.run("s1", analyzer)
    assert report.resources and "Found" in report.resource_search_status


def test_research_queries_use_board_grade_subject_and_topic(profile):
    from app.agents.resource_researcher import deterministic_queries

    queries = deterministic_queries(profile, ["Mathematics"])
    assert queries and all("AKU-EB" in q.query and "HSSC 1" in q.query and "Mathematics" in q.query for q in queries)
    assert any("trigonometric identities" in q.query for q in queries)
    assert {q.kind for q in queries} == {"video"}  # student prefers video lectures only


def test_orchestrator_falls_back_when_llm_fails(analyzer):
    pytest.importorskip("langchain_core")
    from app.agents.orchestrator import AcademicOrchestrator
    from app.config import Settings

    class BrokenLLM:
        def bind_tools(self, tools):
            raise RuntimeError("401 invalid key")

        def with_structured_output(self, model, **kwargs):
            raise RuntimeError("401 invalid key")

        def invoke(self, messages):
            raise RuntimeError("401 invalid key")

    report = AcademicOrchestrator(Settings(tavily_api_key=""), llm=BrokenLLM()).run("s1", analyzer)
    assert report.ai_generated is False and any("unavailable" in n for n in report.ai_notes)
    assert report.recommendations  # a valid report is still produced


# ---- LangChain tools -------------------------------------------------------------------------------
def test_tools_wrap_all_thirteen_operations(analyzer):
    pytest.importorskip("langchain_core")
    from app.agents.tools import TOOL_NAMES, build_student_tools

    tools = {t.name: t for t in build_student_tools(analyzer)}
    assert list(tools) == TOOL_NAMES and len(tools) == 13
    for name, tool in tools.items():
        args = {"subject": "Mathematics"} if name == "get_subject_performance_details" else {}
        result = tool.invoke(args)
        json.dumps(result, default=str)
        assert isinstance(result, dict) and "error" not in result


def test_tool_inputs_are_validated_and_errors_are_data(analyzer):
    pytest.importorskip("langchain_core")
    from pydantic import ValidationError

    from app.agents.tools import build_student_tools

    tools = {t.name: t for t in build_student_tools(analyzer)}
    assert "error" in tools["get_subject_performance_details"].invoke({"subject": "Astrology"})
    with pytest.raises(ValidationError):
        tools["identify_weak_subjects"].invoke({"threshold": 150})
    assert tools["identify_weak_subjects"].invoke({"threshold": 70})["weak_threshold_percent"] == 70


def test_tool_loop_calls_tools_then_answers(analyzer):
    pytest.importorskip("langchain_core")
    from langchain_core.messages import AIMessage

    from app.agents.runner import run_tool_loop
    from app.agents.tools import build_student_tools

    class ScriptedLLM:
        def __init__(self):
            self.calls = 0

        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return AIMessage(content="", tool_calls=[{"name": "identify_weak_subjects", "args": {}, "id": "c1"}])
            tool_msgs = [m for m in messages if m.type == "tool"]
            assert tool_msgs and "Mathematics" in tool_msgs[0].content  # the tool result reached the model
            return AIMessage(content="Mathematics is weakest.")

    result = run_tool_loop(ScriptedLLM(), build_student_tools(analyzer), "sys", "question")
    assert result.text == "Mathematics is weakest." and result.tools_used == ["identify_weak_subjects"]


def test_fake_llm_pipeline_handles_tool_calls_structured_outputs_and_content_blocks(analyzer):
    pytest.importorskip("langchain_core")
    from langchain_core.messages import AIMessage

    from app.agents.academic_analyst import AnalystFindings
    from app.agents.improvement_advisor import AdvisorPlan, AdvisorRecommendation
    from app.agents.orchestrator import AcademicOrchestrator
    from app.agents.resource_researcher import ResearchPlan
    from app.config import Settings

    class FakeStructured:
        def __init__(self, model):
            self.model = model

        def invoke(self, _messages):
            if self.model is AnalystFindings:
                return AnalystFindings(summary="Calculated summary.", key_observations=["Mathematics is lowest."])
            if self.model is AdvisorPlan:
                return AdvisorPlan(recommendations=[
                    AdvisorRecommendation(subject="Mathematics", actions=["Practice weekly."], goal="Reach 70%.")])
            if self.model is ResearchPlan:
                return ResearchPlan(queries=[])
            raise AssertionError(f"Unexpected structured model: {self.model}")

    class FakeLLM:
        def __init__(self):
            self.tool_calls = 0

        def bind_tools(self, _tools):
            return self

        def invoke(self, messages):
            if any(getattr(message, "type", "") == "tool" for message in messages):
                return AIMessage(content=[{"type": "text", "text": "Tool-backed answer."}])
            if any(getattr(message, "type", "") == "human" for message in messages):
                return AIMessage(content=[{"type": "text", "text": "Report summary from blocks."}])
            self.tool_calls += 1
            return AIMessage(
                content="",
                tool_calls=[{"name": "calculate_overall_performance", "args": {}, "id": f"call-{self.tool_calls}"}],
            )

        def with_structured_output(self, model, **_kwargs):
            return FakeStructured(model)

    class FakeSearcher:
        configured = True

        def search(self, *_args, **_kwargs):
            from app.services.resource_search import ResourceSearchOutcome, SearchStatus

            return ResourceSearchOutcome(status=SearchStatus.EMPTY, resources=[])

    llm = FakeLLM()
    report = AcademicOrchestrator(
        Settings(openrouter_api_key="k", tavily_api_key="k"), llm=llm, searcher=FakeSearcher()
    ).run("s1", analyzer)
    assert report.ai_generated is True
    assert any("Report summary from blocks." in line for line in report.narrative_markdown.splitlines())

# ---- chatbot rules ---------------------------------------------------------------------------------
@pytest.mark.parametrize("question,tool", [
    ("Why is my mathematics performance lower than my physics performance?", "get_subject_performance_details"),
    ("Which subject should I prioritize?", "get_academic_improvement_priorities"),
    ("What are my biggest academic weaknesses?", "identify_weak_subjects"),
    ("How has my performance changed?", "compare_examinations"),
    ("Create a weekly study plan based on my results", "get_academic_improvement_priorities"),
    ("Explain my performance chart", "generate_visualization_data"),
])
def test_rule_based_chat_answers_from_data(analyzer, question, tool):
    from app.chatbot.rules import rule_based_reply

    reply, tools = rule_based_reply(question, analyzer, None)
    assert tool in tools and reply.strip()


def test_rule_chat_resources_need_a_report(analyzer):
    from app.chatbot.rules import rule_based_reply

    reply, _ = rule_based_reply("Recommend resources for my weakest subject", analyzer, None)
    assert "don't have" in reply

"""LLM question writing for practice quizzes.

The model supplies wording only. The service validates every returned question
before persistence and all scoring/mastery remains deterministic.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.quiz import QuizQuestionCreate, QuizQuestionType


class QuizQuestionSet(BaseModel):
    questions: list[QuizQuestionCreate] = Field(default_factory=list)


class TopicProposal(BaseModel):
    topics: list[str] = Field(default_factory=list, max_length=8)


def generate_questions(
    llm: Any, *, profile: dict[str, Any], subject: str, topic: str | None,
    difficulty_mix: dict[str, int], count: int, excluded_texts: set[str],
    question_type: QuizQuestionType = QuizQuestionType.MCQ,
) -> list[QuizQuestionCreate]:
    """Ask the configured model for one batch of practice questions."""
    from langchain_core.messages import HumanMessage, SystemMessage

    prompt = {
        "board": profile.get("board"), "grade": profile.get("grade"), "subject": subject,
        "topic": topic, "preferred_language": profile.get("preferred_language"),
        "difficulty_mix": difficulty_mix, "count": count,
        "question_type": question_type.value,
        "excluded_question_texts": sorted(excluded_texts),
    }
    system = (
        "Write practice questions for a school student. Return exactly the requested number when possible. "
        "Use the requested question_type. For mcq, provide exactly four distinct non-empty options and "
        "correct_index 0-3. For qa, provide options as [] and correct_index -1, plus a concise answer. "
        "Include a topic, difficulty (easy, medium or hard), and short explanation. "
        "Markdown and LaTeX are allowed in text, options, answer, and explanation. "
        "Do not copy excluded question text."
    )
    result: QuizQuestionSet = llm.with_structured_output(
        QuizQuestionSet, method="function_calling"
    ).invoke([SystemMessage(content=system), HumanMessage(content=json.dumps(prompt))])
    return result.questions


def propose_topics(llm: Any, *, profile: dict[str, Any], subject: str) -> list[str]:
    from langchain_core.messages import HumanMessage, SystemMessage

    result: TopicProposal = llm.with_structured_output(
        TopicProposal, method="function_calling"
    ).invoke([
        SystemMessage(content="Suggest up to 8 common syllabus topics. Return topic names only; do not invent marks."),
        HumanMessage(content=json.dumps({
            "board": profile.get("board"), "grade": profile.get("grade"), "subject": subject,
        })),
    ])
    return [topic.strip() for topic in result.topics if topic.strip()][:8]

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

PROFILE = {"name": "Quiz Student", "board": "AKU-EB", "country": "Pakistan",
           "grade": "HSSC 1", "academic_year": "2025-2026",
           "difficult_topics": {"Mathematics": ["Algebra"]}}
DATA = Path(__file__).parent / "data" / "sample_marksheet.csv"


@pytest.fixture
def quiz_client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'quiz.db').as_posix()}")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("TAVILY_API_KEY", "")
    from app.config import get_settings
    from app.core.database import reset_engine
    get_settings.cache_clear()
    reset_engine()
    from app.main import app
    with TestClient(app) as value:
        yield value
    reset_engine()
    get_settings.cache_clear()


def _student_with_results(client):
    student = client.post("/students/", json=PROFILE).json()
    import pandas as pd
    rows = pd.read_csv(DATA).fillna("").to_dict(orient="records")
    assert client.post(f"/students/{student['student_id']}/results/", json={"rows": rows}).status_code == 201
    return student


def _fake_model():
    from app.agents.quiz_generator import QuizQuestionSet
    from app.schemas.quiz import QuizDifficulty, QuizQuestionCreate

    class Structured:
        def invoke(self, _messages):
            return QuizQuestionSet(questions=[
                QuizQuestionCreate(text=f"Question {i}", options=["A", "B", "C", "D"],
                                   correct_index=i % 4, explanation="Because this is the rule.",
                                   topic="Algebra", difficulty=QuizDifficulty.MEDIUM)
                for i in range(5)
            ])

    class Fake:
        def with_structured_output(self, *_args, **_kwargs):
            return Structured()

    return Fake()


def test_quiz_api_hides_answers_scores_and_isolates_students(quiz_client, monkeypatch):
    from app.services import quiz_service

    monkeypatch.setattr(quiz_service, "get_llm", lambda _settings: _fake_model())
    first = _student_with_results(quiz_client)
    second = quiz_client.post("/students/", json={**PROFILE, "name": "Other"}).json()
    sid = first["student_id"]
    response = quiz_client.post(f"/students/{sid}/quiz/", json={
        "subject": "Mathematics", "topic": "Algebra", "n_questions": 5})
    assert response.status_code == 200, response.text
    session = response.json()
    assert all("correct_index" not in q and "explanation" not in q for q in session["questions"])
    assert quiz_client.get(f"/students/{second['student_id']}/quiz/{session['id']}/").status_code == 404
    submitted = quiz_client.post(f"/students/{sid}/quiz/{session['id']}/submit/",
                                 json={"answers": [0, 1, 2, 3, 0]})
    assert submitted.status_code == 200
    results = submitted.json()["questions"]
    assert all("correct_index" in q and "explanation" in q and "is_correct" in q for q in results)
    assert quiz_client.post(f"/students/{sid}/quiz/{session['id']}/submit/",
                            json={"answers": [0] * 5}).status_code == 409
    assert quiz_client.post(f"/students/{sid}/quiz/{session['id']}/questions/{results[0]['id']}/flag/").status_code == 200
    mastery = quiz_client.get(f"/students/{sid}/quiz/mastery/")
    assert mastery.status_code == 200 and mastery.json()[0]["attempts"] == 4


def test_quiz_unavailable_creates_no_partial_session(quiz_client):
    student = _student_with_results(quiz_client)
    sid = student["student_id"]
    response = quiz_client.post(f"/students/{sid}/quiz/",
                                json={"subject": "Mathematics", "n_questions": 5})
    assert response.status_code == 503
    assert "no questions were created" in response.json()["detail"]["message"].lower()
    assert quiz_client.get(f"/students/{sid}/quiz/mastery/").json() == []


def test_question_validation_rejects_duplicates():
    from app.schemas.quiz import QuizDifficulty, QuizQuestionCreate
    from app.services.quiz_service import _validate_questions

    question = QuizQuestionCreate(text="same", options=["A", "B", "C", "D"], correct_index=0,
                                  explanation="x", topic="Algebra", difficulty=QuizDifficulty.EASY)
    assert len(_validate_questions([question, question], set())) == 1


def test_quiz_rate_limit_has_actionable_error(quiz_client, monkeypatch):
    from app.agents.openrouter import OpenRouterAPIError
    from app.services import quiz_service

    monkeypatch.setattr(quiz_service, "get_llm", lambda _settings: _fake_model())

    def rate_limited(*_args, **_kwargs):
        raise OpenRouterAPIError("rate limited", status_code=429)

    monkeypatch.setattr(quiz_service, "generate_questions", rate_limited)
    student = _student_with_results(quiz_client)
    response = quiz_client.post(f"/students/{student['student_id']}/quiz/", json={
        "subject": "Mathematics", "topic": "Algebra", "n_questions": 5,
    })
    assert response.status_code == 503
    assert "rate limit" in response.json()["detail"]["message"].lower()

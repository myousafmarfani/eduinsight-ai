"""End-to-end API tests against a temporary SQLite database. No LLM or Tavily key is used."""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("httpx")

DATA = Path(__file__).parent / "data" / "sample_marksheet.csv"
PROFILE = {"name": "Ayesha Khan", "board": "AKU-EB", "country": "Pakistan", "grade": "HSSC 1",
           "academic_year": "2025-2026", "target_percentage": 75, "difficult_subjects": ["Mathematics"],
           "preferred_resources": ["Video lectures"]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    for name in ("UPLOAD_DIRECTORY", "REPORT_DIRECTORY", "CHART_DIRECTORY"):
        monkeypatch.setenv(name, str(tmp_path / name.lower()))
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("TAVILY_API_KEY", "")

    from app.config import get_settings
    from app.core.database import reset_engine

    get_settings.cache_clear()
    reset_engine()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
    reset_engine()
    get_settings.cache_clear()


def rows_from_csv():
    import pandas as pd

    df = pd.read_csv(DATA).fillna("")
    return df.to_dict(orient="records")


@pytest.fixture
def student(client):
    response = client.post("/students/", json=PROFILE)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def student_with_results(client, student):
    response = client.post(f"/students/{student['student_id']}/results/", json={"rows": rows_from_csv()})
    assert response.status_code == 201, response.text
    return student


def test_health_and_boards(client):
    body = client.get("/health/").json()
    assert body["status"] == "ok" and body["llm_configured"] is False and body["tavily_configured"] is False
    assert {"AKU-EB", "CAMBRIDGE", "OTHER"} <= {b["key"] for b in client.get("/boards/").json()}


def test_student_crud_and_validation(client, student):
    sid = student["student_id"]
    assert uuid.UUID(sid) and student["has_results"] is False
    assert client.get(f"/students/{sid}/").json()["name"] == "Ayesha Khan"
    assert client.get("/students/not-a-uuid/").status_code == 422
    assert client.get(f"/students/{uuid.uuid4()}/").status_code == 404
    assert client.post("/students/", json={**PROFILE, "name": ""}).status_code == 422
    assert client.delete(f"/students/{sid}/").status_code == 204
    assert client.get(f"/students/{sid}/").status_code == 404


def test_invalid_results_are_rejected_with_row_issues(client, student):
    rows = [{"exam": "E1", "subject": "Math", "obtained": 150, "total": 100},
            {"exam": "E1", "subject": "", "obtained": 50, "total": 100}]
    response = client.post(f"/students/{student['student_id']}/results/", json={"rows": rows})
    assert response.status_code == 422
    issues = response.json()["detail"]["issues"]
    assert {i["row"] for i in issues} == {1, 2}


def test_analysis_blocked_without_valid_data(client, student):
    sid = student["student_id"]
    for path in ("performance", "weaknesses", "visualizations"):
        assert client.get(f"/students/{sid}/{path}/").status_code == 422
    assert client.post(f"/students/{sid}/analyze/").status_code == 422


def test_performance_weaknesses_and_visualizations(client, student_with_results):
    sid = student_with_results["student_id"]
    perf = client.get(f"/students/{sid}/performance/").json()
    assert perf["metrics"]["overall_percentage"] == pytest.approx(69.43, abs=0.01) and perf["metrics"]["subject_count"] == 7
    weak = client.get(f"/students/{sid}/weaknesses/").json()
    assert weak["weak_subjects"][0]["subject"] == "Mathematics" and weak["threshold_explanation"]
    viz = client.get(f"/students/{sid}/visualizations/").json()
    assert all(c["available"] for c in viz["charts"]) and len(viz["charts"]) == 9
    png = client.get(viz["charts"][0]["url"])
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
    assert client.get(f"/students/{sid}/visualizations/nope/").status_code == 404


def test_full_report_tasks_and_chat_without_llm(client, student_with_results):
    sid = student_with_results["student_id"]
    assert client.get(f"/students/{sid}/report/").status_code == 404
    report = client.post(f"/students/{sid}/analyze/").json()
    assert report["ai_generated"] is False and report["recommendations"][0]["subject"] == "Mathematics"
    assert "TAVILY_API_KEY" in report["resource_search_status"]
    assert client.get(f"/students/{sid}/report/").json()["student_id"] == sid

    tasks = client.get(f"/students/{sid}/tasks/").json()
    assert tasks and not any(t["completed"] for t in tasks)
    done = client.patch(f"/students/{sid}/tasks/{tasks[0]['id']}/", json={"completed": True}).json()
    assert done["completed"] is True and done["completed_at"]
    client.post(f"/students/{sid}/analyze/")  # regenerating keeps completed tasks
    assert any(t["completed"] for t in client.get(f"/students/{sid}/tasks/").json())

    chat = client.post(f"/students/{sid}/chat/", json={"message": "Which subject should I prioritize?"}).json()
    assert "Mathematics" in chat["reply"] and chat["ai_generated"] is False and chat["session_id"]
    follow = client.post(f"/students/{sid}/chat/", json={"message": "How has my performance changed?",
                                                         "session_id": chat["session_id"]}).json()
    assert follow["session_id"] == chat["session_id"]


def test_students_are_isolated(client, student_with_results):
    other = client.post("/students/", json={**PROFILE, "name": "Other Student"}).json()
    oid = other["student_id"]
    assert client.get(f"/students/{oid}/performance/").status_code == 422  # no data leaks from the first student
    first = student_with_results["student_id"]
    client.post(f"/students/{first}/analyze/")
    tasks = client.get(f"/students/{first}/tasks/").json()
    assert client.patch(f"/students/{oid}/tasks/{tasks[0]['id']}/", json={"completed": True}).status_code == 404
    assert client.post(f"/students/{oid}/chat/", json={"message": "hi"}).status_code == 422


def test_upload_csv_returns_proposal_without_saving(client, student):
    sid = student["student_id"]
    response = client.post(f"/students/{sid}/marksheets/upload", files={"file": ("marks.csv", DATA.read_bytes())})
    body = response.json()
    assert response.status_code == 200 and body["requires_confirmation"] is True and len(body["rows"]) == 21
    assert client.get(f"/students/{sid}/results/").json()["examinations"] == []  # nothing stored yet


def test_upload_rejections(client, student):
    sid = student["student_id"]
    assert client.post(f"/students/{sid}/marksheets/upload", files={"file": ("x.exe", b"MZ")}).status_code == 400
    assert client.post(f"/students/{sid}/marksheets/upload", files={"file": ("x.pdf", b"not pdf")}).status_code == 400
    bad = client.post(f"/students/{sid}/marksheets/upload", files={"file": ("x.csv", b"foo,bar\n1,2\n")})
    assert bad.status_code == 422 and "subject" in bad.json()["detail"]["message"].lower()

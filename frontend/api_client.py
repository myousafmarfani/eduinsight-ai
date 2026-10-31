"""HTTP client for the FastAPI backend. The frontend talks to the backend ONLY through this module."""
from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


class ApiError(Exception):
    """A readable backend/connection error. `issues` holds row-level validation problems, if any."""

    def __init__(self, message: str, status: int = 0, issues: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.issues = issues or []


def _detail_to_error(status: int, body: Any) -> ApiError:
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, dict):
        return ApiError(detail.get("message", "Request failed."), status, detail.get("issues") or [])
    if isinstance(detail, str):
        return ApiError(detail, status)
    if isinstance(detail, list):  # FastAPI/Pydantic request validation errors
        parts = [f"{'.'.join(str(p) for p in e.get('loc', [])[1:])}: {e.get('msg', 'invalid')}" for e in detail]
        return ApiError("Some fields are invalid - " + "; ".join(parts), status)
    return ApiError(f"Request failed (HTTP {status}).", status)


def _request(method: str, path: str, timeout: float = 30, **kwargs: Any) -> requests.Response:
    try:
        response = requests.request(method, f"{API_BASE_URL}{path}", timeout=timeout, **kwargs)
    except requests.ConnectionError as exc:
        raise ApiError(f"Cannot reach the backend at {API_BASE_URL}. Start it with: uvicorn app.main:app --reload") from exc
    except requests.Timeout as exc:
        raise ApiError("The backend took too long to respond. Please try again.") from exc
    if response.status_code >= 400:
        try:
            body = response.json()
        except ValueError:
            body = None
        raise _detail_to_error(response.status_code, body)
    return response


def _json(method: str, path: str, **kwargs: Any) -> Any:
    response = _request(method, path, **kwargs)
    return response.json() if response.content else None


# ---- endpoints ----------------------------------------------------------------------------------
def health() -> dict[str, Any]:
    return _json("GET", "/health/", timeout=5)


def boards() -> list[dict[str, Any]]:
    return _json("GET", "/boards/")


def list_students() -> list[dict[str, Any]]:
    return _json("GET", "/students/")


def create_student(payload: dict[str, Any]) -> dict[str, Any]:
    return _json("POST", "/students/", json=payload)


def get_student(student_id: str) -> dict[str, Any]:
    return _json("GET", f"/students/{student_id}/")


def delete_student(student_id: str) -> None:
    _request("DELETE", f"/students/{student_id}/")


def upload_marksheet(student_id: str, filename: str, content: bytes, default_total: float | None,
                     exam_name: str | None) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if default_total:
        data["default_total"] = str(default_total)
    if exam_name:
        data["exam_name"] = exam_name
    return _json("POST", f"/students/{student_id}/marksheets/upload", timeout=120,
                 files={"file": (filename, content)}, data=data)


def save_results(student_id: str, rows: list[dict[str, Any]], default_total: float | None, replace: bool) -> dict[str, Any]:
    return _json("POST", f"/students/{student_id}/results/",
                 json={"rows": rows, "default_total": default_total, "replace_existing": replace})


def get_results(student_id: str) -> dict[str, Any]:
    return _json("GET", f"/students/{student_id}/results/")


def performance(student_id: str) -> dict[str, Any]:
    return _json("GET", f"/students/{student_id}/performance/")


def weaknesses(student_id: str) -> dict[str, Any]:
    return _json("GET", f"/students/{student_id}/weaknesses/")


def visualizations(student_id: str) -> dict[str, Any]:
    return _json("GET", f"/students/{student_id}/visualizations/", timeout=90)


def chart_image(url_path: str) -> bytes:
    return _request("GET", url_path, timeout=30).content


def analyze(student_id: str) -> dict[str, Any]:
    return _json("POST", f"/students/{student_id}/analyze/", timeout=420)


def report(student_id: str) -> dict[str, Any] | None:
    try:
        return _json("GET", f"/students/{student_id}/report/")
    except ApiError as exc:
        if exc.status == 404:
            return None
        raise


def tasks(student_id: str) -> list[dict[str, Any]]:
    return _json("GET", f"/students/{student_id}/tasks/")


def set_task_completed(student_id: str, task_id: str, completed: bool) -> dict[str, Any]:
    return _json("PATCH", f"/students/{student_id}/tasks/{task_id}/", json={"completed": completed})


def chat(student_id: str, message: str, session_id: str | None) -> dict[str, Any]:
    return _json("POST", f"/students/{student_id}/chat/", timeout=180,
                 json={"message": message, "session_id": session_id})


def quiz_topics(student_id: str, subject: str) -> dict[str, Any]:
    return _json("GET", f"/students/{student_id}/quiz/topics/", params={"subject": subject})


def start_quiz(student_id: str, subject: str, topic: str | None, n_questions: int,
               question_type: str = "mcq") -> dict[str, Any]:
    return _json("POST", f"/students/{student_id}/quiz/",
                 json={"subject": subject, "topic": topic, "n_questions": n_questions,
                       "question_type": question_type}, timeout=180)


def get_quiz(student_id: str, session_id: str) -> dict[str, Any]:
    return _json("GET", f"/students/{student_id}/quiz/{session_id}/")


def submit_quiz(student_id: str, session_id: str, answers: list[int | None]) -> dict[str, Any]:
    return _json("POST", f"/students/{student_id}/quiz/{session_id}/submit/",
                 json={"answers": answers})


def flag_quiz_question(student_id: str, session_id: str, question_id: str) -> dict[str, Any]:
    return _json("POST", f"/students/{student_id}/quiz/{session_id}/questions/{question_id}/flag/")


def quiz_mastery(student_id: str) -> list[dict[str, Any]]:
    return _json("GET", f"/students/{student_id}/quiz/mastery/")


def analytics_summary(student_id: str) -> dict[str, Any]:
    return _json("GET", f"/students/{student_id}/analytics/summary/")


def analytics_loss(student_id: str) -> dict[str, Any]:
    return _json("GET", f"/students/{student_id}/analytics/loss/")


def analytics_planner(student_id: str, target_percentage: float) -> dict[str, Any]:
    return _json("POST", f"/students/{student_id}/analytics/planner/", json={"target_percentage": target_percentage})


def analytics_what_if(student_id: str, changes: dict[str, float]) -> dict[str, Any]:
    return _json("POST", f"/students/{student_id}/analytics/what-if/", json={"changes": changes})


def analytics_weighted(student_id: str, weights: dict[str, float]) -> dict[str, Any]:
    return _json("POST", f"/students/{student_id}/analytics/weighted/", json={"weights": weights})


def analytics_pivot(student_id: str, index: str, columns: str, values: str, aggfunc: str) -> dict[str, Any]:
    return _json("POST", f"/students/{student_id}/analytics/pivot/",
                 json={"index": index, "columns": columns, "values": values, "aggfunc": aggfunc})


def analytics_export(student_id: str, file_format: str = "xlsx") -> bytes:
    return _request("GET", f"/students/{student_id}/analytics/export/?format={file_format}").content


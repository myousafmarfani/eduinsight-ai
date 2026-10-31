"""End-to-end API smoke test for a running Student Feedback Agent backend."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import uuid4

import requests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    session = requests.Session()

    def request(method: str, path: str, expected: int, **kwargs):
        response = session.request(method, base + path, timeout=180, **kwargs)
        assert response.status_code == expected, f"{method} {path}: {response.status_code} {response.text}"
        return response

    assert request("GET", "/health/", 200).json()["status"] == "ok"
    assert request("GET", "/boards/", 200).json()
    profile = {
        "name": f"Smoke Student {uuid4().hex[:8]}",
        "board": "Other",
        "country": "Pakistan",
        "grade": "Grade 10",
        "academic_year": "2026",
        "target_percentage": 80,
        "difficult_topics": {"Mathematics": ["Algebra"]},
    }
    student = request("POST", "/students/", 201, json=profile).json()
    student_id = student["student_id"]
    csv_path = Path(__file__).parents[1] / "sample_data" / "sample_marksheet.csv"
    try:
        upload = request(
            "POST",
            f"/students/{student_id}/marksheets/upload",
            200,
            files={"file": (csv_path.name, csv_path.read_bytes(), "text/csv")},
        ).json()
        assert upload["requires_confirmation"] and upload["rows"]
        rows = [
            {
                "exam": row["exam"],
                "exam_type": row["exam_type"],
                "subject": row["subject"],
                "obtained": row["obtained"],
                "total": row["total"],
                "grade": row["grade"],
            }
            for row in upload["rows"]
        ]
        results = request(
            "POST", f"/students/{student_id}/results/", 201,
            json={"rows": rows, "replace_existing": True},
        ).json()
        assert results["examinations"]
        performance = request("GET", f"/students/{student_id}/performance/", 200).json()
        assert performance["metrics"]["overall_percentage"] >= 0
        assert "weak_subjects" in request("GET", f"/students/{student_id}/weaknesses/", 200).json()
        charts = request("GET", f"/students/{student_id}/visualizations/", 200).json()
        if charts["charts"]:
            request("GET", charts["charts"][0]["url"], 200)
        report = request("POST", f"/students/{student_id}/analyze/", 200).json()
        assert "ai_generated" in report and "narrative_markdown" in report
        assert request("GET", f"/students/{student_id}/report/", 200).json()["student_id"] == student_id
        topics = request("GET", f"/students/{student_id}/quiz/topics/?subject=Mathematics", 200).json()
        assert topics["topics"]
        quiz = session.post(
            base + f"/students/{student_id}/quiz/",
            json={"subject": "Mathematics", "topic": topics["topics"][0]["topic"], "n_questions": 5},
            timeout=180,
        )
        assert quiz.status_code in (200, 503), f"POST quiz: {quiz.status_code} {quiz.text}"
        if quiz.status_code == 200:
            quiz_body = quiz.json()
            assert quiz_body["status"] == "in_progress"
            assert all("correct_index" not in q for q in quiz_body["questions"])
        else:
            assert quiz.status_code == 503
        tasks = request("GET", f"/students/{student_id}/tasks/", 200).json()
        if tasks:
            updated = request(
                "PATCH", f"/students/{student_id}/tasks/{tasks[0]['id']}/", 200,
                json={"completed": True},
            ).json()
            assert updated["completed"] is True
        session_id = str(uuid4())
        first = request(
            "POST", f"/students/{student_id}/chat/", 200,
            json={"message": "What is my overall percentage?", "session_id": session_id},
        ).json()
        second = request(
            "POST", f"/students/{student_id}/chat/", 200,
            json={"message": "What should I improve?", "session_id": session_id},
        ).json()
        assert first["session_id"] == second["session_id"] == session_id

        assert request("GET", "/students/not-a-uuid/", 422).status_code == 422
        assert request("GET", f"/students/{uuid4()}/", 404).status_code == 404
        invalid = dict(rows[0], obtained=999999)
        invalid_response = request(
            "POST", f"/students/{student_id}/results/", 422,
            json={"rows": [invalid], "replace_existing": False},
        ).json()
        assert invalid_response["detail"]["issues"]
        assert request(
            "POST", f"/students/{student_id}/marksheets/upload", 400,
            files={"file": ("malware.exe", b"MZ", "application/octet-stream")},
        ).status_code == 400
    finally:
        request("DELETE", f"/students/{student_id}/", 204)

    empty = request("POST", "/students/", 201, json={**profile, "name": "Empty Smoke"}).json()
    try:
        response = request("POST", f"/students/{empty['student_id']}/analyze/", 422)
        assert response.json()["detail"]["message"]
    finally:
        request("DELETE", f"/students/{empty['student_id']}/", 204)
    print("SMOKE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

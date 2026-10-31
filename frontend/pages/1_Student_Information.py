from __future__ import annotations

import api_client as api
import streamlit as st
import ui

ui.setup("Student Information")
st.title("Student information")

try:
    boards = api.boards()
except api.ApiError as exc:
    ui.show_error(exc)
    st.stop()

RESOURCE_CHOICES = ["Video lectures", "Practice questions and past papers", "Reading notes and guides"]


def parse_topics(text: str) -> dict[str, list[str]]:
    """Lines like 'Mathematics: trigonometric identities, logarithms' -> {subject: [topics]}."""
    topics: dict[str, list[str]] = {}
    for line in text.splitlines():
        if ":" in line:
            subject, _, rest = line.partition(":")
            items = [t.strip() for t in rest.split(",") if t.strip()]
            if subject.strip() and items:
                topics[subject.strip()] = items
    return topics


with st.form("student_form"):
    left, right = st.columns(2)
    name = left.text_input("Full name")
    board_name = right.selectbox("Education board", [b["name"] for b in boards])
    country = left.text_input("Country", value="Pakistan")
    grade = right.text_input("Class / grade", placeholder="e.g. HSSC 1, Grade 10")
    academic_year = left.text_input("Academic year", placeholder="e.g. 2025-2026")
    school = right.text_input("School (optional)")
    target = left.number_input("Target percentage (0 = none)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
    language = right.text_input("Preferred resource language (optional)", placeholder="e.g. English, Urdu")
    difficult = st.text_input("Subjects you find difficult (comma-separated)", placeholder="Mathematics, Chemistry")
    topics = st.text_area("Specific topics you find hard (optional, one line per subject)",
                          placeholder="Mathematics: trigonometric identities, logarithms", height=80)
    preferred = st.multiselect("Preferred learning resources", RESOURCE_CHOICES, default=RESOURCE_CHOICES)
    goals = st.text_area("Academic goals (optional)", height=80)
    submitted = st.form_submit_button("Save student")

if submitted:
    board = next(b for b in boards if b["name"] == board_name)
    payload = {
        "name": name, "board": board["key"], "country": country, "grade": grade, "academic_year": academic_year,
        "school_name": school or None, "goals": goals or None, "target_percentage": target or None,
        "difficult_subjects": [s.strip() for s in difficult.split(",") if s.strip()],
        "difficult_topics": parse_topics(topics), "preferred_resources": preferred,
        "preferred_language": language or None,
    }
    try:
        student = api.create_student(payload)
        ui.select_student(student)
        st.success(f"Saved {student['name']}. Next, add your marks.")
        if board["notes"]:
            st.info(f"{board['name']}: {board['notes']}")
        ui.page_link("pages/2_Upload_Marksheet.py", label="Continue to marks")
    except api.ApiError as exc:
        ui.show_error(exc)

st.divider()
st.subheader("Saved students")
try:
    students = api.list_students()
except api.ApiError as exc:
    ui.show_error(exc)
    students = []
if not students:
    st.caption("Nothing saved yet.")
for s in students:
    cols = st.columns([4, 1, 1])
    cols[0].markdown(f"**{s['name']}** - {s['board']}, {s['grade']} ({'marks saved' if s['has_results'] else 'no marks yet'})")
    if cols[1].button("Select", key=f"sel_{s['student_id']}"):
        ui.select_student(s)
        st.rerun()
    with cols[2].popover("Delete"):
        st.write("This permanently deletes this student's marks, reports, tasks and chats.")
        if st.button("Delete everything", key=f"del_{s['student_id']}"):
            try:
                api.delete_student(s["student_id"])
                if st.session_state.get("student", {}).get("student_id") == s["student_id"]:
                    st.session_state.pop("student", None)
                ui.invalidate(s["student_id"])
                st.rerun()
            except api.ApiError as exc:
                ui.show_error(exc)

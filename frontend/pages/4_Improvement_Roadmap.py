from __future__ import annotations

import api_client as api
import streamlit as st
import ui

ui.setup("Improvement Roadmap")
student = ui.require_student()
sid = student["student_id"]
st.title("Improvement roadmap")

try:
    tasks = api.tasks(sid)
    report = api.report(sid)
except api.ApiError as exc:
    ui.show_error(exc)
    st.stop()

if not tasks:
    st.info("Your roadmap is created when you generate the AI report.")
    ui.page_link("pages/3_Academic_Dashboard.py", label="Go to the dashboard")
    st.stop()


def toggle(task_id: str) -> None:
    try:
        api.set_task_completed(sid, task_id, st.session_state[f"task_{task_id}"])
    except api.ApiError as exc:
        st.session_state["task_error"] = exc.message


if st.session_state.pop("task_error", None):
    st.error("Could not update the task. Please try again.")

done = sum(t["completed"] for t in tasks)
st.progress(done / len(tasks), text=f"{done} of {len(tasks)} tasks completed")

goals = {r["subject"]: r for r in (report["recommendations"] if report else [])}
for subject in dict.fromkeys(t["subject"] for t in tasks):
    items = [t for t in tasks if t["subject"] == subject]
    st.subheader(subject)
    st.markdown(ui.pill(items[0]["priority"]), unsafe_allow_html=True)
    if subject in goals:
        st.caption(goals[subject]["goal"])
    for t in items:
        st.checkbox(t["description"], value=t["completed"], key=f"task_{t['id']}", on_change=toggle, args=(t["id"],))

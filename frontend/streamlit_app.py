"""Home page.  Run:  streamlit run frontend/streamlit_app.py"""
from __future__ import annotations

import api_client as api
import streamlit as st
import ui

ui.setup("Home")
st.title("Student Feedback Agent")
st.write("Upload or enter your exam results, see where you stand, and get a study plan with learning resources.")

try:
    status = api.health()
except api.ApiError as exc:
    ui.show_error(exc)
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("AI model", "Connected" if status["llm_configured"] else "Not configured")
c2.metric("Resource search", "Connected" if status["tavily_configured"] else "Not configured")
c3.metric("Marksheet OCR", "Available" if status["ocr_available"] else "Not installed")
if not status["llm_configured"]:
    st.caption("Without an AI key, reports and chat use built-in templates and rules. All numbers are still calculated from your marks.")

st.subheader("Choose a student")
try:
    students = api.list_students()
except api.ApiError as exc:
    ui.show_error(exc)
    st.stop()

if students:
    labels = {f"{s['name']} - {s['board']}, {s['grade']}": s for s in students}
    current = st.session_state.get("student", {}).get("student_id")
    keys = list(labels)
    index = next((i for i, k in enumerate(keys) if labels[k]["student_id"] == current), 0)
    choice = st.selectbox("Existing students", keys, index=index)
    if st.button("Use this student"):
        ui.select_student(labels[choice])
        st.rerun()
else:
    st.info("No students yet. Create one to get started.")

st.divider()
st.subheader("Steps")
ui.page_link("pages/1_Student_Information.py", label="1. Student information")
ui.page_link("pages/2_Upload_Marksheet.py", label="2. Enter or upload marks")
ui.page_link("pages/3_Academic_Dashboard.py", label="3. Academic dashboard and report")
ui.page_link("pages/4_Improvement_Roadmap.py", label="4. Improvement roadmap")
ui.page_link("pages/5_AI_Academic_Chat.py", label="5. Ask the academic advisor")
ui.page_link("pages/6_Practice_Quiz.py", label="6. Practice quiz")
ui.page_link("pages/7_Data_Analysis_Lab.py", label="7. Data analysis lab")

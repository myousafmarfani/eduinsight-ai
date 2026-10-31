from __future__ import annotations

import streamlit as st

try:
    import api_client as api
    import ui
except ModuleNotFoundError:
    from frontend import api_client as api
    from frontend import ui
from frontend.components import quiz as quiz_ui

ui.setup("Practice Quiz")
student = ui.require_student()
sid = student["student_id"]
st.title("Adaptive practice quiz")
st.caption("AI-generated questions may contain mistakes. Flag any question that looks wrong.")

try:
    performance = api.performance(sid)
except api.ApiError as exc:
    ui.show_error(exc)
    st.stop()

subjects = [row["subject"] for row in performance["subjects"]]
subject = st.selectbox("Subject", subjects)
try:
    topic_data = ui.get_cached(f"quiz_topics:{subject}", sid, lambda: api.quiz_topics(sid, subject))
except api.ApiError as exc:
    if exc.status != 503:
        ui.show_error(exc)
    topic_data = {"topics": []}
topic_options = ["Any topic"] + [f"{row['topic']} ({row['label']})" for row in topic_data["topics"]]
topic_choice = st.selectbox("Topic", topic_options)
suggested_topic = None if topic_choice == "Any topic" else topic_choice.rsplit(" (", 1)[0]
topic_description = st.text_area(
    "Describe the topic (optional)",
    value=suggested_topic or "",
    max_chars=120,
    placeholder="e.g. Quadratic equations, including the discriminant and graphing",
    help="Be specific so the questions match what you want to practise.",
)
topic = topic_description.strip() or None
length = st.number_input("Number of questions", min_value=1, max_value=20, value=5, step=1)
question_type = st.radio("Question format", ["MCQs", "Q/A"], horizontal=True)
question_type_value = "mcq" if question_type == "MCQs" else "qa"
if topic:
    with st.expander("Topic preview", expanded=False):
        st.markdown(topic)

session = st.session_state.get("quiz_session")
if session is None:
    if st.button("Start quiz", type="primary"):
        try:
            st.session_state["quiz_session"] = api.start_quiz(
                sid, subject, topic, int(length), question_type_value
            )
            st.session_state["quiz_answers"] = []
            st.rerun()
        except api.ApiError as exc:
            ui.show_error(exc)
else:
    questions = session["questions"]
    if session["status"] == "completed":
        st.success(f"Score: {session['score']:.1f}%")
        for result in questions:
            st.markdown(f"**{result['text']}**")
            if result["question_type"] == "qa":
                st.markdown(f"**Your answer:** {result.get('selected_text') or '_No answer_'}")
                st.markdown(f"**Expected answer:** {result.get('answer') or 'Not available'}")
            st.markdown(result["explanation"])
            if st.button("Flag as wrong", key=f"flag_{result['id']}"):
                try:
                    api.flag_quiz_question(sid, session["id"], result["id"])
                    st.success("Question flagged and excluded from mastery.")
                except api.ApiError as exc:
                    ui.show_error(exc)
    else:
        index = len(st.session_state.get("quiz_answers", []))
        if index < len(questions):
            question = questions[index]
            st.progress(index / len(questions), text=f"Question {index + 1} of {len(questions)}")
            st.markdown(f"**{question['text']}**")
            if question["question_type"] == "qa":
                selected_text = st.text_area(
                    "Your answer", key=f"answer_{question['id']}",
                    placeholder="Explain in your own words...",
                )
                selected = None
            else:
                labels = [f"Option {index + 1}" for index in range(len(question["options"]))]
                for label, option in zip(labels, question["options"]):
                    st.markdown(f"**{label}:** {option}")
                selected_label = st.radio("Choose one", labels, key=f"answer_{question['id']}")
                selected = question["options"][labels.index(selected_label)]
                selected_text = None
            if st.button("Next" if index + 1 < len(questions) else "Submit quiz", type="primary"):
                answers = st.session_state.setdefault("quiz_answers", [])
                answers.append(
                    selected_text if question["question_type"] == "qa"
                    else question["options"].index(selected)
                )
                if len(answers) == len(questions):
                    try:
                        st.session_state["quiz_session"] = api.submit_quiz(sid, session["id"], answers)
                        ui.invalidate(sid, "quiz_mastery")
                        st.rerun()
                    except api.ApiError as exc:
                        ui.show_error(exc)
                else:
                    st.rerun()

st.divider()
st.subheader("Topic mastery")
try:
    quiz_ui.mastery_chart(ui.get_cached("quiz_mastery", sid, lambda: api.quiz_mastery(sid)))
except api.ApiError as exc:
    ui.show_error(exc)

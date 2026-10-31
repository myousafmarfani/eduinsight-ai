from __future__ import annotations

import api_client as api
import streamlit as st
import ui

ui.setup("Academic Chat")
student = ui.require_student()
sid = student["student_id"]
st.title("Academic advisor")
st.caption(f"Answering questions about {student['name']}'s results only.")

SUGGESTIONS = [
    "Which subject should I prioritize?", "What are my biggest academic weaknesses?", "How has my performance changed?",
    "Create a weekly study plan based on my results.", "Recommend resources for my weakest subject.",
    "Explain my performance chart.",
]

# one conversation per student, so histories can never mix
chats = st.session_state.setdefault("chats", {})
chat = chats.setdefault(sid, {"session_id": None, "messages": []})

with st.sidebar:
    if st.button("Start a new conversation"):
        chats[sid] = {"session_id": None, "messages": []}
        st.rerun()

pending = None
if not chat["messages"]:
    st.write("Try one of these:")
    cols = st.columns(2)
    for i, q in enumerate(SUGGESTIONS):
        if cols[i % 2].button(q, key=f"sugg_{i}"):
            pending = q

for m in chat["messages"]:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("caption"):
            st.caption(m["caption"])

prompt = st.chat_input("Ask about your marks, weak subjects, progress or study plan") or pending
if prompt:
    chat["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..."):
                reply = api.chat(sid, prompt, chat["session_id"])
            chat["session_id"] = reply["session_id"]
            caption_parts = []
            if reply["tools_used"]:
                caption_parts.append("Data used: " + ", ".join(reply["tools_used"]))
            if reply.get("note"):
                caption_parts.append(reply["note"])
            entry = {"role": "assistant", "content": reply["reply"], "caption": " | ".join(caption_parts)}
        except api.ApiError as exc:
            entry = {"role": "assistant", "content": f"Sorry, I couldn't answer: {exc.message}"}
        st.markdown(entry["content"])
        if entry.get("caption"):
            st.caption(entry["caption"])
    chat["messages"].append(entry)

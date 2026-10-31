from __future__ import annotations

import api_client as api
import pandas as pd
import streamlit as st
import ui

ui.setup("Marks")
student = ui.require_student()
sid = student["student_id"]
st.title("Marks")
st.caption("List earlier examinations first. The last examination is treated as the current one.")

COLUMNS = ["exam", "exam_type", "subject", "obtained", "total", "grade"]
EXAM_TYPES = ["", "Unit test", "Midterm", "Mock", "Final", "Other"]
state_key = f"marks_{sid}"
if state_key not in st.session_state:
    st.session_state[state_key] = pd.DataFrame(columns=COLUMNS + ["confidence"])


def add_rows(rows: list[dict]) -> None:
    current = st.session_state[state_key]
    st.session_state[state_key] = pd.concat([current, pd.DataFrame(rows)], ignore_index=True)


manual, upload = st.tabs(["Enter manually", "Upload a marksheet"])

with manual:
    with st.form("quick_add"):
        c1, c2, c3 = st.columns(3)
        exam = c1.text_input("Examination name", placeholder="e.g. Mid-Term 2025")
        exam_type = c2.selectbox("Type", EXAM_TYPES)
        total = c3.number_input("Total marks per subject", min_value=1.0, value=100.0)
        subjects = st.text_input("Subjects (comma-separated)", placeholder="Mathematics, Physics, Chemistry, English")
        if st.form_submit_button("Add subjects to the table"):
            names = [s.strip() for s in subjects.split(",") if s.strip()]
            if not exam.strip() or not names:
                st.warning("Enter an examination name and at least one subject.")
            else:
                add_rows([{"exam": exam.strip(), "exam_type": exam_type, "subject": n, "obtained": None, "total": total,
                           "grade": "", "confidence": ""} for n in names])
                st.rerun()
    st.caption("Then fill in the obtained marks in the table below. Repeat for each previous examination.")

with upload:
    file = st.file_uploader("CSV, Excel, PDF or image", type=["csv", "xlsx", "pdf", "png", "jpg", "jpeg"])
    c1, c2 = st.columns(2)
    default_total = c1.number_input("Default total marks (used only if the file has none)", min_value=0.0, value=0.0)
    exam_name = c2.text_input("Examination name (if the file has none)")
    st.caption("CSV/Excel: use columns subject, obtained, total (optional: exam, exam_type, grade). "
               "PDFs and images are read as text/OCR, so layouts vary - you will review everything before it is saved.")
    if file and st.button("Read file"):
        try:
            with st.spinner("Reading the file..."):
                result = api.upload_marksheet(sid, file.name, file.getvalue(), default_total or None, exam_name or None)
            st.session_state[state_key] = pd.DataFrame([{**{c: r.get(c) for c in COLUMNS}, "confidence": r["confidence"]}
                                                        for r in result["rows"]])
            for w in result["warnings"]:
                st.warning(w)
            for issue in result["issues"]:
                (st.warning if issue["severity"] == "warning" else st.error)(
                    f"Row {issue['row'] or '-'}: {issue['message']}")
            st.success(f"Read {len(result['rows'])} rows. Check them in the table below, correct anything wrong, then save.")
        except api.ApiError as exc:
            ui.show_error(exc)

st.subheader("Review and save")
if st.session_state[state_key].empty:
    st.info("Add subjects manually or read a file to start.")
edited = st.data_editor(
    st.session_state[state_key], num_rows="dynamic", hide_index=True, key=f"editor_{sid}",
    column_config={
        "exam": st.column_config.TextColumn("Examination"),
        "exam_type": st.column_config.SelectboxColumn("Type", options=EXAM_TYPES),
        "subject": st.column_config.TextColumn("Subject"),
        "obtained": st.column_config.NumberColumn("Obtained", min_value=0.0),
        "total": st.column_config.NumberColumn("Total", min_value=0.0),
        "grade": st.column_config.TextColumn("Printed grade (optional)"),
        "confidence": st.column_config.TextColumn("Read confidence", disabled=True,
                                                   help="'medium' means the layout was ambiguous - check this row."),
    })

replace = st.checkbox("Replace all previously saved results", value=True)
if st.button("Validate and save", type="primary"):
    rows = []
    for rec in edited[COLUMNS].to_dict(orient="records"):
        clean = {k: (None if pd.isna(v) or v == "" else v) for k, v in rec.items()}
        if any(v is not None for v in clean.values()):
            rows.append(clean)
    if not rows:
        st.warning("The table is empty.")
    else:
        try:
            api.save_results(sid, rows, None, replace)
            ui.invalidate(sid)
            st.session_state[state_key] = edited
            st.success("Results saved.")
            ui.page_link("pages/3_Academic_Dashboard.py", label="Open the dashboard")
        except api.ApiError as exc:
            ui.show_error(exc)

with st.expander("Saved results"):
    try:
        saved = api.get_results(sid)
        if not saved["examinations"]:
            st.caption("Nothing saved yet.")
        for exam_rec in saved["examinations"]:
            st.markdown(f"**{exam_rec['exam_name']}** {exam_rec.get('exam_type') or ''}")
            st.dataframe(exam_rec["subjects"], hide_index=True)
    except api.ApiError as exc:
        ui.show_error(exc)

"""Shared page setup: theme, sidebar, student context, error display and a small data cache."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st
from streamlit.errors import StreamlitPageNotFoundError

try:
    import api_client as api
except ModuleNotFoundError:
    from frontend import api_client as api

INK, TEAL, AMBER, ROSE = "#1F2A44", "#0E7C86", "#D98E04", "#B83A3A"

_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap');
html, body, [class*="css"], .stMarkdown, .stButton button, .stTextInput input {{ font-family: 'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif; }}
h1, h2, h3 {{ color: {INK}; letter-spacing: -0.01em; }}
[data-testid="stSidebar"] {{ background: #F2F5F7; border-right: 1px solid #E1E6EC; }}
[data-testid="stMetric"] {{ background: #FFFFFF; border: 1px solid #E1E6EC; border-radius: 6px; padding: 14px 16px; }}
[data-testid="stMetricLabel"] {{ color: #5B667A; }}
.pill {{ display:inline-block; padding: 1px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; color: #fff; }}
.pill.high {{ background: {ROSE}; }} .pill.medium {{ background: {AMBER}; }} .pill.low {{ background: #5B667A; }}
.res-card {{ border: 1px solid #E1E6EC; border-left: 4px solid {TEAL}; border-radius: 6px; padding: 12px 14px; margin-bottom: 12px; background: #fff; }}
.res-card a {{ color: {INK}; font-weight: 600; text-decoration: none; }}
.res-card a:hover {{ text-decoration: underline; }}
.res-meta {{ color: #5B667A; font-size: 0.82rem; margin: 2px 0 6px; }}
.res-why {{ color: #5B667A; font-size: 0.82rem; font-style: italic; }}
.issue {{ color: {ROSE}; }}
:focus-visible {{ outline: 2px solid {TEAL}; outline-offset: 2px; }}
</style>
"""


def setup(title: str, icon: str = "") -> None:
    """Must be the first Streamlit call of every page."""
    st.set_page_config(page_title=f"{title} - Student Feedback Agent", page_icon=icon or None, layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("### Student Feedback Agent")
        student = st.session_state.get("student")
        if student:
            st.markdown(f"**{student['name']}**  \n{student['board']} - {student['grade']}")
        else:
            st.caption("No student selected.")


def show_error(error: api.ApiError) -> None:
    st.error(error.message)
    if error.issues:
        rows = [{"Row": i.get("row") or "-", "Field": i.get("field"), "Problem": i.get("message"),
                 "Type": i.get("severity")} for i in error.issues]
        st.dataframe(rows, hide_index=True)


def page_link(page: str, label: str) -> None:
    """Render a page link, remaining safe when a page is run directly by AppTest."""
    try:
        st.page_link(page, label=label)
    except StreamlitPageNotFoundError:
        st.caption(label)


def require_student() -> dict[str, Any]:
    """Return the selected student or stop the page with guidance."""
    student = st.session_state.get("student")
    if not student:
        st.info("Choose or create a student first.")
        page_link("pages/1_Student_Information.py", label="Go to Student Information")
        st.stop()
    return student


def select_student(student: dict[str, Any]) -> None:
    st.session_state["student"] = student


def pill(priority: str) -> str:
    return f'<span class="pill {priority}">{priority} priority</span>'


def get_cached(name: str, student_id: str, loader: Callable[[], Any]) -> Any:
    """Per-student session cache so reruns do not hit the backend every time."""
    cache = st.session_state.setdefault("_cache", {})
    key = (student_id, name)
    if key not in cache:
        cache[key] = loader()
    return cache[key]


def invalidate(student_id: str, *names: str) -> None:
    cache = st.session_state.setdefault("_cache", {})
    for key in [k for k in cache if k[0] == student_id and (not names or k[1] in names)]:
        cache.pop(key)

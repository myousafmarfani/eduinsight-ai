"""Interactive Plotly charts built from the backend's visualization data, plus the static PNG gallery."""
from __future__ import annotations

from typing import Any

import streamlit as st

try:
    import api_client as api
except ModuleNotFoundError:
    from frontend import api_client as api

try:
    import plotly.graph_objects as go
except ImportError:  # plotly is optional; the static charts still work
    go = None

INK, TEAL, AMBER, ROSE, GREY = "#1F2A44", "#0E7C86", "#D98E04", "#B83A3A", "#8A94A6"


def _colors(data: dict[str, Any]) -> list[str]:
    weak, strong = set(data["weak_subjects"]), set(data["strong_subjects"])
    return [ROSE if s["subject"] in weak else TEAL if s["subject"] in strong else GREY for s in data["subjects"]]


def percentage_bar(data: dict[str, Any]):
    fig = go.Figure(go.Bar(x=[s["subject"] for s in data["subjects"]], y=[s["percentage"] for s in data["subjects"]],
                           marker_color=_colors(data), text=[f"{s['percentage']:.1f}%" for s in data["subjects"]],
                           textposition="outside", hovertemplate="%{x}: %{y:.1f}%<extra></extra>"))
    fig.add_hline(y=data["pass_mark"], line_dash="dot", line_color=INK, annotation_text="Board pass mark")
    if data.get("target_percentage"):
        fig.add_hline(y=data["target_percentage"], line_dash="dash", line_color=AMBER, annotation_text="Your target")
    fig.update_layout(title="Percentage by subject", yaxis={"range": [0, 110], "title": "%"}, margin={"t": 50, "b": 20})
    return fig


def radar(data: dict[str, Any]):
    names = [s["subject"] for s in data["subjects"]]
    values = [s["percentage"] for s in data["subjects"]]
    fig = go.Figure(go.Scatterpolar(r=values + values[:1], theta=names + names[:1], fill="toself", line_color=TEAL, name="Result"))
    if data.get("target_percentage"):
        fig.add_trace(go.Scatterpolar(r=[data["target_percentage"]] * (len(names) + 1), theta=names + names[:1],
                                      line={"color": AMBER, "dash": "dash"}, name="Target"))
    fig.update_layout(title="Subject profile", polar={"radialaxis": {"range": [0, 100]}}, margin={"t": 60})
    return fig


def exam_comparison(data: dict[str, Any]):
    comp = data["comparison"]
    rows = sorted(comp["subject_changes"], key=lambda r: r["subject"])
    fig = go.Figure([
        go.Bar(name=comp["previous_exam"], x=[r["subject"] for r in rows], y=[r["previous_percentage"] for r in rows], marker_color=GREY),
        go.Bar(name=comp["current_exam"], x=[r["subject"] for r in rows], y=[r["current_percentage"] for r in rows], marker_color=TEAL)])
    fig.update_layout(barmode="group", title="Examination comparison", yaxis={"range": [0, 105], "title": "%"}, margin={"t": 50})
    return fig


def trend(data: dict[str, Any]):
    fig = go.Figure()
    for subject, hist in data["subject_history"].items():
        if len(hist) >= 2:
            fig.add_trace(go.Scatter(x=[h["exam"] for h in hist], y=[h["percentage"] for h in hist], mode="lines+markers", name=subject))
    fig.add_trace(go.Scatter(x=[e["exam"] for e in data["exams"]], y=[e["percentage"] for e in data["exams"]],
                             mode="lines+markers", name="Overall", line={"color": INK, "width": 4}))
    fig.update_layout(title="Performance trend", yaxis={"range": [0, 105], "title": "%"}, margin={"t": 50})
    return fig


def show_interactive(data: dict[str, Any]) -> None:
    if go is None:
        st.info("Install plotly (pip install plotly) for interactive charts. The static charts are available in the next tab.")
        return
    st.plotly_chart(percentage_bar(data))
    left, right = st.columns(2)
    if len(data["subjects"]) >= 3:
        left.plotly_chart(radar(data))
    else:
        left.info("A radar chart needs at least 3 subjects.")
    comp = data["comparison"]
    if comp["available"] and comp["subject_changes"]:
        right.plotly_chart(exam_comparison(data))
    else:
        right.info(comp.get("reason", "Add a previous examination to see a comparison."))
    if len(data["exams"]) >= 3:
        st.plotly_chart(trend(data))
    else:
        st.caption("A trend line needs at least 3 examinations, so none is drawn.")


def show_static(student_id: str, charts: list[dict[str, Any]]) -> None:
    """Matplotlib/Seaborn PNGs rendered by the backend."""
    available = [c for c in charts if c["available"]]
    for chart in available:
        key = f"png:{chart['id']}"
        cache = st.session_state.setdefault("_png", {})
        if (student_id, key) not in cache:
            try:
                cache[(student_id, key)] = api.chart_image(chart["url"])
            except api.ApiError as exc:
                st.warning(f"{chart['title']}: {exc.message}")
                continue
        st.image(cache[(student_id, key)], caption=chart["title"])
    skipped = [c for c in charts if not c["available"]]
    if skipped:
        with st.expander("Charts not shown"):
            for c in skipped:
                st.write(f"**{c['title']}:** {c['reason']}")

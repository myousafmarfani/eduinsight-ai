"""Interactive graph builders for the student Data Analysis Lab."""
from __future__ import annotations

from typing import Any

import streamlit as st

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError:  # pragma: no cover - optional UI dependency
    go = None
    make_subplots = None

INK, TEAL, AMBER, ROSE, GREY = "#1F2A44", "#0E7C86", "#D98E04", "#B83A3A", "#8A94A6"


def available() -> bool:
    return go is not None


def _layout(fig: Any, title: str, y_title: str = "") -> Any:
    fig.update_layout(title=title, template="plotly_white", height=430, margin={"t": 65, "b": 45, "l": 55, "r": 30},
                      font={"color": INK}, yaxis_title=y_title, legend={"orientation": "h", "y": -0.2})
    return fig


def subject_overview(viz: dict[str, Any]) -> Any:
    names = [row["subject"] for row in viz["subjects"]]
    values = [row["percentage"] for row in viz["subjects"]]
    colors = [ROSE if name in viz["weak_subjects"] else TEAL if name in viz["strong_subjects"] else GREY for name in names]
    fig = go.Figure(go.Bar(x=names, y=values, marker_color=colors, text=[f"{v:.1f}%" for v in values],
                           textposition="outside", hovertemplate="%{x}: %{y:.1f}%<extra></extra>"))
    fig.add_hline(y=viz["pass_mark"], line_dash="dot", line_color=INK, annotation_text="Pass mark")
    if viz.get("target_percentage") is not None:
        fig.add_hline(y=viz["target_percentage"], line_dash="dash", line_color=AMBER, annotation_text="Target")
    fig.update_yaxes(range=[0, 110])
    return _layout(fig, "Current subject performance", "Percentage")


def subject_radar(viz: dict[str, Any]) -> Any:
    names = [row["subject"] for row in viz["subjects"]]
    values = [row["percentage"] for row in viz["subjects"]]
    fig = go.Figure(go.Scatterpolar(r=values + values[:1], theta=names + names[:1], fill="toself",
                                    line={"color": TEAL}, name="Current"))
    if viz.get("target_percentage") is not None:
        fig.add_trace(go.Scatterpolar(r=[viz["target_percentage"]] * (len(names) + 1),
                                      theta=names + names[:1], line={"color": AMBER, "dash": "dash"}, name="Target"))
    fig.update_layout(title="Subject profile radar", template="plotly_white", height=430,
                      polar={"radialaxis": {"range": [0, 100]}}, margin={"t": 65, "b": 30})
    return fig


def distribution(viz: dict[str, Any]) -> Any:
    values = [row["percentage"] for row in viz["subjects"]]
    fig = go.Figure(go.Histogram(x=values, xbins={"start": 0, "end": 110, "size": 10},
                                 marker_color=TEAL, opacity=0.85))
    fig.add_vline(x=viz["average_percentage"], line_dash="dash", line_color=AMBER, annotation_text="Mean")
    return _layout(fig, "Distribution of subject percentages", "Number of subjects")


def comparison(viz: dict[str, Any]) -> Any | None:
    comp = viz["comparison"]
    if not comp["available"] or not comp["subject_changes"]:
        return None
    rows = sorted(comp["subject_changes"], key=lambda row: row["subject"])
    fig = go.Figure([
        go.Bar(name=comp["previous_exam"], x=[r["subject"] for r in rows],
               y=[r["previous_percentage"] for r in rows], marker_color=GREY),
        go.Bar(name=comp["current_exam"], x=[r["subject"] for r in rows],
               y=[r["current_percentage"] for r in rows], marker_color=TEAL),
    ])
    fig.update_layout(barmode="group")
    fig.update_yaxes(range=[0, 110])
    return _layout(fig, "Subject comparison across the two latest exams", "Percentage")


def change_bars(viz: dict[str, Any]) -> Any | None:
    comp = viz["comparison"]
    if not comp["available"] or not comp["subject_changes"]:
        return None
    rows = sorted(comp["subject_changes"], key=lambda row: row["change_points"])
    fig = go.Figure(go.Bar(x=[row["change_points"] for row in rows], y=[row["subject"] for row in rows],
                           orientation="h",
                           marker_color=[TEAL if row["change_points"] >= 0 else ROSE for row in rows],
                           text=[f"{row['change_points']:+.1f}" for row in rows], textposition="outside"))
    fig.add_vline(x=0, line_color=INK)
    return _layout(fig, "Subject change since the previous exam", "Subject")


def correlation_heatmap(correlations: dict[str, Any]) -> Any | None:
    if not correlations["available"] or not correlations["pearson"]:
        return None
    rows = correlations["pearson"]
    subjects = [row["subject"] for row in rows]
    matrix = [[row.get(subject) for subject in subjects] for row in rows]
    fig = go.Figure(go.Heatmap(z=matrix, x=subjects, y=subjects, zmin=-1, zmax=1,
                               colorscale="RdBu", reversescale=True, text=[[f"{v:.2f}" if v is not None else "" for v in row]
                                                                            for row in matrix],
                               texttemplate="%{text}", hovertemplate="%{y} / %{x}: %{z:.2f}<extra></extra>"))
    return _layout(fig, "Pearson subject correlation heatmap", "Subject")


def relationship(viz: dict[str, Any], left: str, right: str) -> Any | None:
    left_history = {row["exam"]: row["percentage"] for row in viz["subject_history"].get(left, [])}
    right_history = {row["exam"]: row["percentage"] for row in viz["subject_history"].get(right, [])}
    shared = [(exam, left_history[exam], right_history[exam]) for exam in left_history if exam in right_history]
    if len(shared) < 2:
        return None
    x = [row[1] for row in shared]
    y = [row[2] for row in shared]
    fig = go.Figure(go.Scatter(x=x, y=y, mode="markers+text", text=[row[0] for row in shared],
                               textposition="top center", marker={"size": 11, "color": TEAL},
                               hovertemplate=f"{left}: %{{x:.1f}}%<br>{right}: %{{y:.1f}}%<extra></extra>"))
    fig.update_xaxes(range=[0, 105], title=left)
    fig.update_yaxes(range=[0, 105], title=right)
    return _layout(fig, f"Relationship: {left} vs {right}")


def consistency(consistency_data: dict[str, Any]) -> Any | None:
    if not consistency_data["available"]:
        return None
    rows = consistency_data["subjects"]
    rows = sorted(rows, key=lambda row: row["cv_percent"], reverse=True)
    fig = go.Figure(go.Bar(x=[row["cv_percent"] for row in rows], y=[row["subject"] for row in rows],
                           orientation="h", marker_color=AMBER,
                           text=[f"{row['cv_percent']:.1f}%" for row in rows], textposition="outside"))
    return _layout(fig, "Subject consistency (coefficient of variation)", "Subject")


def history_boxplot(viz: dict[str, Any]) -> Any | None:
    fig = go.Figure()
    count = 0
    for subject, history in viz["subject_history"].items():
        if len(history) >= 3:
            fig.add_trace(go.Box(y=[row["percentage"] for row in history], name=subject, boxmean=True))
            count += 1
    if not count:
        return None
    fig.update_yaxes(range=[0, 105], title="Percentage")
    return _layout(fig, "Percentage spread by subject across exams")


def outlier_scatter(viz: dict[str, Any], outliers: dict[str, Any]) -> Any:
    values = outliers["within_exam"].get("values", [])
    subjects = [row["subject"] for row in viz["subjects"]]
    flags = [value["iqr_flag"] or value["z_flag"] for value in values]
    fig = go.Figure(go.Scatter(x=subjects, y=[value["value"] for value in values], mode="markers",
                               marker={"size": 13, "color":[ROSE if flag else TEAL for flag in flags]},
                               text=["Outlier" if flag else "Within expected range" for flag in flags],
                               hovertemplate="%{x}: %{y:.1f}%<br>%{text}<extra></extra>"))
    fig.update_yaxes(range=[0, 105], title="Percentage")
    return _layout(fig, "Current-exam outlier screening")


def trend(viz: dict[str, Any], moving: dict[str, Any], projection: dict[str, Any]) -> Any:
    fig = go.Figure()
    exams = [row["exam"] for row in viz["exams"]]
    for subject, history in viz["subject_history"].items():
        if len(history) >= 2:
            fig.add_trace(go.Scatter(x=[row["exam"] for row in history], y=[row["percentage"] for row in history],
                                     mode="lines+markers", name=subject, opacity=0.45))
    fig.add_trace(go.Scatter(x=exams, y=[row["percentage"] for row in viz["exams"]],
                             mode="lines+markers", name="Overall", line={"color": INK, "width": 4}))
    if moving["available"]:
        series = moving["series"]
        fig.add_trace(go.Scatter(x=exams, y=[row["moving_average_2"] for row in series],
                                 mode="lines+markers", name="2-exam moving average", line={"color": TEAL, "dash": "dash"}))
        fig.add_trace(go.Scatter(x=exams, y=[row["moving_average_3"] for row in series],
                                 mode="lines+markers", name="3-exam moving average", line={"color": AMBER, "dash": "dot"}))
    if projection["available"]:
        fig.add_trace(go.Scatter(x=[*exams, "Next exam"], y=[row["percentage"] for row in viz["exams"]] + [projection["projected_next"]],
                                 mode="lines+markers", name="Illustrative extrapolation", line={"color": ROSE, "dash": "dash"}))
    fig.update_yaxes(range=[0, 105], title="Percentage")
    return _layout(fig, "Performance trends and moving averages")


def pareto(loss: dict[str, Any]) -> Any | None:
    if not loss["available"]:
        return None
    rows = loss["subjects"]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=[row["subject"] for row in rows], y=[row["marks_lost"] for row in rows],
                         marker_color=ROSE, name="Marks lost"), secondary_y=False)
    fig.add_trace(go.Scatter(x=[row["subject"] for row in rows], y=[row["cumulative_share"] for row in rows],
                             mode="lines+markers", marker_color=AMBER, name="Cumulative share"), secondary_y=True)
    fig.add_hline(y=80, line_dash="dash", line_color=INK, secondary_y=True)
    fig.update_yaxes(title_text="Marks lost", secondary_y=False)
    fig.update_yaxes(title_text="Cumulative share (%)", range=[0, 105], secondary_y=True)
    return _layout(fig, "Pareto: where marks were lost")


def scenario_bar(original: float, new: float, title: str) -> Any:
    fig = go.Figure(go.Bar(x=["Original", "What-if"], y=[original, new], marker_color=[GREY, TEAL],
                           text=[f"{original:.1f}%", f"{new:.1f}%"], textposition="outside"))
    fig.update_yaxes(range=[0, 110])
    return _layout(fig, title, "Overall percentage")


def required_scores(plan: dict[str, Any]) -> Any:
    rows = plan["per_subject"]
    fig = go.Figure(go.Bar(x=[row["subject"] for row in rows], y=[row["required_percentage"] for row in rows],
                           marker_color=[TEAL if row["feasible"] else ROSE for row in rows],
                           text=[f"{row['required_percentage']:.1f}%" for row in rows], textposition="outside"))
    fig.add_hline(y=100, line_dash="dash", line_color=ROSE, annotation_text="Maximum feasible")
    fig.update_yaxes(range=[0, max(110, max(row["required_percentage"] for row in rows) + 10)])
    return _layout(fig, "Required percentage by subject for the target")


def weighted(original: float, weighted_score: float) -> Any:
    fig = go.Figure(go.Bar(x=["Unweighted", "Weighted"], y=[original, weighted_score],
                           marker_color=[GREY, TEAL], text=[f"{original:.1f}%", f"{weighted_score:.1f}%"],
                           textposition="outside"))
    fig.update_yaxes(range=[0, 110])
    return _layout(fig, "Weighted versus unweighted score", "Percentage")


def show_unavailable(reason: str) -> None:
    st.info(reason)

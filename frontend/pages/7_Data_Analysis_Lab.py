from __future__ import annotations

import streamlit as st

try:
    import api_client as api
    import ui
    from components import analytics_charts as charts
except ModuleNotFoundError:
    from frontend import api_client as api, ui
    from frontend.components import analytics_charts as charts

ui.setup("Data Analysis Lab")
student = ui.require_student()
sid = student["student_id"]

try:
    viz = ui.get_cached("analytics_viz", sid, lambda: api.visualizations(sid))["data"]
    summary = ui.get_cached("analytics_summary", sid, lambda: api.analytics_summary(sid))
    loss = ui.get_cached("analytics_loss", sid, lambda: api.analytics_loss(sid))
except api.ApiError as exc:
    ui.show_error(exc)
    st.stop()

st.title("Data Analysis Lab")
st.caption("Explore your results through interactive graphs. Every chart is calculated from your marks.")
if not charts.available():
    st.warning("Interactive charts require Plotly. Install it with: pip install plotly")
    st.stop()

tabs = st.tabs(["Overview", "Comparisons", "Relationships", "Consistency & outliers", "Trends & projections",
                "Marks lost & scenarios"])

with tabs[0]:
    st.plotly_chart(charts.subject_overview(viz), use_container_width=True)
    left, right = st.columns(2)
    with left:
        st.plotly_chart(charts.subject_radar(viz), use_container_width=True)
    with right:
        st.plotly_chart(charts.distribution(viz), use_container_width=True)

with tabs[1]:
    comparison = charts.comparison(viz)
    changes = charts.change_bars(viz)
    if comparison is None or changes is None:
        st.info(viz["comparison"].get("reason", "Add a previous examination to compare subjects."))
    else:
        st.plotly_chart(comparison, use_container_width=True)
        st.plotly_chart(changes, use_container_width=True)

with tabs[2]:
    correlations = charts.correlation_heatmap(summary["correlations"])
    if correlations is None:
        st.info(summary["correlations"]["reason"])
    else:
        st.plotly_chart(correlations, use_container_width=True)
        subjects = sorted(viz["subject_history"])
        if len(subjects) >= 2:
            left, right = st.columns(2)
            first = left.selectbox("First subject", subjects)
            second = right.selectbox("Second subject", subjects, index=1)
            if first == second:
                st.warning("Choose two different subjects for the relationship graph.")
            else:
                relationship = charts.relationship(viz, first, second)
                if relationship is None:
                    st.info("At least two shared exams are needed for this relationship graph.")
                else:
                    st.plotly_chart(relationship, use_container_width=True)

with tabs[3]:
    consistency = charts.consistency(summary["consistency"])
    if consistency is None:
        st.info(summary["consistency"]["reason"])
    else:
        st.plotly_chart(consistency, use_container_width=True)
    box = charts.history_boxplot(viz)
    if box is not None:
        st.plotly_chart(box, use_container_width=True)
    outliers = summary["outliers"]
    if outliers["within_exam"].get("available", True):
        st.plotly_chart(charts.outlier_scatter(viz, outliers), use_container_width=True)

with tabs[4]:
    st.plotly_chart(charts.trend(viz, summary["moving_average"], summary["projection"]),
                    use_container_width=True)
    if not summary["moving_average"]["available"]:
        st.info(summary["moving_average"]["reason"])
    if not summary["projection"]["available"]:
        st.info(summary["projection"]["reason"])

with tabs[5]:
    pareto = charts.pareto(loss)
    if pareto is None:
        st.info(loss["reason"])
    else:
        st.plotly_chart(pareto, use_container_width=True)
    subjects = [row["subject"] for row in viz["subjects"]]
    left, right = st.columns(2)
    with left:
        target = st.number_input("Target percentage", 0.0, 100.0, 80.0)
        if st.button("Show target graph"):
            try:
                st.plotly_chart(charts.required_scores(api.analytics_planner(sid, target)),
                                use_container_width=True)
            except api.ApiError as exc:
                ui.show_error(exc)
    with right:
        selected = st.multiselect("Subjects to change", subjects)
        changes = {subject: st.slider(subject, 0.0, 100.0, float(next(
            row["percentage"] for row in viz["subjects"] if row["subject"] == subject)), key=f"scenario_{subject}")
                   for subject in selected}
        if st.button("Show what-if graph"):
            try:
                result = api.analytics_what_if(sid, changes)
                st.plotly_chart(charts.scenario_bar(result["original_overall"], result["new_overall"],
                                                    "What-if overall comparison"), use_container_width=True)
            except api.ApiError as exc:
                ui.show_error(exc)

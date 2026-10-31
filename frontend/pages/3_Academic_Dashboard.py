from __future__ import annotations

import api_client as api
import pandas as pd
import streamlit as st
import ui

from frontend.components import charts, metrics, resource_cards

ui.setup("Academic Dashboard")
student = ui.require_student()
sid = student["student_id"]

try:
    perf = ui.get_cached("performance", sid, lambda: api.performance(sid))
except api.ApiError as exc:
    if exc.status == 422:
        st.info("No marks saved yet. Add your results to see the dashboard.")
        ui.page_link("pages/2_Upload_Marksheet.py", label="Enter or upload marks")
    else:
        ui.show_error(exc)
    st.stop()

metrics.student_header(student, perf["metrics"]["exam_name"])

report = ui.get_cached("report", sid, lambda: api.report(sid))
left, right = st.columns([3, 1])
left.write(perf["summary"])
if right.button("Generate AI report" if report is None else "Regenerate report", type="primary"):
    try:
        with st.spinner("Analysing results, planning improvements and searching for resources. This can take a minute..."):
            api.analyze(sid)
        ui.invalidate(sid, "report")
        st.rerun()
    except api.ApiError as exc:
        ui.show_error(exc)

tabs = st.tabs(["Overview", "Performance", "Visual analytics", "Weakness analysis", "Learning resources", "AI report"])

with tabs[0]:
    metrics.overview_metrics(perf["metrics"])
    st.subheader("Insights from your marks")
    labels = {"strength": "Strength", "improvement_area": "Improve", "attention": "Needs attention",
              "progress": "Progress", "priority": "Priority"}
    for ins in perf["insights"]:
        st.markdown(f"**{labels.get(ins['category'], ins['category'])} - {ins['title']}**  \n{ins['statement']}")

with tabs[1]:
    st.subheader("Subject results")
    st.dataframe(
        [{"Subject": s["subject"], "Obtained": s["obtained"], "Total": s["total"], "Percentage": s["percentage"],
          "Grade": s["grade"] + (" *" if s["grade_is_indicative"] else "")} for s in perf["subjects"]],
        hide_index=True,
        column_config={"Percentage": st.column_config.ProgressColumn("Percentage", min_value=0, max_value=100, format="%.1f%%")})
    if any(s["grade_is_indicative"] for s in perf["subjects"]):
        st.caption("* Grades marked with an asterisk are indicative: this board has no fixed percentage-to-grade table. Your marksheet's grade is the official one.")
    m = perf["metrics"]
    c1, c2 = st.columns(2)
    c1.metric("Highest subject", m["highest_subject"], f"{m['highest_percentage']:.1f}%")
    c2.metric("Lowest subject", m["lowest_subject"], f"{m['lowest_percentage']:.1f}%", delta_color="off")
    metrics.statistics_metrics({"statistics": perf["statistics"]["statistics"], "std_dev_method": perf["statistics"]["std_dev_method"]})
    st.subheader("Performance distribution")
    dist = perf["statistics"]["distribution"]
    st.bar_chart(pd.DataFrame({"Subjects": [d["count"] for d in dist]}, index=[d["label"] for d in dist]))
    cmp = perf["comparison"]
    st.subheader("Change since the previous examination")
    if cmp["available"]:
        st.write(f"Overall: {cmp['previous_overall_percentage']:.1f}% to {cmp['current_overall_percentage']:.1f}% "
                 f"({cmp['overall_change_points']:+.1f} points, {cmp['overall_status']}).")
        st.dataframe([{"Subject": c["subject"], "Previous": c["previous_percentage"], "Current": c["current_percentage"],
                       "Change (points)": c["change_points"], "Status": c["status"]} for c in cmp["subject_changes"]],
                     hide_index=True)
    else:
        st.info(cmp["reason"])

with tabs[2]:
    try:
        viz = ui.get_cached("viz", sid, lambda: api.visualizations(sid))
    except api.ApiError as exc:
        ui.show_error(exc)
    else:
        interactive, static = st.tabs(["Interactive", "Static charts"])
        with interactive:
            charts.show_interactive(viz["data"])
        with static:
            charts.show_static(sid, viz["charts"])

with tabs[3]:
    try:
        weak = ui.get_cached("weak", sid, lambda: api.weaknesses(sid))
    except api.ApiError as exc:
        ui.show_error(exc)
    else:
        st.caption(weak["threshold_explanation"])
        recs = {r["subject"].lower(): r for r in (report["recommendations"] if report else [])}
        if not weak["weak_subjects"]:
            st.success("No subject met a weakness criterion.")
        for w in weak["weak_subjects"]:
            with st.expander(f"{w['subject']} - {w['percentage']:.1f}%", expanded=w["priority"] == "high"):
                st.markdown(ui.pill(w["priority"]), unsafe_allow_html=True)
                st.markdown("**Evidence from your results**")
                for r in w["reasons"]:
                    st.write(f"- {r['explanation']}")
                if w["student_reported_difficulty"]:
                    st.write("- You also listed this as a difficult subject.")
                rec = recs.get(w["subject"].lower())
                st.markdown("**Suggested improvement strategy**")
                if rec:
                    for a in rec["actions"]:
                        st.write(f"- {a}")
                    st.caption(rec["goal"])
                else:
                    st.caption("Generate the AI report to get a study strategy for this subject.")
        st.subheader("Topic mastery from practice quizzes")
        try:
            mastery_rows = api.quiz_mastery(sid)
        except api.ApiError as exc:
            ui.show_error(exc)
        else:
            if mastery_rows:
                from frontend.components.quiz import mastery_chart
                mastery_chart(mastery_rows)
            else:
                st.info("Take a practice quiz to get topic-level evidence.")

with tabs[4]:
    if report is None:
        st.info("Generate the report to search for learning resources.")
    else:
        st.caption(report["resource_search_status"])
        if report["resources"]:
            resource_cards.render_resource_cards(report["resources"])

with tabs[5]:
    if report is None:
        st.info("No report yet. Select Generate AI report above.")
    else:
        st.caption(("Includes AI-written content. " if report["ai_generated"] else "Built from templates and calculations. ")
                   + f"Generated {report['generated_at'][:16].replace('T', ' ')} UTC.")
        for note in report["ai_notes"]:
            st.info(note)
        st.markdown(report["narrative_markdown"])
        st.download_button("Download report (Markdown)", report["narrative_markdown"],
                           file_name=f"academic_report_{student['name'].replace(' ', '_')}.md")

st.divider()
ui.page_link("pages/4_Improvement_Roadmap.py", label="Open the improvement roadmap")
ui.page_link("pages/5_AI_Academic_Chat.py", label="Ask the academic advisor")

"""Metric cards and summary blocks."""
from __future__ import annotations

from typing import Any

import streamlit as st


def overview_metrics(metrics: dict[str, Any]) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall percentage", f"{metrics['overall_percentage']:.1f}%")
    c2.metric("Marks", f"{metrics['total_obtained']:g} / {metrics['total_possible']:g}")
    c3.metric("Average subject score", f"{metrics['average_subject_percentage']:.1f}%")
    grade = metrics["overall_grade"] + (" (indicative)" if metrics["overall_grade_is_indicative"] else "")
    c4.metric("Overall grade", grade)


def student_header(student: dict[str, Any], exam_name: str) -> None:
    st.title(student["name"])
    parts = [student["board"], student["grade"], student["academic_year"], exam_name]
    st.caption(" | ".join(p for p in parts if p))


def statistics_metrics(stats: dict[str, Any]) -> None:
    s = stats["statistics"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Mean", f"{s['mean']:.1f}%")
    c2.metric("Median", f"{s['median']:.1f}%")
    c3.metric("Std deviation", f"{s['std_dev']:.1f}")
    c4.metric("Range", f"{s['min']:.0f}% to {s['max']:.0f}%")
    st.caption(stats["std_dev_method"].capitalize() + ".")

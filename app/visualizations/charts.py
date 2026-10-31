"""Matplotlib/Seaborn chart builders.

Each builder takes the dict from `StudentAnalyzer.generate_visualization_data()` and writes a PNG.
A builder returns `None` (and the registry records a reason) when the data cannot support an honest
chart, instead of drawing something misleading.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless backend; must be set before importing pyplot

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

INK, TEAL, AMBER, ROSE, GREY, LIGHT = "#1F2A44", "#0E7C86", "#D98E04", "#B83A3A", "#8A94A6", "#E6EAF0"

sns.set_theme(style="whitegrid", rc={"axes.edgecolor": LIGHT, "grid.color": LIGHT, "axes.labelcolor": INK,
                                     "text.color": INK, "xtick.color": INK, "ytick.color": INK})


def _save(fig: plt.Figure, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _colors(data: dict[str, Any]) -> list[str]:
    weak, strong = set(data["weak_subjects"]), set(data["strong_subjects"])
    return [ROSE if s["subject"] in weak else TEAL if s["subject"] in strong else GREY for s in data["subjects"]]


def subject_marks_bar(data: dict[str, Any], path: Path) -> Path | None:
    names = [s["subject"] for s in data["subjects"]]
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(x, [s["total"] for s in data["subjects"]], color=LIGHT, label="Total marks")
    ax.bar(x, [s["obtained"] for s in data["subjects"]], color=TEAL, width=0.6, label="Obtained marks")
    for i, s in enumerate(data["subjects"]):
        ax.text(i, s["obtained"], f"{s['obtained']:g}", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x, names, rotation=25, ha="right")
    ax.set_ylabel("Marks")
    ax.set_title(f"Marks by subject - {data['exam_name']}", loc="left", fontweight="bold")
    ax.legend(frameon=False)
    return _save(fig, path)


def subject_percentage_bar(data: dict[str, Any], path: Path) -> Path | None:
    names = [s["subject"] for s in data["subjects"]]
    pcts = [s["percentage"] for s in data["subjects"]]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    bars = ax.bar(names, pcts, color=_colors(data))
    ax.axhline(data["pass_mark"], color=INK, ls=":", lw=1, label=f"Board pass mark ({data['pass_mark']:g}%)")
    if data.get("target_percentage"):
        ax.axhline(data["target_percentage"], color=AMBER, ls="--", lw=1.2, label=f"Your target ({data['target_percentage']:g}%)")
    ax.bar_label(bars, fmt="%.1f%%", fontsize=9, padding=2)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Percentage")
    ax.set_xticks(range(len(names)), names, rotation=25, ha="right")
    ax.set_title("Percentage by subject (red = flagged weak, teal = strong)", loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="lower right")
    return _save(fig, path)


def overall_performance_chart(data: dict[str, Any], path: Path) -> Path | None:
    fig, ax = plt.subplots(figsize=(9, 2.8))
    ax.barh(["Overall"], [100], color=LIGHT, height=0.5)
    ax.barh(["Overall"], [data["overall_percentage"]], color=TEAL, height=0.5)
    ax.axvline(data["pass_mark"], color=INK, ls=":", lw=1.2)
    ax.text(data["pass_mark"], 0.42, "pass mark", ha="center", fontsize=8)
    if data.get("target_percentage"):
        ax.axvline(data["target_percentage"], color=AMBER, ls="--", lw=1.4)
        ax.text(data["target_percentage"], -0.42, "target", ha="center", fontsize=8, color=AMBER)
    ax.text(min(data["overall_percentage"], 96) - 1, 0, f"{data['overall_percentage']:.1f}%", ha="right", va="center",
            color="white", fontweight="bold")
    ax.set_xlim(0, 100)
    ax.set_xlabel("Overall percentage (total obtained / total possible)")
    ax.set_title("Overall academic performance", loc="left", fontweight="bold")
    return _save(fig, path)


def strong_vs_weak(data: dict[str, Any], path: Path) -> Path | None:
    weak = [s for s in data["subjects"] if s["subject"] in set(data["weak_subjects"])]
    strong = [s for s in data["subjects"] if s["subject"] in set(data["strong_subjects"])]
    if not weak and not strong:
        return None
    rows = sorted(strong + weak, key=lambda s: s["percentage"])
    colors = [ROSE if s["subject"] in set(data["weak_subjects"]) else TEAL for s in rows]
    fig, ax = plt.subplots(figsize=(8, max(2.8, 0.55 * len(rows) + 1.2)))
    bars = ax.barh([s["subject"] for s in rows], [s["percentage"] for s in rows], color=colors)
    ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=9)
    ax.axvline(data["average_percentage"], color=INK, ls="--", lw=1, label=f"Your average ({data['average_percentage']:.1f}%)")
    ax.set_xlim(0, 105)
    ax.set_xlabel("Percentage")
    ax.set_title("Strong vs weak subjects", loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="lower right")
    return _save(fig, path)


def radar_chart(data: dict[str, Any], path: Path) -> Path | None:
    subjects = data["subjects"]
    if len(subjects) < 3:
        return None
    labels = [s["subject"] for s in subjects]
    values = [s["percentage"] for s in subjects]
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    fig, ax = plt.subplots(figsize=(6.2, 6.2), subplot_kw={"polar": True})
    ax.plot(angles + angles[:1], values + values[:1], color=TEAL, lw=2)
    ax.fill(angles + angles[:1], values + values[:1], color=TEAL, alpha=0.25)
    if data.get("target_percentage"):
        ax.plot(angles + angles[:1], [data["target_percentage"]] * (len(labels) + 1), color=AMBER, ls="--", lw=1.2,
                label="Target")
        ax.legend(frameon=False, loc="upper right", bbox_to_anchor=(1.2, 1.1))
    ax.set_xticks(angles, labels, fontsize=9)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_title("Subject performance profile (%)", fontweight="bold", pad=20)
    return _save(fig, path)


def distribution_histogram(data: dict[str, Any], path: Path) -> Path | None:
    if len(data["subjects"]) < 3:
        return None
    dist = data["distribution"]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    bars = ax.bar([d["label"] for d in dist], [d["count"] for d in dist], color=TEAL)
    ax.bar_label(bars, padding=2, fontsize=9)
    ax.set_xlabel("Percentage band")
    ax.set_ylabel("Number of subjects")
    ax.yaxis.get_major_locator().set_params(integer=True)
    ax.set_title("Performance distribution", loc="left", fontweight="bold")
    return _save(fig, path)


def exam_comparison_chart(data: dict[str, Any], path: Path) -> Path | None:
    comp = data["comparison"]
    if not comp["available"] or not comp["subject_changes"]:
        return None
    rows = sorted(comp["subject_changes"], key=lambda r: r["subject"])
    x = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(x - 0.2, [r["previous_percentage"] for r in rows], width=0.4, color=GREY, label=comp["previous_exam"])
    ax.bar(x + 0.2, [r["current_percentage"] for r in rows], width=0.4, color=TEAL, label=comp["current_exam"])
    ax.set_xticks(x, [r["subject"] for r in rows], rotation=25, ha="right")
    ax.set_ylim(0, 105)
    ax.set_ylabel("Percentage")
    ax.set_title("Examination comparison", loc="left", fontweight="bold")
    ax.legend(frameon=False)
    return _save(fig, path)


def improvement_decline_chart(data: dict[str, Any], path: Path) -> Path | None:
    comp = data["comparison"]
    if not comp["available"] or not comp["subject_changes"]:
        return None
    rows = sorted(comp["subject_changes"], key=lambda r: r["change_points"])
    colors = [TEAL if r["change_points"] > 0 else ROSE if r["change_points"] < 0 else GREY for r in rows]
    fig, ax = plt.subplots(figsize=(8, max(2.8, 0.55 * len(rows) + 1.2)))
    bars = ax.barh([r["subject"] for r in rows], [r["change_points"] for r in rows], color=colors)
    ax.bar_label(bars, fmt="%+.1f", padding=3, fontsize=9)
    ax.axvline(0, color=INK, lw=1)
    ax.set_xlabel(f"Change in percentage points ({comp['previous_exam']} -> {comp['current_exam']})")
    ax.set_title("Improvement or decline by subject", loc="left", fontweight="bold")
    return _save(fig, path)


def trend_line_chart(data: dict[str, Any], path: Path) -> Path | None:
    if len(data["exams"]) < 3:
        return None  # two points do not make a trend; the comparison charts cover that case
    exams = [e["exam"] for e in data["exams"]]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for subject, hist in data["subject_history"].items():
        if len(hist) >= 2:
            ax.plot([h["exam"] for h in hist], [h["percentage"] for h in hist], marker="o", lw=1.4, alpha=0.8, label=subject)
    ax.plot(exams, [e["percentage"] for e in data["exams"]], color=INK, lw=3, marker="s", label="Overall")
    ax.set_ylim(0, 105)
    ax.set_ylabel("Percentage")
    ax.set_title("Performance trend across examinations", loc="left", fontweight="bold")
    ax.legend(frameon=False, bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
    return _save(fig, path)


# (id, title, builder, why it may be unavailable)
CHART_REGISTRY: list[tuple[str, str, Callable[[dict[str, Any], Path], Path | None], str]] = [
    ("subject_marks", "Subject-wise marks", subject_marks_bar, ""),
    ("subject_percentages", "Subject-wise percentages", subject_percentage_bar, ""),
    ("overall", "Overall performance", overall_performance_chart, ""),
    ("strong_vs_weak", "Strong versus weak subjects", strong_vs_weak, "No subject met a strength or weakness criterion."),
    ("radar", "Subject performance radar", radar_chart, "A radar chart needs at least 3 subjects."),
    ("distribution", "Performance distribution", distribution_histogram, "A distribution needs at least 3 subjects."),
    ("exam_comparison", "Examination comparison", exam_comparison_chart, "Needs two examinations with shared subjects."),
    ("improvement_decline", "Improvement or decline", improvement_decline_chart, "Needs two examinations with shared subjects."),
    ("trend", "Performance trend", trend_line_chart, "A trend needs at least 3 examinations."),
]

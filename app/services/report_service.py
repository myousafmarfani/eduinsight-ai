"""Report rendering (Markdown) and export to REPORT_DIRECTORY."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.security import ensure_within_directory
from app.schemas.analysis import (
    AcademicReport,
    EducationalResource,
    ImprovementRecommendation,
    WeakSubject,
)


def _subject_table(subjects: list[dict[str, Any]]) -> str:
    lines = ["| Subject | Obtained | Total | Percentage | Grade |", "|---|---:|---:|---:|---|"]
    for s in subjects:
        grade = f"{s['grade']}{' (indicative)' if s.get('grade_is_indicative') else ''}"
        lines.append(f"| {s['subject']} | {s['obtained']:g} | {s['total']:g} | {s['percentage']:.1f}% | {grade} |")
    return "\n".join(lines)


def _weak_block(weak: list[WeakSubject]) -> str:
    if not weak:
        return "No subject met any weakness criterion."
    out = []
    for w in weak:
        out.append(f"- **{w.subject}** ({w.percentage:.1f}%, priority: {w.priority.value})")
        out.extend(f"  - {r.explanation}" for r in w.reasons)
        if w.student_reported_difficulty:
            out.append("  - You also listed this as a difficult subject.")
    return "\n".join(out)


def _recommendation_block(recs: list[ImprovementRecommendation]) -> str:
    out = []
    for r in recs:
        label = "AI-written advice" if r.ai_generated else "standard study strategy"
        out.append(f"### {r.subject} - {r.priority.value} priority ({label})")
        out.append(f"*Evidence from your marks:* {r.evidence}")
        out.extend(f"- {a}" for a in r.actions)
        out.append(f"*{r.goal}*\n")
    return "\n".join(out)


def _resource_block(resources: list[EducationalResource], status: str) -> str:
    if not resources:
        return status
    out = [status, ""]
    for r in resources:
        out.append(f"- [{r.title}]({r.url}) - {r.resource_type.value}, {r.subject}. {r.description}")
    return "\n".join(out)


def render_markdown(report_parts: dict[str, Any], ai_summary: str | None) -> str:
    """Compose the full report. Sections are labelled so calculated facts and advice stay distinct."""
    overall = report_parts["overview"]
    comparison = report_parts["comparison"]
    parts = [f"# Academic report - {overall.exam_name}", ""]
    if ai_summary:
        parts += ["## AI summary", ("*Written by an AI model from the calculated results below; the numbers in the sections "
                  "that follow are the source of truth.*"), "", ai_summary.strip(), ""]
    parts += [
        "## Your results (calculated from your marks)",
        (f"Total: **{overall.total_obtained:g} / {overall.total_possible:g}** = **{overall.overall_percentage:.1f}%** "
        f"(grade {overall.overall_grade}{', indicative' if overall.overall_grade_is_indicative else ''}). "
        f"Highest: {overall.highest_subject} ({overall.highest_percentage:.1f}%). "
        f"Lowest: {overall.lowest_subject} ({overall.lowest_percentage:.1f}%)."),
        "", _subject_table(report_parts["subjects"]), "",
        "### Strengths",
        "\n".join(f"- **{s.subject}** ({s.percentage:.1f}%): {s.reasons[0].explanation}" for s in report_parts["strengths"])
        or "No subject met a strength criterion.",
        "", "### Areas needing improvement", _weak_block(report_parts["weaknesses"]), "",
        "### Progress between examinations",
    ]
    if comparison.get("available"):
        parts.append(f"Overall: {comparison['previous_overall_percentage']:.1f}% -> {comparison['current_overall_percentage']:.1f}% "
                     f"({comparison['overall_change_points']:+.1f} points, {comparison['overall_status']}).")
        parts += [f"- {c['subject']}: {c['previous_percentage']:.1f}% -> {c['current_percentage']:.1f}% ({c['change_points']:+.1f})"
                  for c in comparison["subject_changes"]]
    else:
        parts.append(comparison.get("reason", "No comparison available."))
    topic_rows = report_parts.get("weak_topics", [])
    parts += ["", "## Topic-level evidence from practice quizzes"]
    if topic_rows:
        parts.extend(f"- **{row['topic']}** ({row['subject']}): {row['evidence']}" for row in topic_rows)
    else:
        parts.append("A completed practice quiz will provide topic-level insight; marks alone cannot identify weak topics.")
    parts += ["", "## Improvement plan", _recommendation_block(report_parts["recommendations"]),
              "## Learning resources", _resource_block(report_parts["resources"], report_parts["resource_status"])]
    if report_parts["ai_notes"]:
        parts += ["", "## Notes", *[f"- {n}" for n in report_parts["ai_notes"]]]
    return "\n".join(parts)


def export_report(report: AcademicReport, report_dir: Path) -> Path:
    """Write the report's Markdown to <report_dir>/<student_id>/<timestamp>.md."""
    folder = report_dir / report.student_id
    folder.mkdir(parents=True, exist_ok=True)
    path = ensure_within_directory(report_dir, folder / f"report_{report.generated_at:%Y%m%d_%H%M%S}.md")
    path.write_text(report.narrative_markdown, encoding="utf-8")
    return path

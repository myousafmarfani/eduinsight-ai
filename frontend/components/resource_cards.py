"""Learning-resource cards (all external text is HTML-escaped)."""
from __future__ import annotations

import html
from typing import Any

import streamlit as st

_TYPE_LABEL = {"video": "Video", "article": "Article", "documentation": "Documentation", "practice": "Practice material",
               "course": "Course", "other": "Resource"}


def _card(res: dict[str, Any]) -> str:
    url = html.escape(res["url"], quote=True)
    return (
        '<div class="res-card">'
        f'<a href="{url}" target="_blank" rel="noopener noreferrer">{html.escape(res["title"])}</a>'
        f'<div class="res-meta">{_TYPE_LABEL.get(res["resource_type"], "Resource")} | {html.escape(res["subject"])}</div>'
        f'<div>{html.escape(res["description"])}</div>'
        f'<div class="res-why">{html.escape(res["why_recommended"])}</div>'
        "</div>"
    )


def render_resource_cards(resources: list[dict[str, Any]]) -> None:
    """Show resources grouped by subject in two columns."""
    subjects = list(dict.fromkeys(r["subject"] for r in resources))
    for subject in subjects:
        st.subheader(subject)
        items = [r for r in resources if r["subject"] == subject]
        cols = st.columns(2)
        for i, res in enumerate(items):
            cols[i % 2].markdown(_card(res), unsafe_allow_html=True)

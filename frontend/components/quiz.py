"""Practice-quiz widgets."""
from __future__ import annotations

from typing import Any

import streamlit as st


def mastery_chart(rows: list[dict[str, Any]]) -> None:
    if not rows:
        st.info("No completed quiz evidence yet.")
        return
    import pandas as pd

    frame = pd.DataFrame(rows)
    frame["label"] = frame["subject"] + " - " + frame["topic"]
    frame["display_accuracy"] = frame["accuracy"].where(frame["enough_data"], 0)
    st.bar_chart(frame.set_index("label")["display_accuracy"])
    under = frame[~frame["enough_data"]]
    if not under.empty:
        st.caption("Topics below the minimum sample are shown at zero until enough evidence is collected.")

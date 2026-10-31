"""Generate the chart set for a student and report which charts are available."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.visualizations.charts import CHART_REGISTRY

logger = logging.getLogger(__name__)


@dataclass
class ChartResult:
    id: str
    title: str
    available: bool
    path: Path | None = None
    reason: str = ""


def generate_charts(viz_data: dict[str, Any], out_dir: Path) -> list[ChartResult]:
    """Render every chart whose data requirements are met. Failures never abort the others."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[ChartResult] = []
    for chart_id, title, builder, unavailable_reason in CHART_REGISTRY:
        path = out_dir / f"{chart_id}.png"
        path.unlink(missing_ok=True)  # never serve a stale image from an earlier analysis
        try:
            built = builder(viz_data, path)
        except Exception:
            logger.exception("Chart '%s' failed", chart_id)
            results.append(ChartResult(chart_id, title, False, None, "The chart could not be rendered."))
            continue
        if built is None:
            results.append(ChartResult(chart_id, title, False, None, unavailable_reason))
        else:
            results.append(ChartResult(chart_id, title, True, built))
    return results


def chart_ids() -> list[str]:
    return [c[0] for c in CHART_REGISTRY]

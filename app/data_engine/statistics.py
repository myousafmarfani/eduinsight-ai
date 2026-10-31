"""Descriptive statistics and performance distribution (NumPy)."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

DEFAULT_BIN_EDGES = [0, 40, 50, 60, 70, 80, 90, 100]


def descriptive_statistics(values: Sequence[float]) -> dict[str, Any]:
    """Mean, median, spread and quartiles of subject percentages.

    The standard deviation is the *sample* standard deviation (ddof=1); with a single value it is 0.
    """
    arr = np.asarray(list(values), dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        return {"count": 0, "mean": None, "median": None, "std_dev": None, "min": None, "max": None,
                "range": None, "q1": None, "q3": None, "iqr": None}
    q1, q3 = np.percentile(arr, [25, 75])
    return {
        "count": int(arr.size),
        "mean": round(float(arr.mean()), 2),
        "median": round(float(np.median(arr)), 2),
        "std_dev": round(float(arr.std(ddof=1)), 2) if arr.size > 1 else 0.0,
        "min": round(float(arr.min()), 2),
        "max": round(float(arr.max()), 2),
        "range": round(float(arr.max() - arr.min()), 2),
        "q1": round(float(q1), 2),
        "q3": round(float(q3), 2),
        "iqr": round(float(q3 - q1), 2),
    }


def performance_distribution(percentages: Sequence[float], edges: Sequence[float] = DEFAULT_BIN_EDGES) -> list[dict]:
    """Count subjects per percentage band. The top band includes 100."""
    arr = np.asarray(list(percentages), dtype=float)
    arr = arr[~np.isnan(arr)]
    counts, _ = np.histogram(arr, bins=list(edges))
    result = []
    for i, count in enumerate(counts):
        lo, hi = edges[i], edges[i + 1]
        label = f"{lo:g}-{hi:g}" if i == len(counts) - 1 else f"{lo:g}-<{hi:g}"
        result.append({"label": label, "lower": float(lo), "upper": float(hi), "count": int(count)})
    return result

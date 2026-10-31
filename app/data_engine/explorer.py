"""Pivot and export helpers for the analytics pages."""
from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd

ALLOWED_AGGREGATIONS = {"mean", "median", "min", "max", "std", "count", "sum"}


def pivot_results(df: pd.DataFrame, index: str, columns: str, values: str = "percentage",
                  aggfunc: str = "mean") -> pd.DataFrame:
    """Create a safe user-selected pivot using a strict aggregation whitelist."""
    allowed = {"exam", "exam_order", "subject", "percentage", "obtained", "total"}
    if index not in allowed or columns not in allowed or values not in allowed:
        raise ValueError("index, columns and values must be recognised result fields.")
    if aggfunc not in ALLOWED_AGGREGATIONS:
        raise ValueError(f"Unsupported aggregation '{aggfunc}'. Choose from {sorted(ALLOWED_AGGREGATIONS)}.")
    return pd.pivot_table(df, index=index, columns=columns, values=values, aggfunc=aggfunc)


def export_results(df: pd.DataFrame, statistics: pd.DataFrame | None = None,
                   comparison: pd.DataFrame | None = None, pareto: pd.DataFrame | None = None,
                   correlations: pd.DataFrame | None = None) -> bytes:
    """Build the documented multi-sheet workbook in memory."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Raw", index=False)
        percentages = df.pivot_table(index="exam", columns="subject", values="percentage", aggfunc="mean")
        percentages.round(2).to_excel(writer, sheet_name="Subject_Percentages")
        (statistics if statistics is not None else pd.DataFrame()).to_excel(writer, sheet_name="Statistics", index=False)
        (comparison if comparison is not None else pd.DataFrame()).to_excel(writer, sheet_name="Comparison", index=False)
        (pareto if pareto is not None else pd.DataFrame()).to_excel(writer, sheet_name="Pareto", index=False)
        if correlations is not None:
            correlations.to_excel(writer, sheet_name="Correlations", index=False)
        for sheet in writer.sheets.values():
            for column in sheet.columns:
                letter = column[0].column_letter
                width = min(40, max(10, max(len(str(cell.value or "")) for cell in column) + 2))
                sheet.column_dimensions[letter].width = width
    return output.getvalue()


def export_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

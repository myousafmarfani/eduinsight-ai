"""Additional descriptive statistics for a student's marks history.

The functions in this module are deliberately independent of FastAPI and the database.
They return ordinary Python values so their results can be sent as JSON directly.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.data_engine.board_config import grade_for_percentage
from app.data_engine.performance_analysis import add_percentage, exam_overall_series


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def _py(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else round(float(value), 4)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [{str(k): _py(v) for k, v in row.items()} for row in frame.astype(object).to_dict("records")]


def _latest(df: pd.DataFrame) -> pd.DataFrame:
    order = df["exam_order"].max()
    return add_percentage(df[df["exam_order"] == order])


def distribution_shape(df: pd.DataFrame) -> dict[str, Any]:
    values = _latest(df)["percentage"].dropna().to_numpy(float)
    if len(values) < 4:
        return _unavailable("At least 4 subjects are needed to describe distribution shape.")
    mean = values.mean()
    m2 = np.mean((values - mean) ** 2)
    if m2 == 0:
        skew = kurtosis = 0.0
    else:
        centered = values - mean
        n = len(values)
        # These finite-sample corrections match pandas Series.skew/kurt.
        skew = float(np.sqrt(n * (n - 1)) / (n - 2) * np.mean(centered ** 3) / m2 ** 1.5)
        kurtosis = float((n - 1) / ((n - 2) * (n - 3)) *
                         ((n + 1) * np.mean(centered ** 4) / m2 ** 2 - 3 * (n - 1)))
    interpretation = "approximately symmetric"
    if skew > 0.5:
        interpretation = "right-skewed (a few higher results)"
    elif skew < -0.5:
        interpretation = "left-skewed (a few lower results)"
    return {"available": True, "n": len(values), "skewness": _py(skew), "excess_kurtosis": _py(kurtosis),
            "interpretation": interpretation}


def standardized_scores(df: pd.DataFrame) -> dict[str, Any]:
    current = _latest(df)
    if len(current) < 3:
        return _unavailable("At least 3 subjects are needed for standardized scores.")
    values = current["percentage"].astype(float)
    mean, std = float(values.mean()), float(values.std(ddof=0))
    z = np.zeros(len(values)) if std == 0 else (values.to_numpy() - mean) / std
    result = pd.DataFrame({"subject": current["subject"].astype(str), "percentage": values, "z_score": z})
    result = result.sort_values("z_score", ascending=False)
    return {"available": True, "mean": _py(mean), "population_std": _py(std), "scores": _records(result)}


def consistency_table(df: pd.DataFrame) -> dict[str, Any]:
    data = add_percentage(df)
    if data["exam_order"].nunique() < 3:
        return _unavailable("At least 3 examinations are needed for consistency.")
    grouped = data.groupby("subject", sort=True)["percentage"]
    rows = []
    for subject, values in grouped:
        values = values.dropna()
        mean, std = float(values.mean()), float(values.std(ddof=1)) if len(values) > 1 else 0.0
        cv = abs(std / mean * 100) if mean else 0.0
        label = "highly consistent" if cv < 5 else "reasonably consistent" if cv < 10 else "variable"
        rows.append({"subject": str(subject), "n": len(values), "mean": mean, "std_dev": std, "cv_percent": cv,
                     "min": float(values.min()), "max": float(values.max()),
                     "range": float(values.max() - values.min()), "consistency": label})
    return {"available": True, "exams": int(data["exam_order"].nunique()), "cv_thresholds": "under 5% highly consistent; under 10% reasonably consistent",
            "subjects": [_records(pd.DataFrame([row]))[0] for row in rows]}


def _outliers(values: pd.Series) -> dict[str, Any]:
    x = values.dropna().astype(float)
    if len(x) < 3:
        return {"available": False, "reason": "At least 3 values are needed for outlier rules."}
    q1, q3 = np.percentile(x, [25, 75])
    iqr = q3 - q1
    low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    mean, std = x.mean(), x.std(ddof=0)
    z = np.zeros(len(x)) if std == 0 else (x - mean) / std
    return {"values": [{"value": _py(v), "iqr_flag": bool(v < low or v > high),
                        "z_flag": bool(abs(zv) > 2)} for v, zv in zip(x, z)],
            "n": len(x), "iqr_bounds": [_py(low), _py(high)], "minimum_n": 3}


def outlier_report(df: pd.DataFrame) -> dict[str, Any]:
    latest = _latest(df)
    within_exam = _outliers(latest["percentage"])
    history = {str(subject): _outliers(group["percentage"]) for subject, group in add_percentage(df).groupby("subject")}
    return {"available": True, "within_exam": within_exam, "subject_history": history,
            "rule": "IQR fences (Q1 - 1.5*IQR, Q3 + 1.5*IQR) and absolute z-score > 2."}


def moving_average(df: pd.DataFrame) -> dict[str, Any]:
    series = exam_overall_series(df)
    if len(series) < 3:
        return _unavailable("At least 3 examinations are needed for moving averages.")
    series["moving_average_2"] = series["percentage"].rolling(2).mean()
    series["moving_average_3"] = series["percentage"].rolling(3).mean()
    return {"available": True, "series": _records(series[["exam_order", "exam", "percentage", "moving_average_2", "moving_average_3"]])}


def subject_correlations(df: pd.DataFrame) -> dict[str, Any]:
    data = add_percentage(df)
    if data["exam_order"].nunique() < 4:
        return _unavailable("At least 4 examinations are needed for correlations.")
    wide = data.pivot_table(index="exam_order", columns="subject", values="percentage", aggfunc="mean")
    pearson, spearman = wide.corr(), wide.corr(method="spearman")
    pairs = []
    for i, left in enumerate(wide.columns):
        for right in wide.columns[i + 1:]:
            n = int(wide[[left, right]].dropna().shape[0])
            if n:
                pairs.append({"subject_a": str(left), "subject_b": str(right), "pearson": pearson.loc[left, right],
                              "spearman": spearman.loc[left, right], "n": n})
    positive = max(pairs, key=lambda x: x["pearson"]) if pairs else None
    negative = min(pairs, key=lambda x: x["pearson"]) if pairs else None
    return {"available": True, "n_exams": int(len(wide)), "pearson": _records(pearson.reset_index().rename(columns={"subject": "subject"})),
            "spearman": _records(spearman.reset_index().rename(columns={"subject": "subject"})),
            "pairs": [_py_record(p) for p in pairs], "strongest_positive": _py_record(positive),
            "strongest_negative": _py_record(negative),
            "note": "Correlation is not causation; the small sample makes these associations indicative only."}


def _py_record(record: dict[str, Any] | None) -> dict[str, Any] | None:
    return None if record is None else {k: _py(v) for k, v in record.items()}


def change_significance(df: pd.DataFrame, seed: int = 42, resamples: int = 5000) -> dict[str, Any]:
    series = exam_overall_series(df)
    if len(series) < 2:
        return _unavailable("Two examinations are needed for a change analysis.")
    current, previous = int(series.iloc[-1].exam_order), int(series.iloc[-2].exam_order)
    values = add_percentage(df[df.exam_order.isin([previous, current])]).pivot(index="subject", columns="exam_order", values="percentage").dropna()
    if len(values) < 4:
        return _unavailable("At least 4 shared subjects are needed for change significance.")
    change = (values[current] - values[previous]).to_numpy(float)
    mean = float(change.mean())
    sd = float(change.std(ddof=1))
    effect = mean / sd if sd else 0.0
    rng = np.random.default_rng(seed)
    boot = rng.choice(change, size=(resamples, len(change)), replace=True).mean(axis=1)
    ci = np.percentile(boot, [2.5, 97.5])
    return {"available": True, "n": len(change), "mean_change": _py(mean), "cohens_dz": _py(effect),
            "confidence_interval_95": [_py(ci[0]), _py(ci[1])], "seed": seed,
            "interpretation": "small sample, indicative only."}


def project_next_exam(df: pd.DataFrame) -> dict[str, Any]:
    series = exam_overall_series(df)
    if len(series) < 4:
        return _unavailable("At least 4 examinations are needed for an illustrative extrapolation.")
    x, y = np.arange(len(series), dtype=float), series["percentage"].to_numpy(float)
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    residual_std = float(np.std(y - fitted, ddof=1)) if len(y) > 1 else 0.0
    ss_tot, ss_res = np.sum((y - y.mean()) ** 2), np.sum((y - fitted) ** 2)
    r2 = 1.0 if ss_tot == 0 else 1 - ss_res / ss_tot
    projected = float(np.clip(slope * len(y) + intercept, 0, 100))
    return {"available": True, "slope": _py(slope), "intercept": _py(intercept), "r_squared": _py(r2),
            "residual_std": _py(residual_std), "projected_next": _py(projected),
            "range_95": [_py(max(0, projected - 1.96 * residual_std)), _py(min(100, projected + 1.96 * residual_std))],
            "label": "Illustrative linear extrapolation, NOT a prediction.",
            "series": _records(series[["exam_order", "exam", "percentage"]])}

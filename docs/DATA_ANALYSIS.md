# Data analysis toolkit

The analytics pages are deterministic and work without API keys. Every operation reports
`available: false` when its minimum sample rule is not met.

| Analysis | Formula / purpose | Minimum | Limitation |
|---|---|---:|---|
| Distribution shape | Bias and tail weight using corrected skewness and excess kurtosis | 4 subjects | Describes the current exam only |
| Standardized scores | `(subject % - current mean) / population std` | 3 subjects | Relative to this student, not a class |
| Consistency | Sample standard deviation and `CV = std / mean * 100` | 3 exams | CV is unstable near a zero mean |
| Outliers | Tukey IQR fences and `abs(z) > 2` | 3 values | Rules are screening tools, not diagnoses |
| Moving average | Pandas rolling means over 2 and 3 exams | 3 exams | Early windows are unavailable |
| Correlation | Pearson and rank-based Spearman coefficients | 4 exams | Correlation is not causation |
| Change significance | Mean paired change, Cohen's `d_z`, seeded bootstrap 95% interval | 4 shared subjects | Small sample, indicative only |
| Projection | `numpy.polyfit` line, R² and residual range | 4 exams | Illustrative extrapolation, not a prediction |
| Marks lost | `total - obtained`, sorted with cumulative Pareto share | 1 exam | Uses the latest exam |
| Target planner | Required marks at a requested overall percentage | 1 exam | Assumes the same total marks |
| Weighted score | Weighted mean of subject percentages | 1 exam | Weights represent user-supplied credit hours |

## Pandas/NumPy techniques

`pivot_table` in [explorer.py](../app/data_engine/explorer.py); `rolling`, `rank`, boolean masks
and `polyfit` in [advanced_stats.py](../app/data_engine/advanced_stats.py); and vectorized
arithmetic, `corr`, percentile calculations and bootstrap resampling throughout the same engine.

The student page is **Data Analysis Lab**.
The reproducible 40-student dataset can be regenerated with:

```powershell
.venv\Scripts\python.exe scripts\make_class_sample.py
```

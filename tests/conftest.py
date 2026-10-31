from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATA = Path(__file__).parent / "data" / "sample_marksheet.csv"


@pytest.fixture
def sample_raw() -> pd.DataFrame:
    return pd.read_csv(DATA)


@pytest.fixture
def sample_clean(sample_raw):
    from app.data_engine.preprocessing import clean_results

    cleaned, report = clean_results(sample_raw)
    assert report.is_valid
    return cleaned


@pytest.fixture
def profile() -> dict:
    return {"student_id": "s1", "name": "Test Student", "board": "AKU-EB", "country": "Pakistan", "grade": "HSSC 1",
            "academic_year": "2025-2026", "target_percentage": 75.0, "difficult_subjects": ["maths"],
            "difficult_topics": {"Mathematics": ["trigonometric identities"]}, "preferred_resources": ["Video lectures"],
            "preferred_language": None}

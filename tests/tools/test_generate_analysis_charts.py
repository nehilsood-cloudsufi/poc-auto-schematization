import os

import numpy as np
import pandas as pd
import pytest


def test_domain_palette_has_all_domains():
    from tools.generate_analysis_charts import DOMAIN_PALETTE
    expected = {
        "Census/Demographics", "Economics/Finance", "Health", "Education",
        "Employment/Labor", "Environment", "Crime/Safety", "Brazil/LatAm",
        "India", "Other/Misc",
    }
    assert set(DOMAIN_PALETTE.keys()) == expected


def test_get_outlier_indices_returns_top_and_bottom():
    from tools.generate_analysis_charts import get_outlier_indices
    x = list(range(10))
    y = list(range(10))
    y[3] = 100  # big positive outlier
    y[7] = -50  # big negative outlier
    indices = get_outlier_indices(x, y, n=2)
    assert 3 in indices
    assert 7 in indices
    assert len(indices) <= 4


def test_make_short_alias():
    from tools.generate_analysis_charts import make_short_alias
    assert make_short_alias("brazil_visdata_FoodBasketDistribution") == "brazil_FBD"
    assert make_short_alias("zurich_bev_3240_wiki") == "zurich_3240"
    assert make_short_alias("bis_bis_central_bank_policy_rate") == "bis_cbpr"
    assert make_short_alias("undata") == "undata"


def test_get_schema_coverage_tier():
    from tools.generate_analysis_charts import get_schema_coverage_tier
    assert get_schema_coverage_tier("Census/Demographics") == "Strong"
    assert get_schema_coverage_tier("Economics/Finance") == "Moderate"
    assert get_schema_coverage_tier("Crime/Safety") == "Weak"
    assert get_schema_coverage_tier("India") == "Weak"


# ---------------------------------------------------------------------------
# Smoke tests for chart generation
# ---------------------------------------------------------------------------

def test_generate_all_charts_produces_6_files(tmp_path, monkeypatch):
    from tools.generate_analysis_charts import generate_all_charts
    monkeypatch.setattr("tools.generate_analysis_charts.CHART_DIR", str(tmp_path))
    paths = generate_all_charts()
    assert len(paths) == 6
    for name, path in paths.items():
        assert os.path.exists(path), f"Chart {name} not created at {path}"
        assert os.path.getsize(path) > 1000, f"Chart {name} too small"


def test_chart_h1_returns_valid_png(tmp_path, monkeypatch):
    from tools.generate_analysis_charts import chart_h1_column_count, CSV_PATH
    monkeypatch.setattr("tools.generate_analysis_charts.CHART_DIR", str(tmp_path))
    df = pd.read_csv(CSV_PATH)
    path = chart_h1_column_count(df)
    assert path.endswith(".png")
    assert os.path.exists(path)

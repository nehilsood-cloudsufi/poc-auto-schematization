import pytest
import pandas as pd
import numpy as np


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

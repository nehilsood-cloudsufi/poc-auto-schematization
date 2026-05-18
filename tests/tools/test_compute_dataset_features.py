import pytest
from tools.compute_dataset_features import parse_comparison_table

SAMPLE_TABLE = """| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % |
|---------|---------------|--------------|----------------|
| dataset_a | 10.0 | 20.0 | **30.0** |
| dataset_b | 0.0 | 5.5 | 0.0 |
| dataset_c | **15.2** | 8.1 | 8.1 |
"""

def test_parse_comparison_table_extracts_gemini3pro():
    result = parse_comparison_table(SAMPLE_TABLE, model_column="Gemini 3 Pro %")
    assert result == {
        "dataset_a": 30.0,
        "dataset_b": 0.0,
        "dataset_c": 8.1,
    }

def test_parse_comparison_table_strips_bold_markers():
    result = parse_comparison_table(SAMPLE_TABLE, model_column="Gemini Base %")
    assert result["dataset_c"] == 15.2

def test_parse_comparison_table_missing_column_raises():
    with pytest.raises(ValueError, match="Column .* not found"):
        parse_comparison_table(SAMPLE_TABLE, model_column="Nonexistent %")


def test_extract_metrics_from_file(tmp_path):
    from tools.compute_dataset_features import extract_gemini3pro_metrics

    md_content = """# Comparison

## Node Accuracy Comparison

Node Accuracy = blah

| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % |
|---------|---------------|--------------|----------------|
| ds_a | 0.0 | 10.0 | **15.0** |
| ds_b | 5.0 | 5.0 | 0.0 |

---

## Node Coverage Comparison

Node Coverage = blah

| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % |
|---------|---------------|--------------|----------------|
| ds_a | 50.0 | 60.0 | **70.0** |
| ds_b | 30.0 | 40.0 | 40.0 |

---

## PV Accuracy Comparison

PV Accuracy = blah

| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % |
|---------|---------------|--------------|----------------|
| ds_a | 5.0 | 20.0 | **25.0** |
| ds_b | 0.0 | 3.0 | 3.0 |
"""
    md_file = tmp_path / "comparison.md"
    md_file.write_text(md_content)

    metrics = extract_gemini3pro_metrics(str(md_file))

    assert metrics["ds_a"]["pv_accuracy"] == 25.0
    assert metrics["ds_a"]["node_accuracy"] == 15.0
    assert metrics["ds_a"]["node_coverage"] == 70.0
    assert metrics["ds_b"]["pv_accuracy"] == 3.0


def test_extract_metrics_filters_to_nonzero(tmp_path):
    """49-dataset filter: keep datasets with at least one non-zero metric."""
    from tools.compute_dataset_features import extract_gemini3pro_metrics

    md_content = """# Comparison

## Node Accuracy Comparison

| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % |
|---------|---------------|--------------|----------------|
| has_data | 0.0 | 0.0 | **5.0** |
| all_zero | 0.0 | 0.0 | 0.0 |

---

## Node Coverage Comparison

| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % |
|---------|---------------|--------------|----------------|
| has_data | 0.0 | 0.0 | **50.0** |
| all_zero | 0.0 | 0.0 | 0.0 |

---

## PV Accuracy Comparison

| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % |
|---------|---------------|--------------|----------------|
| has_data | 0.0 | 0.0 | **10.0** |
| all_zero | 0.0 | 0.0 | 0.0 |
"""
    md_file = tmp_path / "comparison.md"
    md_file.write_text(md_content)

    metrics = extract_gemini3pro_metrics(str(md_file))
    assert "has_data" in metrics
    assert "all_zero" not in metrics


import pandas as pd

def test_extract_structural_features(tmp_path):
    from tools.compute_dataset_features import extract_structural_features

    # Create a test CSV: 3 numeric cols, 2 categorical cols, 20 rows
    df = pd.DataFrame({
        "year": [2020 + i % 5 for i in range(20)],
        "value": [float(i * 10) for i in range(20)],
        "rate": [0.1 * i for i in range(20)],
        "country": ["US", "UK", "FR", "DE", "JP"] * 4,
        "category": ["A", "B"] * 10,
    })
    csv_path = tmp_path / "test.csv"
    df.to_csv(csv_path, index=False)

    features = extract_structural_features(str(csv_path))

    assert features["column_count"] == 5
    assert features["row_count"] == 20
    assert features["numeric_column_count"] == 3  # year, value, rate
    assert features["categorical_column_count"] == 2  # country, category
    assert features["max_column_cardinality"] == 20  # value or rate have 20 unique
    assert features["mean_column_cardinality"] == pytest.approx(
        (5 + 20 + 20 + 5 + 2) / 5, rel=0.01
    )


def test_extract_structural_features_all_numeric(tmp_path):
    from tools.compute_dataset_features import extract_structural_features

    df = pd.DataFrame({"a": [1, 2, 3], "b": [4.0, 5.0, 6.0]})
    csv_path = tmp_path / "numeric.csv"
    df.to_csv(csv_path, index=False)

    features = extract_structural_features(str(csv_path))
    assert features["numeric_column_count"] == 2
    assert features["categorical_column_count"] == 0
    assert features["numeric_to_categorical_ratio"] == 0  # 0 when no categorical


def test_get_domain():
    from tools.compute_dataset_features import get_domain

    assert get_domain("bis_bis_central_bank_policy_rate") == "Economics/Finance"
    assert get_domain("brfss_nchs_asthma_prevalence") == "Health"
    assert get_domain("census_v2_sahie") == "Census/Demographics"
    assert get_domain("ccd_enrollment") == "Education"
    assert get_domain("undata") == "Other/Misc"
    assert get_domain("totally_unknown_dataset") == "Other/Misc"


def test_find_input_csv(tmp_path):
    from tools.compute_dataset_features import find_input_csv

    # Create fake input structure
    test_data = tmp_path / "my_dataset" / "test_data"
    test_data.mkdir(parents=True)
    (test_data / "my_dataset_input.csv").write_text("a,b\n1,2\n")

    result = find_input_csv("my_dataset", str(tmp_path))
    assert result is not None
    assert result.endswith("my_dataset_input.csv")


def test_find_input_csv_missing(tmp_path):
    from tools.compute_dataset_features import find_input_csv

    result = find_input_csv("nonexistent_dataset", str(tmp_path))
    assert result is None


def test_compute_correlations():
    from tools.compute_dataset_features import compute_correlations

    features_df = pd.DataFrame({
        "dataset": ["a", "b", "c", "d", "e", "f", "g", "h"],
        "pv_accuracy": [50.0, 40.0, 30.0, 20.0, 10.0, 5.0, 60.0, 70.0],
        "column_count": [3, 5, 8, 12, 20, 25, 2, 1],
        "row_count": [100, 200, 300, 400, 500, 600, 50, 25],
    })

    result = compute_correlations(features_df, target="pv_accuracy",
                                  factors=["column_count", "row_count"])

    assert len(result) == 2
    assert "factor" in result.columns
    assert "spearman_r" in result.columns
    assert "p_value" in result.columns
    assert "n" in result.columns
    # column_count should have negative correlation (more columns = lower accuracy)
    col_row = result[result["factor"] == "column_count"].iloc[0]
    assert col_row["spearman_r"] < 0
    assert col_row["n"] == 8

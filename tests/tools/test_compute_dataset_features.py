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

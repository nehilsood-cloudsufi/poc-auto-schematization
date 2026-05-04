import json
import pytest
from src.agents.pvmap_retry_loop import format_statvar_examples_for_prompt


def test_format_statvar_examples():
    examples = [
        {
            "dcid": "Count_Person_Male",
            "populationType": "dcs:Person",
            "measuredProperty": "dcs:count",
            "gender": "dcs:Male",
        },
        {
            "dcid": "Exports_EconomicActivity_Unspecified",
            "populationType": "dcs:EconomicActivity",
            "measuredProperty": "dcs:exports",
            "product": "dcs:Unspecified",
        },
    ]
    result = format_statvar_examples_for_prompt(examples)
    assert "Count_Person_Male" in result
    assert "populationType: dcs:Person" in result
    assert "measuredProperty: dcs:count" in result
    assert "gender: dcs:Male" in result
    assert "Exports_EconomicActivity_Unspecified" in result


def test_format_empty_examples():
    result = format_statvar_examples_for_prompt([])
    assert result == ""


def test_format_truncates_at_budget():
    examples = [{"dcid": f"SV_{i}", "populationType": "dcs:Person", "measuredProperty": "dcs:count"} for i in range(100)]
    result = format_statvar_examples_for_prompt(examples, max_chars=500)
    assert len(result) <= 600  # Allow some header overhead

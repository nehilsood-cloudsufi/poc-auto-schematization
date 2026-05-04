"""Tests for pricing."""
import json
from pathlib import Path

import pytest

from scripts.batch_lib.pricing import PricingTable, compute_cost


@pytest.fixture
def pricing_file(tmp_path: Path) -> Path:
    p = tmp_path / "pricing.json"
    p.write_text(json.dumps({
        "models": {
            "gemini-3.1-pro-preview": {
                "input_per_mtok": 1.25, "output_per_mtok": 10.0, "thoughts_per_mtok": 10.0,
                "is_estimate": True,
            },
            "gemini-3-flash-preview": {
                "input_per_mtok": 0.15, "output_per_mtok": 0.60, "thoughts_per_mtok": 0.60,
                "is_estimate": True,
            },
        },
        "fallback": {
            "input_per_mtok": 1.25, "output_per_mtok": 10.0, "thoughts_per_mtok": 10.0,
            "is_estimate": True,
        },
    }))
    return p


def test_pricing_table_loads(pricing_file: Path):
    pt = PricingTable.load(pricing_file)
    assert "gemini-3.1-pro-preview" in pt.models
    assert pt.models["gemini-3.1-pro-preview"]["input_per_mtok"] == 1.25


def test_compute_cost_pro(pricing_file: Path):
    pt = PricingTable.load(pricing_file)
    # 1M input, 1M output, 1M thoughts -> 1.25 + 10 + 10 = 21.25
    result = compute_cost(
        prompt_tokens=1_000_000, response_tokens=1_000_000, thoughts_tokens=1_000_000,
        model="gemini-3.1-pro-preview", pricing=pt,
    )
    assert result["cost_usd"] == pytest.approx(21.25, rel=1e-6)
    assert result["is_estimate"] is True


def test_compute_cost_flash_is_cheaper(pricing_file: Path):
    pt = PricingTable.load(pricing_file)
    r_pro = compute_cost(
        prompt_tokens=100_000, response_tokens=100_000, thoughts_tokens=0,
        model="gemini-3.1-pro-preview", pricing=pt,
    )
    r_flash = compute_cost(
        prompt_tokens=100_000, response_tokens=100_000, thoughts_tokens=0,
        model="gemini-3-flash-preview", pricing=pt,
    )
    assert r_flash["cost_usd"] < r_pro["cost_usd"]


def test_compute_cost_unknown_model_uses_fallback(pricing_file: Path):
    pt = PricingTable.load(pricing_file)
    r = compute_cost(
        prompt_tokens=0, response_tokens=0, thoughts_tokens=0,
        model="gemini-99-pro-preview", pricing=pt,
    )
    assert r["cost_usd"] == 0.0
    assert r["is_estimate"] is True
    assert r["model_used_for_pricing"] == "fallback"


def test_compute_cost_none_tokens_treated_as_zero(pricing_file: Path):
    """Missing token counts should be treated as 0, not crash."""
    pt = PricingTable.load(pricing_file)
    r = compute_cost(
        prompt_tokens=None, response_tokens=None, thoughts_tokens=None,
        model="gemini-3.1-pro-preview", pricing=pt,
    )
    assert r["cost_usd"] == 0.0

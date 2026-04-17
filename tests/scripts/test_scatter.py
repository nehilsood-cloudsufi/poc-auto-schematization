"""Tests for scatter plot writer."""
from pathlib import Path

import pytest

from scripts.batch_lib.scatter import write_scatter


def test_write_scatter_produces_png(tmp_path: Path):
    records = [
        {"dataset": "a", "complexity": {"raw_rows": 100},  "tokens_total": {"total": 1000}, "timing_seconds": {"total": 10.0}},
        {"dataset": "b", "complexity": {"raw_rows": 1000}, "tokens_total": {"total": 5000}, "timing_seconds": {"total": 30.0}},
        {"dataset": "c", "complexity": {"raw_rows": 10000},"tokens_total": {"total": 25000},"timing_seconds": {"total": 120.0}},
    ]
    out = tmp_path / "scatter.png"
    write_scatter(records, out, x_key=("complexity", "raw_rows"), y_key=("tokens_total", "total"), title="tokens vs rows", log_scale=True)
    assert out.exists()
    assert out.stat().st_size > 100


def test_write_scatter_skips_none_values(tmp_path: Path):
    """Datasets with missing x/y don't break the plot."""
    records = [
        {"dataset": "a", "complexity": {"raw_rows": 100},  "tokens_total": {"total": 1000}, "timing_seconds": {"total": 10.0}},
        {"dataset": "b", "complexity": {"raw_rows": None}, "tokens_total": {"total": 5000}, "timing_seconds": {"total": None}},
    ]
    out = tmp_path / "scatter.png"
    write_scatter(records, out, x_key=("complexity", "raw_rows"), y_key=("tokens_total", "total"), title="x", log_scale=True)
    assert out.exists()

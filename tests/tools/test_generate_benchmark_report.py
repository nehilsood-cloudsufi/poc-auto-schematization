import pytest


def test_verdict_color():
    from tools.generate_benchmark_report import get_verdict_color
    assert get_verdict_color("SUPPORTED") == "2E7D32"  # green
    assert get_verdict_color("REJECTED") == "C62828"  # red
    assert get_verdict_color("PARTIALLY SUPPORTED") == "E65100"  # orange


def test_format_stat_row():
    from tools.generate_benchmark_report import format_stat_row
    row = format_stat_row(spearman_r=-0.099, p_value=0.499, n=48)
    assert row["Spearman r"] == "-0.099"
    assert row["p-value"] == "0.499"
    assert row["N"] == "48"
    assert row["Significant (p<0.05)"] == "No"


def test_format_stat_row_significant():
    from tools.generate_benchmark_report import format_stat_row
    row = format_stat_row(spearman_r=0.45, p_value=0.001, n=48)
    assert row["Significant (p<0.05)"] == "Yes"

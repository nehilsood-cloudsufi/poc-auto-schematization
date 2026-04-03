"""Tests for the benchmark runner."""
import json
import os
import tempfile

import pytest


def test_collect_metrics_success():
    """collect_metrics extracts Node Accuracy, Node Coverage, PV Accuracy from diff_results.json."""
    from tools.run_benchmark import collect_metrics

    with tempfile.TemporaryDirectory() as tmpdir:
        dataset = "test_dataset"
        eval_dir = os.path.join(tmpdir, dataset, "eval_results")
        os.makedirs(eval_dir)

        counters = {
            "nodes-ground-truth": 100,
            "nodes-auto-generated": 80,
            "nodes-matched": 20,
            "nodes-with-diff": 30,
            "PVs-matched": 50,
            "pvs-modified": 10,
            "pvs-deleted": 40,
            "pvs-added": 5,
        }
        with open(os.path.join(eval_dir, "diff_results.json"), "w") as f:
            json.dump(counters, f)

        result = collect_metrics(dataset, tmpdir)

        assert result is not None
        assert result["node_accuracy"] == 20.0
        assert result["node_coverage"] == 50.0
        assert result["pv_accuracy"] == 50.0


def test_collect_metrics_missing_file():
    """collect_metrics returns None when diff_results.json doesn't exist."""
    from tools.run_benchmark import collect_metrics

    with tempfile.TemporaryDirectory() as tmpdir:
        result = collect_metrics("nonexistent", tmpdir)
        assert result is None


def test_collect_metrics_zero_ground_truth():
    """collect_metrics handles zero ground truth nodes gracefully."""
    from tools.run_benchmark import collect_metrics

    with tempfile.TemporaryDirectory() as tmpdir:
        dataset = "empty_dataset"
        eval_dir = os.path.join(tmpdir, dataset, "eval_results")
        os.makedirs(eval_dir)

        counters = {
            "nodes-ground-truth": 0,
            "nodes-auto-generated": 0,
            "nodes-matched": 0,
            "nodes-with-diff": 0,
            "PVs-matched": 0,
            "pvs-modified": 0,
            "pvs-deleted": 0,
            "pvs-added": 0,
        }
        with open(os.path.join(eval_dir, "diff_results.json"), "w") as f:
            json.dump(counters, f)

        result = collect_metrics(dataset, tmpdir)
        assert result is not None
        assert result["node_accuracy"] == 0.0
        assert result["node_coverage"] == 0.0
        assert result["pv_accuracy"] == 0.0


def test_parse_comparison_md():
    """parse_comparison_md extracts baseline metrics from the existing comparison doc."""
    from tools.run_benchmark import parse_comparison_md

    md_content = """# Auto-Schematization Evaluation Benchmark Comparison

## Node Accuracy Comparison

| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % |
|---------|---------------|--------------|----------------|
| bis_bis_central_bank_policy_rate | 0.0 | **14.3** | 14.3 |
| brfss_nchs_asthma_prevalence | 0.0 | 21.1 | **26.1** |

---

## Node Coverage Comparison

| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % |
|---------|---------------|--------------|----------------|
| bis_bis_central_bank_policy_rate | 100.0 | 100.0 | **114.3** |
| brfss_nchs_asthma_prevalence | 20.0 | 63.2 | **269.6** |

---

## PV Accuracy Comparison

| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % |
|---------|---------------|--------------|----------------|
| bis_bis_central_bank_policy_rate | 0.0 | 18.2 | **36.4** |
| brfss_nchs_asthma_prevalence | 1.5 | **23.3** | 19.1 |
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(md_content)
        f.flush()
        try:
            baseline = parse_comparison_md(f.name)
        finally:
            os.unlink(f.name)

    assert "bis_bis_central_bank_policy_rate" in baseline
    bis = baseline["bis_bis_central_bank_policy_rate"]
    assert bis["gemini_base"]["node_accuracy"] == 0.0
    assert bis["claude_cli"]["node_accuracy"] == 14.3
    assert bis["gemini_3_pro"]["node_accuracy"] == 14.3
    assert bis["gemini_base"]["pv_accuracy"] == 0.0
    assert bis["claude_cli"]["pv_accuracy"] == 18.2
    assert bis["gemini_3_pro"]["pv_accuracy"] == 36.4

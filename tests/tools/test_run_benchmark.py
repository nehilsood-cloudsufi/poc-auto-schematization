"""Tests for the benchmark runner."""
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

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

## Summary Statistics

| Metric | Gemini (Base) | Claude CLI | Gemini 3 Pro |
|--------|---------------|------------|--------------|
| Total Datasets Evaluated | 2 | 2 | 2 |
| Average Node Accuracy | 0.0% | 17.7% | 20.2% |
| Average Node Coverage | 60.0% | 81.6% | 191.9% |
| Average PV Accuracy | 0.8% | 20.8% | 27.8% |

---

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


def test_generate_comparison_md():
    """generate_comparison_md produces a markdown file with 4 model columns + time."""
    from tools.run_benchmark import generate_comparison_md

    baseline = {
        "bis_bis_central_bank_policy_rate": {
            "gemini_base": {"node_accuracy": 0.0, "node_coverage": 100.0, "pv_accuracy": 0.0},
            "claude_cli": {"node_accuracy": 14.3, "node_coverage": 100.0, "pv_accuracy": 18.2},
            "gemini_3_pro": {"node_accuracy": 14.3, "node_coverage": 114.3, "pv_accuracy": 36.4},
        },
        "brfss_nchs_asthma_prevalence": {
            "gemini_base": {"node_accuracy": 0.0, "node_coverage": 20.0, "pv_accuracy": 1.5},
            "claude_cli": {"node_accuracy": 21.1, "node_coverage": 63.2, "pv_accuracy": 23.3},
            "gemini_3_pro": {"node_accuracy": 26.1, "node_coverage": 269.6, "pv_accuracy": 19.1},
        },
        "__summary__": {
            "gemini_base": {"node_accuracy": 0.0, "node_coverage": 60.0, "pv_accuracy": 0.8, "total": 2},
            "claude_cli": {"node_accuracy": 17.7, "node_coverage": 81.6, "pv_accuracy": 20.8, "total": 2},
            "gemini_3_pro": {"node_accuracy": 20.2, "node_coverage": 191.9, "pv_accuracy": 27.8, "total": 2},
        },
    }

    enhanced_results = {
        "bis_bis_central_bank_policy_rate": {
            "node_accuracy": 25.0,
            "node_coverage": 85.7,
            "pv_accuracy": 40.2,
            "elapsed_seconds": 187.3,
        },
        "brfss_nchs_asthma_prevalence": {
            "node_accuracy": 30.0,
            "node_coverage": 80.0,
            "pv_accuracy": 28.0,
            "elapsed_seconds": 220.1,
        },
    }

    run_config = {
        "branch": "test-branch",
        "commit": "abc1234",
        "timestamp": "2026-04-03T12:00:00",
        "flags": ["--prompt-version v3"],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        output_path = f.name

    try:
        generate_comparison_md(baseline, enhanced_results, run_config, output_path)

        with open(output_path) as f:
            content = f.read()

        assert "Enhanced Pipeline" in content
        assert "Time (s)" in content
        assert "Node Accuracy" in content
        assert "Node Coverage" in content
        assert "PV Accuracy" in content
        assert "bis_bis_central_bank_policy_rate" in content
        assert "25.0" in content
        assert "187.3" in content
        assert "**40.2**" in content  # Best PV accuracy for bis
    finally:
        os.unlink(output_path)


def test_run_single_dataset_success():
    """run_single_dataset returns a DatasetResult with timing and exit code."""
    from tools.run_benchmark import run_single_dataset, DatasetResult

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "Pipeline completed"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        result = run_single_dataset("test_dataset", "/tmp/output")

    assert isinstance(result, DatasetResult)
    assert result.dataset == "test_dataset"
    assert result.exit_code == 0
    assert result.elapsed_seconds >= 0
    assert result.error_message is None


def test_run_single_dataset_quota_error():
    """run_single_dataset detects quota errors from stderr."""
    from tools.run_benchmark import run_single_dataset

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "google.api_core.exceptions.ResourceExhausted: 429 Quota exceeded"

    with patch("subprocess.run", return_value=mock_result):
        result = run_single_dataset("test_dataset", "/tmp/output")

    assert result.exit_code == 1
    assert result.error_message is not None
    assert "quota" in result.error_message.lower() or "429" in result.error_message


def test_run_single_dataset_timeout():
    """run_single_dataset handles subprocess timeout."""
    import subprocess as sp
    from tools.run_benchmark import run_single_dataset

    with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="test", timeout=900)):
        result = run_single_dataset("test_dataset", "/tmp/output")

    assert result.exit_code == -1
    assert "timeout" in result.error_message.lower()


def test_run_batch_categorizes_results():
    """run_batch categorizes results into successes, failures, and quota_failures."""
    from tools.run_benchmark import run_batch, DatasetResult

    results = [
        DatasetResult(dataset="d1", exit_code=0, elapsed_seconds=10.0),
        DatasetResult(dataset="d2", exit_code=1, error_message="Pipeline failed (exit 1): some error"),
        DatasetResult(dataset="d3", exit_code=1, error_message="Quota/rate limit error (exit 1)"),
    ]

    with patch("tools.run_benchmark.run_single_dataset", side_effect=results):
        successes, failures, quota_failures = run_batch(
            ["d1", "d2", "d3"], "/tmp/output", max_parallel=3
        )

    assert len(successes) == 1
    assert successes[0].dataset == "d1"
    assert len(failures) == 1
    assert failures[0].dataset == "d2"
    assert len(quota_failures) == 1
    assert quota_failures[0].dataset == "d3"


def test_save_and_load_manifest():
    """Manifest is saved incrementally and can be loaded for resume."""
    from tools.run_benchmark import save_manifest, load_manifest

    with tempfile.TemporaryDirectory() as tmpdir:
        manifest_path = os.path.join(tmpdir, "benchmark_results.json")
        run_config = {"branch": "test", "commit": "abc", "timestamp": "now", "flags": []}

        results_1 = {"dataset_a": {"node_accuracy": 10.0, "node_coverage": 50.0, "pv_accuracy": 5.0, "elapsed_seconds": 100.0}}
        save_manifest(manifest_path, run_config, results_1)

        loaded = load_manifest(manifest_path)
        assert loaded["run_config"]["branch"] == "test"
        assert "dataset_a" in loaded["results"]

        results_2 = {"dataset_b": {"node_accuracy": 20.0, "node_coverage": 60.0, "pv_accuracy": 15.0, "elapsed_seconds": 200.0}}
        save_manifest(manifest_path, run_config, results_2)

        loaded = load_manifest(manifest_path)
        assert "dataset_a" in loaded["results"]
        assert "dataset_b" in loaded["results"]


def test_load_manifest_missing_file():
    """load_manifest returns None for non-existent file."""
    from tools.run_benchmark import load_manifest

    result = load_manifest("/tmp/nonexistent_benchmark_results.json")
    assert result is None

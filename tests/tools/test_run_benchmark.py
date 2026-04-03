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

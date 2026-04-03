"""Batch benchmark runner for the PVMAP generation pipeline.

Runs the pipeline on multiple datasets in parallel batches, collects
evaluation metrics, and generates a comparison markdown report.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class DatasetResult:
    """Result from a single pipeline run."""
    dataset: str
    exit_code: int = -1
    elapsed_seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""
    error_message: str | None = None
    node_accuracy: float | None = None
    node_coverage: float | None = None
    pv_accuracy: float | None = None


def collect_metrics(dataset: str, output_dir: str) -> dict | None:
    """Extract evaluation metrics from a completed pipeline run.

    Reads diff_results.json and computes Node Accuracy, Node Coverage,
    and PV Accuracy from raw counters.

    Returns None if the results file doesn't exist.
    """
    results_path = os.path.join(output_dir, dataset, "eval_results", "diff_results.json")
    if not os.path.exists(results_path):
        return None

    with open(results_path) as f:
        counters = json.load(f)

    nodes_gt = counters.get("nodes-ground-truth", 0)
    nodes_matched = counters.get("nodes-matched", 0)
    nodes_with_diff = counters.get("nodes-with-diff", 0)
    pvs_matched = counters.get("PVs-matched", 0)
    pvs_modified = counters.get("pvs-modified", 0)
    pvs_deleted = counters.get("pvs-deleted", 0)

    node_accuracy = (nodes_matched / nodes_gt * 100) if nodes_gt else 0.0
    node_coverage = ((nodes_matched + nodes_with_diff) / nodes_gt * 100) if nodes_gt else 0.0

    pv_denom = pvs_matched + pvs_modified + pvs_deleted
    pv_accuracy = (pvs_matched / pv_denom * 100) if pv_denom else 0.0

    return {
        "node_accuracy": round(node_accuracy, 1),
        "node_coverage": round(node_coverage, 1),
        "pv_accuracy": round(pv_accuracy, 1),
    }

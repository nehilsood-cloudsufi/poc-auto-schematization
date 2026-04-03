"""Batch benchmark runner for the PVMAP generation pipeline.

Runs the pipeline on multiple datasets in parallel batches, collects
evaluation metrics, and generates a comparison markdown report.
"""
from __future__ import annotations

import json
import os
import re
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


def parse_comparison_md(filepath: str) -> dict[str, dict]:
    """Parse the existing Gemini_vs_Claude_Comparison.md to extract baseline metrics.

    Returns: {dataset_name: {gemini_base: {node_accuracy, node_coverage, pv_accuracy},
                             claude_cli: {...}, gemini_3_pro: {...}}}
    """
    with open(filepath) as f:
        content = f.read()

    sections = re.split(r"^## ", content, flags=re.MULTILINE)

    metric_map = {
        "Node Accuracy": "node_accuracy",
        "Node Coverage": "node_coverage",
        "PV Accuracy": "pv_accuracy",
    }

    baseline: dict[str, dict] = {}

    for section in sections:
        metric_key = None
        for heading, key in metric_map.items():
            if section.startswith(heading):
                metric_key = key
                break
        if not metric_key:
            continue

        for line in section.split("\n"):
            line = line.strip()
            if not line.startswith("|") or line.startswith("| Dataset") or line.startswith("|--"):
                continue

            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c or c == "0"]
            if len(cells) < 4:
                continue

            dataset = cells[0].strip()
            if dataset == "Dataset" or dataset.startswith("--"):
                continue

            def parse_val(s: str) -> float:
                s = s.replace("**", "").strip()
                try:
                    return float(s)
                except ValueError:
                    return 0.0

            gemini_base = parse_val(cells[1])
            claude_cli = parse_val(cells[2])
            gemini_3_pro = parse_val(cells[3])

            if dataset not in baseline:
                baseline[dataset] = {
                    "gemini_base": {},
                    "claude_cli": {},
                    "gemini_3_pro": {},
                }

            baseline[dataset]["gemini_base"][metric_key] = gemini_base
            baseline[dataset]["claude_cli"][metric_key] = claude_cli
            baseline[dataset]["gemini_3_pro"][metric_key] = gemini_3_pro

    return baseline

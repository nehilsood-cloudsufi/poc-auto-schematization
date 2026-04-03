"""Batch benchmark runner for the PVMAP generation pipeline.

Runs the pipeline on multiple datasets in parallel batches, collects
evaluation metrics, and generates a comparison markdown report.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
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


def generate_comparison_md(
    baseline: dict[str, dict],
    enhanced_results: dict[str, dict],
    run_config: dict,
    output_path: str,
) -> None:
    """Generate the Enhanced_Pipeline_Comparison.md file."""
    all_datasets = sorted(set(list(baseline.keys()) + list(enhanced_results.keys())))

    lines = [
        "# Enhanced Pipeline Benchmark Comparison",
        "",
        f"**Generated**: {run_config.get('timestamp', 'unknown')}",
        f"**Branch**: `{run_config.get('branch', 'unknown')}`",
        f"**Commit**: `{run_config.get('commit', 'unknown')}`",
        f"**Flags**: `{' '.join(run_config.get('flags', []))}`",
        "",
        "---",
        "",
    ]

    # Summary Statistics
    metrics = ["node_accuracy", "node_coverage", "pv_accuracy"]
    metric_labels = {
        "node_accuracy": "Average Node Accuracy",
        "node_coverage": "Average Node Coverage",
        "pv_accuracy": "Average PV Accuracy",
    }
    models = ["gemini_base", "claude_cli", "gemini_3_pro", "enhanced"]
    model_headers = ["Gemini (Base)", "Claude CLI", "Gemini 3 Pro", "Enhanced Pipeline"]

    lines.append("## Summary Statistics")
    lines.append("")
    lines.append(f"| Metric | {' | '.join(model_headers)} |")
    lines.append(f"|{'|'.join(['--------'] * (len(models) + 1))}|")

    total_datasets = len(all_datasets)
    lines.append(f"| Total Datasets Evaluated | {total_datasets} | {total_datasets} | {total_datasets} | {len(enhanced_results)} |")

    for metric in metrics:
        avgs = []
        for model in models:
            if model == "enhanced":
                vals = [r[metric] for r in enhanced_results.values() if metric in r]
            else:
                vals = [baseline[d][model].get(metric, 0.0) for d in all_datasets if d in baseline and model in baseline[d]]
            avg = sum(vals) / len(vals) if vals else 0.0
            avgs.append(f"{avg:.1f}%")
        lines.append(f"| {metric_labels[metric]} | {' | '.join(avgs)} |")

    lines.extend(["", "---", ""])

    # Per-metric tables
    table_configs = [
        ("Node Accuracy Comparison", "node_accuracy"),
        ("Node Coverage Comparison", "node_coverage"),
        ("PV Accuracy Comparison", "pv_accuracy"),
    ]

    for table_title, metric in table_configs:
        lines.append(f"## {table_title}")
        lines.append("")
        lines.append("| Dataset | Gemini Base % | Claude CLI % | Gemini 3 Pro % | Enhanced Pipeline % | Time (s) |")
        lines.append("|---------|---------------|--------------|----------------|---------------------|----------|")

        for dataset in all_datasets:
            vals = []

            for model in ["gemini_base", "claude_cli", "gemini_3_pro"]:
                if dataset in baseline and model in baseline[dataset]:
                    vals.append(baseline[dataset][model].get(metric, 0.0))
                else:
                    vals.append(0.0)

            if dataset in enhanced_results and metric in enhanced_results[dataset]:
                enhanced_val = enhanced_results[dataset][metric]
                vals.append(enhanced_val)
            else:
                enhanced_val = None
                vals.append(None)

            elapsed = enhanced_results.get(dataset, {}).get("elapsed_seconds")

            numeric_vals = [v for v in vals if v is not None]
            best = max(numeric_vals) if numeric_vals else None

            def fmt(v, is_best):
                if v is None:
                    return "\u2014"
                s = f"{v:.1f}" if isinstance(v, float) else str(v)
                return f"**{s}**" if is_best and v == best and v > 0 else s

            cells = [fmt(v, True) for v in vals]
            time_cell = f"{elapsed:.1f}" if elapsed is not None else "\u2014"

            lines.append(f"| {dataset} | {' | '.join(cells)} | {time_cell} |")

        lines.extend(["", "---", ""])

    with open(output_path, "w") as f:
        f.write("\n".join(lines))


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PIPELINE_FLAGS = [
    "--prompt-version", "v3",
    "--feedback-prompt-version", "v2",
    "--use-llm-judge",
    "--enable-mcp",
    "--auto-approve",
    "--force-resample",
    "--force-schema-selection",
]

SUBPROCESS_TIMEOUT = 900  # 15 minutes

QUOTA_PATTERNS = re.compile(r"429|resourceexhausted|quota", re.IGNORECASE)


def run_single_dataset(dataset: str, output_dir: str) -> DatasetResult:
    """Run the pipeline for a single dataset and return the result with timing."""
    cmd = [
        sys.executable,
        os.path.join(BASE_DIR, "src", "run_pipeline.py"),
        f"--dataset={dataset}",
        f"--output-dir={output_dir}",
        *PIPELINE_FLAGS,
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{BASE_DIR}:{os.path.join(BASE_DIR, 'src')}"

    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
            env=env,
            cwd=BASE_DIR,
        )
        elapsed = time.monotonic() - start

        error_msg = None
        if proc.returncode != 0:
            combined = proc.stdout + proc.stderr
            if QUOTA_PATTERNS.search(combined):
                error_msg = f"Quota/rate limit error (exit {proc.returncode})"
            else:
                error_msg = f"Pipeline failed (exit {proc.returncode}): {proc.stderr[-500:]}"

        return DatasetResult(
            dataset=dataset,
            exit_code=proc.returncode,
            elapsed_seconds=round(elapsed, 1),
            stdout=proc.stdout,
            stderr=proc.stderr,
            error_message=error_msg,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        return DatasetResult(
            dataset=dataset,
            exit_code=-1,
            elapsed_seconds=round(elapsed, 1),
            error_message=f"Timeout after {SUBPROCESS_TIMEOUT}s",
        )

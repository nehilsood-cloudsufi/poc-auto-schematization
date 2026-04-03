"""Batch benchmark runner for the PVMAP generation pipeline.

Runs the pipeline on multiple datasets in parallel batches, collects
evaluation metrics, and generates a comparison markdown report.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone


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


from concurrent.futures import ThreadPoolExecutor, as_completed


def _is_quota_error(result: DatasetResult) -> bool:
    """Check if a result represents a quota/rate limit error."""
    if result.error_message and ("quota" in result.error_message.lower() or "429" in result.error_message):
        return True
    return False


def run_batch(
    datasets: list[str],
    output_dir: str,
    max_parallel: int = 3,
) -> tuple[list[DatasetResult], list[DatasetResult], list[DatasetResult]]:
    """Run a batch of datasets in parallel.

    Returns: (successes, failures, quota_failures)
    """
    successes = []
    failures = []
    quota_failures = []

    with ThreadPoolExecutor(max_workers=max_parallel) as executor:
        future_to_dataset = {
            executor.submit(run_single_dataset, ds, output_dir): ds
            for ds in datasets
        }

        for future in as_completed(future_to_dataset):
            result = future.result()
            if result.exit_code == 0:
                successes.append(result)
            elif _is_quota_error(result):
                quota_failures.append(result)
            else:
                failures.append(result)

    return successes, failures, quota_failures


def load_manifest(path: str) -> dict | None:
    """Load an existing benchmark manifest. Returns None if file doesn't exist."""
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def save_manifest(path: str, run_config: dict, new_results: dict[str, dict]) -> None:
    """Save results to the manifest, merging with any existing results."""
    existing = load_manifest(path)
    if existing:
        existing["results"].update(new_results)
        existing["run_config"] = run_config
    else:
        existing = {"run_config": run_config, "results": new_results}

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w") as f:
        json.dump(existing, f, indent=2)


DATASETS = [
    "bis_bis_central_bank_policy_rate",
    "brazil_sidra_ibge",
    "brazil_visdata_FoodBasketDistribution",
    "brazil_visdata_brazil_rural_development_program",
    "brfss_nchs_asthma_prevalence",
    "ccd_enrollment",
    "cdc_social_vulnerability_index",
    "census_v2_sahie",
    "census_v2_saipe",
    "child_birth",
    "commerce_eda",
    "crdc_import_crdc_harassment_or_bullying",
    "crdc_instructional_wifi_devices",
    "database_on_indian_economy_india_rbi_state_statistics",
    "doctoratedegreeemployment",
    "fao_currency_and_exchange_rate",
    "fbi_fbigovcrime",
    "finland_census",
    "google_sustainability_financial_incentives",
    "india_ndap",
    "india_ndap_india_nss_health_ailments",
    "india_nfhs",
    "india_rbistatedomesticproduct",
    "inpe_fire",
    "ipeds",
    "ireland_census",
    "mexico_subnational_population_statistics_mexico_census_aa2",
    "ncses_median_annual_salary",
    "ncses_ncses_demographics_seh_import",
    "ncses_research_doctorate_recipients",
    "ntia_internet_use_survey",
    "nyu_diabetes_texas",
    "oecd_regional_education",
    "oecd_wastewater_treatment",
    "opendataforafrica_ethiopia_statistics",
    "opendataforafrica_kenya_census",
    "opendataforafrica_rwanda_census",
    "school_algebra1",
    "school_finance",
    "school_retention",
    "southkorea_statistics_education",
    "southkorea_statistics_employment",
    "southkorea_statistics_health",
    "statistics_new_zealand_new_zealand_census",
    "uae_bayanat",
    "undata",
    "us_bachelors_degree_data",
    "us_bls_bls_ces",
    "us_bls_bls_ces_state",
    "us_bls_cpi_category",
    "us_bls_us_cpi",
    "us_cdc_single_race",
    "us_census",
    "us_census_us_monthly_retail_sales",
    "us_crash_fars_crashdata",
    "us_federal_reserve_h15_interest_rates",
    "us_steam_degrees_data",
    "us_urban_school_teachers",
    "usa_dol",
    "usa_dol_minimum_wage",
    "world_bank_commodity_market",
    "zurich_bev_3240_wiki",
    "zurich_bev_3903_age10_wiki",
    "zurich_bev_3903_hel_wiki",
    "zurich_bev_3903_sex_wiki",
    "zurich_bev_4031_hel_wiki",
    "zurich_bev_4031_sex_wiki",
    "zurich_bev_4031_wiki",
    "zurich_wir_2552_wiki",
]

BATCH_COOLDOWN = 30  # seconds between batches

COMPARISON_SOURCE = os.path.join(BASE_DIR, "analysis", "Gemini_vs_Claude_Comparison.md")


def _get_run_config() -> dict:
    """Build run configuration metadata."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=BASE_DIR,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=BASE_DIR,
        ).stdout.strip()
    except Exception:
        commit = "unknown"
        branch = "unknown"

    return {
        "branch": branch,
        "commit": commit,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "flags": PIPELINE_FLAGS,
    }


def main():
    parser = argparse.ArgumentParser(description="Run enhanced pipeline benchmark on all datasets")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from existing results manifest")
    parser.add_argument("--datasets", type=str, default=None,
                        help="Comma-separated list of specific datasets to run")
    parser.add_argument("--batch-size", type=int, default=3,
                        help="Number of parallel runs per batch (default: 3)")
    parser.add_argument("--output-dir", type=str,
                        default=os.path.join(BASE_DIR, "output", "enhanced_benchmark"),
                        help="Output directory for pipeline results")
    args = parser.parse_args()

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    manifest_path = os.path.join(output_dir, "benchmark_results.json")
    run_config = _get_run_config()

    # Determine which datasets to run
    if args.datasets:
        datasets_to_run = [d.strip() for d in args.datasets.split(",")]
    else:
        datasets_to_run = list(DATASETS)

    # Filter datasets that have input data
    input_dir = os.path.join(BASE_DIR, "input")
    datasets_to_run = [d for d in datasets_to_run if os.path.isdir(os.path.join(input_dir, d))]

    # Resume: skip already-completed datasets
    if args.resume:
        existing = load_manifest(manifest_path)
        if existing:
            completed = set(existing["results"].keys())
            skipped = [d for d in datasets_to_run if d in completed]
            datasets_to_run = [d for d in datasets_to_run if d not in completed]
            print(f"Resuming: skipping {len(skipped)} already-completed datasets")

    if not datasets_to_run:
        print("No datasets to run.")
        return

    print(f"Running enhanced pipeline benchmark on {len(datasets_to_run)} datasets")
    print(f"Output: {output_dir}")
    print(f"Batch size: {args.batch_size}")
    print(f"Branch: {run_config['branch']} @ {run_config['commit']}")
    print()

    # Split into batches
    batch_size = args.batch_size
    batches = [datasets_to_run[i:i + batch_size]
               for i in range(0, len(datasets_to_run), batch_size)]
    total_batches = len(batches)

    all_successes = []
    all_failures = []
    all_quota_failures = []
    total_start = time.monotonic()

    for batch_idx, batch in enumerate(batches, 1):
        batch_start = time.monotonic()
        print(f"\n[Batch {batch_idx}/{total_batches}] Running: {', '.join(batch)}")

        successes, failures, quota_failures = run_batch(batch, output_dir, max_parallel=batch_size)

        batch_elapsed = time.monotonic() - batch_start
        total_elapsed = time.monotonic() - total_start

        all_successes.extend(successes)
        all_failures.extend(failures)
        all_quota_failures.extend(quota_failures)

        # Collect metrics and save manifest for this batch
        batch_metrics = {}
        for result in successes:
            metrics = collect_metrics(result.dataset, output_dir)
            if metrics:
                metrics["elapsed_seconds"] = result.elapsed_seconds
                batch_metrics[result.dataset] = metrics

        if batch_metrics:
            save_manifest(manifest_path, run_config, batch_metrics)

        print(f"[Batch {batch_idx}/{total_batches}] Completed: "
              f"{len(successes)} success, {len(failures)} fail, "
              f"{len(quota_failures)} quota-fail "
              f"[batch: {batch_elapsed:.0f}s, total: {total_elapsed:.0f}s]")

        for r in failures:
            print(f"  FAIL: {r.dataset} - {r.error_message}")
        for r in quota_failures:
            print(f"  QUOTA: {r.dataset} - {r.error_message}")

        # Cooldown between batches (not after the last one)
        if batch_idx < total_batches:
            print(f"  Cooling down {BATCH_COOLDOWN}s...")
            time.sleep(BATCH_COOLDOWN)

    # Retry quota failures
    if all_quota_failures:
        print(f"\n--- Retrying {len(all_quota_failures)} quota failures ---")
        retry_datasets = [r.dataset for r in all_quota_failures]
        time.sleep(BATCH_COOLDOWN)

        successes, failures, still_quota = run_batch(
            retry_datasets, output_dir, max_parallel=batch_size
        )
        all_successes.extend(successes)
        all_failures.extend(failures + still_quota)

        retry_metrics = {}
        for result in successes:
            metrics = collect_metrics(result.dataset, output_dir)
            if metrics:
                metrics["elapsed_seconds"] = result.elapsed_seconds
                retry_metrics[result.dataset] = metrics

        if retry_metrics:
            save_manifest(manifest_path, run_config, retry_metrics)

        print(f"Retry results: {len(successes)} recovered, "
              f"{len(failures) + len(still_quota)} still failed")

    # Final summary
    total_elapsed = time.monotonic() - total_start
    print(f"\n{'=' * 60}")
    print(f"BENCHMARK COMPLETE ({total_elapsed:.0f}s total)")
    print(f"  Success: {len(all_successes)}")
    print(f"  Failed:  {len(all_failures)}")
    print(f"{'=' * 60}")

    # Generate comparison markdown
    manifest = load_manifest(manifest_path)
    if manifest:
        baseline = parse_comparison_md(COMPARISON_SOURCE)
        comparison_path = os.path.join(BASE_DIR, "analysis", "Enhanced_Pipeline_Comparison.md")
        generate_comparison_md(baseline, manifest["results"], run_config, comparison_path)
        print(f"\nComparison report: {comparison_path}")
    else:
        print("\nNo results to generate comparison report.")

    print(f"Results manifest: {manifest_path}")


if __name__ == "__main__":
    main()

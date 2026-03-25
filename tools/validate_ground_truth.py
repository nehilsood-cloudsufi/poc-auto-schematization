#!/usr/bin/env python3
"""Validate ground truth PVMAPs by running stat_var_processor on each.

Reads the 48 datasets from analysis/factor_analysis/dataset_features_and_accuracy.csv,
resolves input CSV, PVMAP, and metadata files, then runs stat_var_processor as a
subprocess for each (dataset, pvmap) pair. Produces a CSV and markdown report.
"""

import csv
import glob
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ValidationResult:
    dataset: str
    pvmap_file: str
    status: str  # PASS, FAIL, SKIP
    data_rows: int = 0
    return_code: int = -1
    metadata_source: str = "none"
    error: str = ""


def load_datasets() -> List[str]:
    """Load dataset names from factor analysis CSV."""
    csv_path = PROJECT_ROOT / "analysis" / "factor_analysis" / "dataset_features_and_accuracy.csv"
    datasets = []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            datasets.append(row["dataset"])
    return datasets


def resolve_first_csv(pattern: str) -> Optional[Path]:
    """Return the first CSV matching a glob pattern, or None."""
    matches = sorted(glob.glob(pattern))
    for m in matches:
        if m.endswith(".csv"):
            return Path(m)
    return None


def resolve_files(dataset: str):
    """Resolve input CSV, PVMAP list, and metadata for a dataset.

    Returns (input_csv, pvmap_list, metadata_csv, metadata_source).
    """
    input_csv = resolve_first_csv(
        str(PROJECT_ROOT / "input" / dataset / "test_data" / "*_input.csv")
    )

    pvmap_dir = PROJECT_ROOT / "ground_truth" / dataset / "pvmap"
    pvmap_list = sorted(pvmap_dir.glob("*.csv")) if pvmap_dir.is_dir() else []

    # Metadata: try ground_truth first, then input fallback
    metadata_csv = resolve_first_csv(
        str(PROJECT_ROOT / "ground_truth" / dataset / "metadata" / "*.csv")
    )
    metadata_source = "ground_truth"

    if metadata_csv is None:
        metadata_csv = resolve_first_csv(
            str(PROJECT_ROOT / "input" / dataset / "input_metadata" / "*.csv")
        )
        metadata_source = "input_fallback" if metadata_csv else "none"

    return input_csv, pvmap_list, metadata_csv, metadata_source


def count_data_rows(output_file: Path) -> int:
    """Count non-empty lines after the header in a CSV."""
    if not output_file.exists():
        return 0
    with open(output_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    data_lines = [l for l in lines if l.strip()]
    return max(0, len(data_lines) - 1)  # subtract header


def run_validation(
    dataset: str,
    input_csv: Path,
    pvmap_csv: Path,
    metadata_csv: Optional[Path],
    metadata_source: str,
) -> ValidationResult:
    """Run stat_var_processor for one (dataset, pvmap) pair."""
    pvmap_stem = pvmap_csv.stem
    output_dir = PROJECT_ROOT / "output" / "ground_truth_validation" / dataset / pvmap_stem
    output_dir.mkdir(parents=True, exist_ok=True)

    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python3"
    python_cmd = str(venv_python) if venv_python.exists() else sys.executable

    cmd = [
        python_cmd,
        str(PROJECT_ROOT / "src" / "pipeline" / "validation" / "stat_var_processor.py"),
        f"--input_data={input_csv}",
        f"--pv_map={pvmap_csv}",
        "--generate_statvar_name=True",
        f"--output_path={output_dir}/processed",
    ]
    if metadata_csv:
        cmd.append(f"--config_file={metadata_csv}")

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_ROOT}:{PROJECT_ROOT}/src"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            cwd=str(PROJECT_ROOT),
        )
        rc = result.returncode
    except subprocess.TimeoutExpired:
        return ValidationResult(
            dataset=dataset,
            pvmap_file=pvmap_csv.name,
            status="FAIL",
            return_code=-1,
            metadata_source=metadata_source,
            error="timeout after 300s",
        )
    except Exception as e:
        return ValidationResult(
            dataset=dataset,
            pvmap_file=pvmap_csv.name,
            status="FAIL",
            return_code=-1,
            metadata_source=metadata_source,
            error=str(e)[:200],
        )

    processed_file = output_dir / "processed.csv"
    data_rows = count_data_rows(processed_file)

    if rc == 0 and processed_file.exists() and data_rows >= 1:
        return ValidationResult(
            dataset=dataset,
            pvmap_file=pvmap_csv.name,
            status="PASS",
            data_rows=data_rows,
            return_code=rc,
            metadata_source=metadata_source,
        )
    else:
        # Extract short error from stderr
        stderr_lines = (result.stderr or "").strip().splitlines()
        error_msg = stderr_lines[-1][:200] if stderr_lines else "no output file or empty"
        if rc != 0 and not error_msg:
            error_msg = f"exit code {rc}"
        if rc == 0 and not processed_file.exists():
            error_msg = "processed.csv not created"
        elif rc == 0 and data_rows == 0:
            error_msg = "processed.csv has 0 data rows"

        return ValidationResult(
            dataset=dataset,
            pvmap_file=pvmap_csv.name,
            status="FAIL",
            data_rows=data_rows,
            return_code=rc,
            metadata_source=metadata_source,
            error=error_msg,
        )


def write_csv(results: List[ValidationResult], output_path: Path):
    """Write results to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["dataset", "pvmap_file", "status", "data_rows", "return_code", "metadata_source", "error"]
        )
        for r in results:
            writer.writerow(
                [r.dataset, r.pvmap_file, r.status, r.data_rows, r.return_code, r.metadata_source, r.error]
            )


def write_markdown(results: List[ValidationResult], output_path: Path):
    """Write markdown report."""
    total = len(results)
    passed = [r for r in results if r.status == "PASS"]
    failed = [r for r in results if r.status == "FAIL"]
    skipped = [r for r in results if r.status == "SKIP"]

    datasets_seen = set(r.dataset for r in results)
    num_datasets = len(datasets_seen)

    lines = []
    lines.append("# Ground Truth Validation Report\n")
    lines.append(
        f"{len(passed)} of {total} PVMAP files pass validation across {num_datasets} datasets.\n"
    )

    # Summary counts
    lines.append(f"- PASS: {len(passed)}")
    lines.append(f"- FAIL: {len(failed)}")
    lines.append(f"- SKIP: {len(skipped)}")
    lines.append("")

    # Full results table
    lines.append("## Results\n")
    lines.append("| Dataset | PVMAP File | Status | Data Rows | Return Code | Metadata Source | Error |")
    lines.append("|---------|-----------|--------|-----------|-------------|-----------------|-------|")
    for r in results:
        error_cell = r.error.replace("|", "/") if r.error else ""
        lines.append(
            f"| {r.dataset} | {r.pvmap_file} | {r.status} | {r.data_rows} | {r.return_code} | {r.metadata_source} | {error_cell} |"
        )
    lines.append("")

    # Failures
    if failed:
        lines.append("## Failures\n")
        for r in failed:
            lines.append(f"- **{r.dataset}** / `{r.pvmap_file}`: {r.error}")
        lines.append("")

    # Metadata fallbacks
    fallbacks = [r for r in results if r.metadata_source == "input_fallback"]
    if fallbacks:
        lines.append("## Metadata Fallbacks\n")
        lines.append("These datasets used `input/*/input_metadata/` instead of `ground_truth/*/metadata/`:\n")
        for r in fallbacks:
            lines.append(f"- {r.dataset}")
        lines.append("")

    # Skipped
    if skipped:
        lines.append("## Skipped\n")
        for r in skipped:
            lines.append(f"- **{r.dataset}**: {r.error}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))


def main():
    datasets = load_datasets()
    print(f"Loaded {len(datasets)} datasets from factor analysis CSV.\n")

    results: List[ValidationResult] = []

    for i, dataset in enumerate(datasets, 1):
        input_csv, pvmap_list, metadata_csv, metadata_source = resolve_files(dataset)

        # Skip if no input CSV
        if input_csv is None:
            print(f"[{i}/{len(datasets)}] {dataset}: SKIP (no input CSV)")
            results.append(
                ValidationResult(
                    dataset=dataset,
                    pvmap_file="",
                    status="SKIP",
                    metadata_source=metadata_source,
                    error="no input CSV found",
                )
            )
            continue

        # Skip if no PVMAPs
        if not pvmap_list:
            print(f"[{i}/{len(datasets)}] {dataset}: SKIP (no ground truth PVMAPs)")
            results.append(
                ValidationResult(
                    dataset=dataset,
                    pvmap_file="",
                    status="SKIP",
                    metadata_source=metadata_source,
                    error="no ground truth PVMAP files found",
                )
            )
            continue

        # Skip if no metadata
        if metadata_csv is None:
            print(f"[{i}/{len(datasets)}] {dataset}: SKIP (no metadata)")
            results.append(
                ValidationResult(
                    dataset=dataset,
                    pvmap_file="",
                    status="SKIP",
                    metadata_source="none",
                    error="no metadata found",
                )
            )
            continue

        for j, pvmap in enumerate(pvmap_list, 1):
            tag = f"[{i}/{len(datasets)}] {dataset} pvmap {j}/{len(pvmap_list)}"
            print(f"{tag}: running {pvmap.name} ...", end=" ", flush=True)
            r = run_validation(dataset, input_csv, pvmap, metadata_csv, metadata_source)
            results.append(r)
            if r.status == "PASS":
                print(f"PASS ({r.data_rows} rows)")
            else:
                print(f"{r.status}: {r.error[:80]}")

    # Write outputs
    csv_path = PROJECT_ROOT / "analysis" / "factor_analysis" / "ground_truth_validation.csv"
    md_path = PROJECT_ROOT / "analysis" / "ground_truth_validation_report.md"

    write_csv(results, csv_path)
    write_markdown(results, md_path)

    # Print summary
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    skipped = sum(1 for r in results if r.status == "SKIP")
    print(f"\nDone. {passed} PASS, {failed} FAIL, {skipped} SKIP out of {len(results)} total.")
    print(f"CSV:      {csv_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate ground truth PVMAPs using files from the upstream datacommonsorg/data repo.

Instead of using local consolidated input files (which may not match the PVMAPs),
this script uses the original files from the upstream repo where input CSVs, PVMAPs,
and metadata live in the same directory and are known to be compatible.

Upstream repo: /Users/nehilsood/work/datacommonsorg-data/statvar_imports/
"""

import csv
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_BASE = Path("/Users/nehilsood/work/datacommonsorg-data/statvar_imports")


@dataclass
class ValidationResult:
    dataset: str
    pvmap_file: str
    status: str  # PASS, FAIL, SKIP
    data_rows: int = 0
    return_code: int = -1
    metadata_source: str = "none"
    upstream_dir: str = ""
    input_file: str = ""
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


def get_upstream_top_dirs() -> List[str]:
    """List all top-level directories under UPSTREAM_BASE."""
    dirs = []
    for entry in sorted(UPSTREAM_BASE.iterdir()):
        if entry.is_dir() and not entry.name.startswith("."):
            dirs.append(entry.name)
    return dirs


def map_dataset_to_upstream(dataset: str, top_dirs: List[str]) -> Optional[Path]:
    """Map a dataset name to its upstream directory path.

    Strategy: find the longest top-level dir prefix that matches the dataset name,
    then try various ways to resolve the remainder as a subdirectory path.
    """
    # Sort top dirs by length descending to find longest match first
    sorted_dirs = sorted(top_dirs, key=len, reverse=True)

    for top_dir in sorted_dirs:
        if dataset == top_dir:
            return UPSTREAM_BASE / top_dir
        if not dataset.startswith(top_dir + "_"):
            continue

        remainder = dataset[len(top_dir) + 1:]
        top_path = UPSTREAM_BASE / top_dir

        # Try 1: remainder as direct subdir name
        candidate = top_path / remainder
        if candidate.is_dir():
            return candidate

        # Try 2: split remainder on underscores, try progressive subdir combinations
        parts = remainder.split("_")
        for i in range(1, len(parts)):
            subdir = "_".join(parts[:i])
            rest = "_".join(parts[i:])
            # Try subdir/rest as nested path
            candidate = top_path / subdir / rest
            if candidate.is_dir():
                return candidate
            # Try subdir alone (rest might not be a subdir)
            if (top_path / subdir).is_dir():
                sub_candidate = top_path / subdir / rest
                if sub_candidate.is_dir():
                    return sub_candidate

        # Try 3: scan actual subdirs for one that contains the remainder
        # This handles cases like ncses_median_annual_salary -> ncses/ncses_median_annual_salary
        # where the subdir name includes the parent prefix
        if top_path.is_dir():
            for child in sorted(top_path.iterdir()):
                if child.is_dir() and child.name.endswith(remainder):
                    return child
            # Also try: the subdir might be top_dir + "_" + remainder
            candidate = top_path / (top_dir + "_" + remainder)
            if candidate.is_dir():
                return candidate

    return None


def find_input_files(upstream_dir: Path) -> List[Path]:
    """Find input CSV files in test_data/ or testdata/ subdirectory.

    Handles several upstream conventions:
    - test_data/*_input.csv or test_data/*_data.csv
    - testdata/*_input.csv (some datasets use this variant)
    - test_data/sample_input/*.csv (usa_dol pattern)
    """
    inputs = []
    for td_name in ["test_data", "testdata"]:
        td = upstream_dir / td_name
        if not td.is_dir():
            continue
        for f in sorted(td.iterdir()):
            if f.is_file() and f.suffix == ".csv":
                name = f.name.lower()
                if "_output" in name:
                    continue
                if "_input" in name or "_data" in name:
                    inputs.append(f)
        # Also check for subdirs like sample_input/
        for subdir in sorted(td.iterdir()):
            if subdir.is_dir() and "input" in subdir.name.lower():
                for f in sorted(subdir.iterdir()):
                    if f.is_file() and f.suffix == ".csv":
                        inputs.append(f)
    return inputs


def find_pvmap_files(upstream_dir: Path) -> List[Path]:
    """Find PVMAP CSV files in the upstream directory.

    Checks the directory itself and common subdirectories like pv_map/ and config_files/.
    """
    pvmaps = []

    # Check main directory
    for f in sorted(upstream_dir.iterdir()):
        if f.is_file() and f.suffix == ".csv":
            name = f.name.lower()
            if "pvmap" in name or "pv_map" in name:
                pvmaps.append(f)

    # Check common subdirectories for pvmaps
    for subdir_name in ["pv_map", "config_files"]:
        subdir = upstream_dir / subdir_name
        if subdir.is_dir():
            for f in sorted(subdir.iterdir()):
                if f.is_file() and f.suffix == ".csv":
                    name = f.name.lower()
                    if "pvmap" in name or "pv_map" in name:
                        pvmaps.append(f)

    return pvmaps


def find_metadata_files(upstream_dir: Path) -> List[Path]:
    """Find metadata CSV files in the upstream directory and common subdirectories."""
    metas = []
    # Check main directory
    for f in sorted(upstream_dir.iterdir()):
        if f.is_file() and f.suffix == ".csv":
            name = f.name.lower()
            if "metadata" in name:
                metas.append(f)
    # Check config_files/ subdir (brazil_sidra_ibge pattern)
    for subdir_name in ["config_files"]:
        subdir = upstream_dir / subdir_name
        if subdir.is_dir():
            for f in sorted(subdir.iterdir()):
                if f.is_file() and f.suffix == ".csv":
                    name = f.name.lower()
                    if "metadata" in name:
                        metas.append(f)
    return metas


def get_prefix(filename: str) -> str:
    """Extract the prefix from a filename by stripping known suffixes."""
    name = Path(filename).stem.lower()
    for suffix in ["_pvmap", "_pv_map", "_input", "_data", "_metadata"]:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def match_pvmap_to_input(
    pvmap: Path, input_files: List[Path]
) -> Optional[Path]:
    """Match a PVMAP to its corresponding input file by shared prefix."""
    if not input_files:
        return None
    if len(input_files) == 1:
        return input_files[0]

    pvmap_prefix = get_prefix(pvmap.name)

    # Try exact prefix match
    for inp in input_files:
        inp_prefix = get_prefix(inp.name)
        if pvmap_prefix == inp_prefix:
            return inp

    # Try substring match (pvmap prefix contains input prefix or vice versa)
    for inp in input_files:
        inp_prefix = get_prefix(inp.name)
        if pvmap_prefix in inp_prefix or inp_prefix in pvmap_prefix:
            return inp

    # Fallback: use first input file
    return input_files[0]


def match_pvmap_to_metadata(
    pvmap: Path, metadata_files: List[Path]
) -> Optional[Path]:
    """Match a PVMAP to its corresponding metadata file by shared prefix."""
    if not metadata_files:
        return None
    if len(metadata_files) == 1:
        return metadata_files[0]

    pvmap_prefix = get_prefix(pvmap.name)

    # Try exact prefix match
    for meta in metadata_files:
        meta_prefix = get_prefix(meta.name)
        if pvmap_prefix == meta_prefix:
            return meta

    # Try substring match
    for meta in metadata_files:
        meta_prefix = get_prefix(meta.name)
        if pvmap_prefix in meta_prefix or meta_prefix in pvmap_prefix:
            return meta

    # Fallback: use first metadata file
    return metadata_files[0]


def count_data_rows(output_file: Path) -> int:
    """Count non-empty lines after the header in a CSV."""
    if not output_file.exists():
        return 0
    with open(output_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    data_lines = [l for l in lines if l.strip()]
    return max(0, len(data_lines) - 1)


def run_validation(
    dataset: str,
    input_csv: Path,
    pvmap_csv: Path,
    metadata_csv: Optional[Path],
    upstream_dir: Path,
) -> ValidationResult:
    """Run stat_var_processor for one (dataset, pvmap) pair."""
    pvmap_stem = pvmap_csv.stem
    output_dir = (
        PROJECT_ROOT / "output" / "ground_truth_validation_upstream" / dataset / pvmap_stem
    )
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

    meta_source = "upstream" if metadata_csv else "none"

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
            metadata_source=meta_source,
            upstream_dir=str(upstream_dir.relative_to(UPSTREAM_BASE)),
            input_file=input_csv.name,
            error="timeout after 300s",
        )
    except Exception as e:
        return ValidationResult(
            dataset=dataset,
            pvmap_file=pvmap_csv.name,
            status="FAIL",
            return_code=-1,
            metadata_source=meta_source,
            upstream_dir=str(upstream_dir.relative_to(UPSTREAM_BASE)),
            input_file=input_csv.name,
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
            metadata_source=meta_source,
            upstream_dir=str(upstream_dir.relative_to(UPSTREAM_BASE)),
            input_file=input_csv.name,
        )
    else:
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
            metadata_source=meta_source,
            upstream_dir=str(upstream_dir.relative_to(UPSTREAM_BASE)),
            input_file=input_csv.name,
            error=error_msg,
        )


def write_csv(results: List[ValidationResult], output_path: Path):
    """Write results to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "dataset",
                "pvmap_file",
                "status",
                "data_rows",
                "return_code",
                "metadata_source",
                "upstream_dir",
                "input_file",
                "error",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    r.dataset,
                    r.pvmap_file,
                    r.status,
                    r.data_rows,
                    r.return_code,
                    r.metadata_source,
                    r.upstream_dir,
                    r.input_file,
                    r.error,
                ]
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
    lines.append("# Ground Truth Validation Report (Upstream Files)\n")
    lines.append(
        f"{len(passed)} of {total} PVMAP files pass validation across {num_datasets} datasets.\n"
    )
    lines.append(
        "Uses files from `datacommonsorg/data` repo instead of local consolidated inputs.\n"
    )

    lines.append(f"- PASS: {len(passed)}")
    lines.append(f"- FAIL: {len(failed)}")
    lines.append(f"- SKIP: {len(skipped)}")
    lines.append("")

    # Results table
    lines.append("## Results\n")
    lines.append(
        "| Dataset | PVMAP File | Input File | Status | Data Rows | Upstream Dir | Error |"
    )
    lines.append(
        "|---------|-----------|------------|--------|-----------|--------------|-------|"
    )
    for r in results:
        error_cell = r.error.replace("|", "/") if r.error else ""
        lines.append(
            f"| {r.dataset} | {r.pvmap_file} | {r.input_file} | {r.status} "
            f"| {r.data_rows} | {r.upstream_dir} | {error_cell} |"
        )
    lines.append("")

    # Failures
    if failed:
        lines.append("## Failures\n")
        for r in failed:
            lines.append(f"- **{r.dataset}** / `{r.pvmap_file}`: {r.error}")
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

    top_dirs = get_upstream_top_dirs()
    print(f"Found {len(top_dirs)} top-level dirs in upstream repo.\n")

    results: List[ValidationResult] = []
    mapping_issues = []

    for i, dataset in enumerate(datasets, 1):
        upstream_dir = map_dataset_to_upstream(dataset, top_dirs)

        if upstream_dir is None or not upstream_dir.is_dir():
            print(f"[{i}/{len(datasets)}] {dataset}: SKIP (no upstream dir found)")
            results.append(
                ValidationResult(
                    dataset=dataset,
                    pvmap_file="",
                    status="SKIP",
                    error=f"no upstream directory found for '{dataset}'",
                )
            )
            mapping_issues.append(dataset)
            continue

        rel_dir = str(upstream_dir.relative_to(UPSTREAM_BASE))

        # Find files
        pvmap_files = find_pvmap_files(upstream_dir)
        input_files = find_input_files(upstream_dir)
        metadata_files = find_metadata_files(upstream_dir)

        if not pvmap_files:
            print(f"[{i}/{len(datasets)}] {dataset}: SKIP (no PVMAPs in {rel_dir})")
            results.append(
                ValidationResult(
                    dataset=dataset,
                    pvmap_file="",
                    status="SKIP",
                    upstream_dir=rel_dir,
                    error=f"no PVMAP files found in {rel_dir}",
                )
            )
            continue

        if not input_files:
            print(f"[{i}/{len(datasets)}] {dataset}: SKIP (no input CSVs in {rel_dir})")
            results.append(
                ValidationResult(
                    dataset=dataset,
                    pvmap_file="",
                    status="SKIP",
                    upstream_dir=rel_dir,
                    error=f"no input CSV files found in {rel_dir}/test_data/",
                )
            )
            continue

        for j, pvmap in enumerate(pvmap_files, 1):
            input_csv = match_pvmap_to_input(pvmap, input_files)
            metadata_csv = match_pvmap_to_metadata(pvmap, metadata_files)

            tag = f"[{i}/{len(datasets)}] {dataset} pvmap {j}/{len(pvmap_files)}"
            print(
                f"{tag}: {pvmap.name} + {input_csv.name} ...",
                end=" ",
                flush=True,
            )

            r = run_validation(dataset, input_csv, pvmap, metadata_csv, upstream_dir)
            results.append(r)
            if r.status == "PASS":
                print(f"PASS ({r.data_rows} rows)")
            else:
                print(f"{r.status}: {r.error[:80]}")

    # Write outputs
    csv_path = (
        PROJECT_ROOT / "analysis" / "factor_analysis" / "ground_truth_validation_upstream.csv"
    )
    md_path = PROJECT_ROOT / "analysis" / "ground_truth_validation_upstream_report.md"

    write_csv(results, csv_path)
    write_markdown(results, md_path)

    # Print summary
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    skipped = sum(1 for r in results if r.status == "SKIP")
    print(f"\nDone. {passed} PASS, {failed} FAIL, {skipped} SKIP out of {len(results)} total.")
    print(f"CSV:      {csv_path}")
    print(f"Markdown: {md_path}")

    if mapping_issues:
        print(f"\nMapping issues ({len(mapping_issues)} datasets could not be mapped):")
        for d in mapping_issues:
            print(f"  - {d}")


if __name__ == "__main__":
    main()

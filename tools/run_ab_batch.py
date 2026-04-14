"""Batch pipeline runner for A/B comparison."""
import csv
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
RESULTS_FILE = PROJECT_ROOT / "output" / "ab_batch_results.json"


def find_datasets():
    datasets = []
    for test_data in sorted(Path(PROJECT_ROOT / "input").glob("*/test_data")):
        csvs = list(test_data.glob("*_input.csv"))
        if csvs:
            ds = test_data.parent.name
            rows = sum(1 for _ in open(csvs[0], "r", errors="replace"))
            datasets.append((ds, rows))
    datasets.sort(key=lambda x: x[1])
    return datasets


def run_dataset(ds_name, timeout=600):
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_ROOT}:{PROJECT_ROOT / 'src'}"

    cmd = [
        str(PROJECT_ROOT / ".venv" / "bin" / "python"),
        str(PROJECT_ROOT / "src" / "run_pipeline.py"),
        f"--dataset={ds_name}",
    ]

    start = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=str(PROJECT_ROOT), env=env,
        )
        elapsed = time.time() - start
        output = result.stdout + result.stderr

        # Parse results from output
        gen_success = "Generation success: True" in output
        val_passed = "Validation passed: True" in output

        node_acc = 0.0
        m = re.search(r"Node accuracy: ([\d.]+)%", output)
        if m:
            node_acc = float(m.group(1))

        pv_acc = 0.0
        m = re.search(r"PV accuracy: ([\d.]+)%", output)
        if m:
            pv_acc = float(m.group(1))

        return {
            "dataset": ds_name,
            "generation_success": gen_success,
            "validation_passed": val_passed,
            "node_accuracy": node_acc,
            "pv_accuracy": pv_acc,
            "elapsed_s": round(elapsed, 1),
            "returncode": result.returncode,
            "error": None,
        }
    except subprocess.TimeoutExpired:
        return {
            "dataset": ds_name,
            "generation_success": False,
            "validation_passed": False,
            "node_accuracy": 0.0,
            "pv_accuracy": 0.0,
            "elapsed_s": timeout,
            "returncode": -1,
            "error": "TIMEOUT",
        }
    except Exception as e:
        return {
            "dataset": ds_name,
            "generation_success": False,
            "validation_passed": False,
            "node_accuracy": 0.0,
            "pv_accuracy": 0.0,
            "elapsed_s": time.time() - start,
            "returncode": -1,
            "error": str(e),
        }


def main():
    datasets = find_datasets()
    print(f"Running {len(datasets)} datasets...")
    print()

    results = []
    passed = 0
    total = len(datasets)

    for i, (ds, rows) in enumerate(datasets, 1):
        print(f"[{i}/{total}] {ds} ({rows} rows)...", end=" ", flush=True)
        r = run_dataset(ds)
        results.append(r)

        status = "PASS" if r["validation_passed"] else "FAIL"
        if r["validation_passed"]:
            passed += 1
        print(f"{status} (PV:{r['pv_accuracy']:.1f}%, {r['elapsed_s']:.0f}s)")

        # Save incrementally
        RESULTS_FILE.write_text(json.dumps(results, indent=2))

    print()
    print(f"{'=' * 60}")
    print(f"TOTAL: {passed}/{total} passed ({passed/total*100:.1f}%)")
    print(f"Results saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()

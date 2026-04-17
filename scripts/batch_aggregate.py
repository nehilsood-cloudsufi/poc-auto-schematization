#!/usr/bin/env python3
"""Batch aggregator: reads per-dataset artifacts and writes the final report."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from scripts.batch_lib.aggregator_core import build_dataset_record
from scripts.batch_lib.pricing import PricingTable
from scripts.batch_lib.report_markdown import render_report
from scripts.batch_lib.scatter import write_scatter

logger = logging.getLogger("batch_aggregate")


def parse_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--pricing-file", required=True)
    p.add_argument("--baseline-doc", default=None,
                   help="Path to Gemini_vs_Claude_Comparison.md for delta vs. Gemini 3 Pro")
    return p.parse_args(argv)


_PV_HEADER = "## PV Accuracy Comparison"
_NODE_HEADER = "## Node Accuracy Comparison"


def _parse_baseline(doc_path: Optional[Path]) -> Dict[str, Dict[str, float]]:
    """Returns {dataset: {'pv': float, 'node': float}} using the Gemini 3 Pro columns."""
    out: Dict[str, Dict[str, float]] = {}
    if not doc_path or not doc_path.exists():
        return out
    text = doc_path.read_text(encoding="utf-8", errors="replace")

    def _section(start_header: str) -> List[str]:
        i = text.find(start_header)
        if i < 0:
            return []
        # Section ends at the next top-level heading ("## ") or EOF. Don't
        # use "---" because the markdown table delimiter ("|---|") appears
        # inside the section just below the header row.
        j = text.find("\n## ", i + len(start_header))
        return text[i:(j if j > 0 else None)].splitlines()

    # Rows look like: | dataset | gb | claude | g3pro |
    row_re = re.compile(r"\|\s*([^\|]+?)\s*\|.*?\|.*?\|\s*([0-9.]+|\*\*[0-9.]+\*\*)\s*\|\s*$")

    def _parse_section(section_lines: List[str], key: str):
        for line in section_lines:
            m = row_re.search(line)
            if not m:
                continue
            ds = m.group(1)
            if ds.lower().startswith("dataset") or set(ds) <= set("-"):
                continue
            val_s = m.group(2).replace("**", "")
            try:
                val = float(val_s)
            except ValueError:
                continue
            out.setdefault(ds, {})[key] = val

    _parse_section(_section(_PV_HEADER), "pv")
    _parse_section(_section(_NODE_HEADER), "node")
    return out


def _write_summary_csv(records: List[dict], out: Path) -> None:
    if not records:
        out.write_text("")
        return
    agent_set = set()
    for r in records:
        agent_set.update(r["tokens_by_agent"].keys())
    agents = sorted(agent_set)

    fields = [
        "dataset", "status",
        "raw_rows", "cleaned_rows", "observation_rows", "columns", "file_size_mb", "skeleton_bytes",
        "pv_accuracy", "node_accuracy", "node_coverage",
        "delta_pv_vs_doc", "delta_node_vs_doc",
        "tokens_total", "cost_usd_total", "duration_total_s",
        "attempt_count", "schema_category", "sampling_strategy",
        "output_statvar_count", "git_sha",
    ]
    for a in agents:
        fields += [f"{a}_calls", f"{a}_tokens", f"{a}_cost_usd", f"{a}_model"]

    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in records:
            row = {
                "dataset": r["dataset"], "status": r["status"],
                "raw_rows": r["complexity"].get("raw_rows"),
                "cleaned_rows": r["complexity"].get("cleaned_rows"),
                "observation_rows": r["complexity"].get("observation_rows"),
                "columns": r["complexity"].get("columns"),
                "file_size_mb": r["complexity"].get("file_size_mb"),
                "skeleton_bytes": r["complexity"].get("skeleton_bytes"),
                "pv_accuracy": r["accuracy"].get("pv_accuracy"),
                "node_accuracy": r["accuracy"].get("node_accuracy"),
                "node_coverage": r["accuracy"].get("node_coverage"),
                "delta_pv_vs_doc": r["accuracy"].get("delta_pv_vs_doc_gemini3pro"),
                "delta_node_vs_doc": r["accuracy"].get("delta_node_vs_doc_gemini3pro"),
                "tokens_total": r["tokens_total"]["total"],
                "cost_usd_total": r["cost_usd"]["total"],
                "duration_total_s": r["timing_seconds"].get("total"),
                "attempt_count": r["run_meta"].get("attempt_count"),
                "schema_category": r["run_meta"].get("schema_category"),
                "sampling_strategy": r["run_meta"].get("sampling_strategy"),
                "output_statvar_count": r["run_meta"].get("output_statvar_count"),
                "git_sha": r["run_meta"].get("git_sha"),
            }
            for a in agents:
                b = r["tokens_by_agent"].get(a, {})
                row[f"{a}_calls"] = b.get("calls")
                row[f"{a}_tokens"] = b.get("total")
                row[f"{a}_cost_usd"] = b.get("cost_usd")
                row[f"{a}_model"] = b.get("model")
            w.writerow(row)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    runs_dir = Path(args.runs_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pricing = PricingTable.load(Path(args.pricing_file))
    baseline = _parse_baseline(Path(args.baseline_doc)) if args.baseline_doc else {}

    records: List[dict] = []
    failed: List[dict] = []
    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        dataset = run_dir.name
        input_csv = None
        base = Path("input") / dataset / "test_data"
        if base.exists():
            cands = list(base.glob("*_input.csv"))
            if cands:
                input_csv = cands[0]
        b = baseline.get(dataset, {})
        if (run_dir / "pipeline.log").exists():
            status = "passed"
        else:
            status = "crashed"
        rec = build_dataset_record(
            dataset=dataset, run_dir=run_dir, input_csv=input_csv,
            pricing=pricing, baseline_pv=b.get("pv"), baseline_node=b.get("node"),
            status=status,
        )
        records.append(rec)
        if rec["status"] not in ("passed", "passed_with_warnings"):
            failed.append({"dataset": dataset, "status": rec["status"]})

    (out_dir / "batch_results.json").write_text(json.dumps(records, indent=2))
    _write_summary_csv(records, out_dir / "batch_summary.csv")
    md = render_report(
        records=records,
        pricing_raw=pricing.raw,
        run_meta={
            "generated_at": datetime.now().isoformat(),
            "git_sha": next((r["run_meta"]["git_sha"] for r in records if r["run_meta"].get("git_sha")), "unknown"),
            "cli_args": "",
        },
    )
    (out_dir / "report.md").write_text(md)

    write_scatter(
        records, out_dir / "scatter_tokens_vs_rows.png",
        x_key=("complexity", "raw_rows"), y_key=("tokens_total", "total"),
        title="Input rows vs Total tokens", log_scale=True,
    )
    write_scatter(
        records, out_dir / "scatter_duration_vs_rows.png",
        x_key=("complexity", "raw_rows"), y_key=("timing_seconds", "total"),
        title="Input rows vs Total duration (s)", log_scale=True,
    )

    (out_dir / "failed.json").write_text(json.dumps(failed, indent=2))

    logger.info("aggregate: %d records; %d failed; outputs in %s",
                len(records), len(failed), out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Pre-compute all data for the manager_summary.docx builder.

Reads the same sources as scripts/manager_summary.py (batch_results.json +
per-dataset llm_calls.jsonl) and emits a flat docx_data.json that the
docx.js Node.js script can consume without reimplementing pricing logic.
"""
from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import sys
sys.path.insert(0, ".")
from scripts.manager_summary import compute_dataset_cost

BASE = Path("output/batch_runs/2026-04-17_comparison")
RUNS = BASE / "runs"
OUT = BASE / "docx_data.json"


def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = math.sqrt(
        sum((xs[i] - mx) ** 2 for i in range(n))
        * sum((ys[i] - my) ** 2 for i in range(n))
    )
    return num / den if den else 0.0


def main() -> int:
    results = json.loads((BASE / "batch_results.json").read_text())
    rows = []
    for r in results:
        ds = r["dataset"]
        calls_file = RUNS / ds / "llm_calls.jsonl"
        num_calls = 0
        if calls_file.exists():
            num_calls = sum(1 for l in calls_file.read_text().splitlines() if l.strip())
        rows.append({
            "dataset": ds,
            "rows": r["complexity"].get("raw_rows"),
            "cols": r["complexity"].get("columns"),
            "tokens": r["tokens_total"]["total"],
            "cost": compute_dataset_cost(RUNS / ds),
            "num_calls": num_calls,
        })
    rows.sort(key=lambda r: -r["tokens"])  # descending by tokens

    total_tokens = sum(r["tokens"] for r in rows)
    total_cost = sum(r["cost"] for r in rows)
    n = len(rows)
    min_r = min(rows, key=lambda r: r["tokens"])
    max_r = max(rows, key=lambda r: r["tokens"])

    eligible = [r for r in rows if r["rows"] and r["rows"] > 0 and r["cols"]]
    r_rows  = pearson([r["rows"]      for r in eligible], [r["cost"] for r in eligible])
    r_cols  = pearson([r["cols"]      for r in eligible], [r["cost"] for r in eligible])
    r_calls = pearson([r["num_calls"] for r in eligible], [r["cost"] for r in eligible])

    # Row and column cost buckets
    def row_bucket(rc):
        if rc <= 10:   return "1–10"
        if rc <= 100:  return "11–100"
        if rc <= 1000: return "101–1,000"
        return "1,000–10,000"
    rb = defaultdict(list)
    cb = defaultdict(list)
    for r in eligible:
        rb[row_bucket(r["rows"])].append(r["cost"])
        c = r["cols"]
        if   c <=  5: cb["1–5"].append(r["cost"])
        elif c <= 10: cb["6–10"].append(r["cost"])
        elif c <= 20: cb["11–20"].append(r["cost"])
        elif c <= 50: cb["21–50"].append(r["cost"])
        else:         cb[">50"].append(r["cost"])

    def bstats(name, d):
        out = []
        for label, costs in d.items():
            out.append({
                "label": label,
                "n": len(costs),
                "avg": round(statistics.mean(costs), 4),
                "median": round(statistics.median(costs), 4),
            })
        return out

    # Order bucket outputs consistently
    row_order = ["1–10", "11–100", "101–1,000", "1,000–10,000"]
    col_order = ["1–5", "6–10", "11–20", "21–50", ">50"]
    row_buckets = [b for lbl in row_order for b in bstats("row", {lbl: rb.get(lbl, [])}) if b["n"] > 0]
    col_buckets = [b for lbl in col_order for b in bstats("col", {lbl: cb.get(lbl, [])}) if b["n"] > 0]

    # Linear fit cost = a + b*cols
    xs = [r["cols"] for r in eligible]
    ys = [r["cost"] for r in eligible]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num_ = sum((xs[i] - mx) * (ys[i] - my) for i in range(len(xs)))
    den_ = sum((xs[i] - mx) ** 2 for i in range(len(xs)))
    slope = (num_ / den_) if den_ else 0.0
    intercept = my - slope * mx

    payload = {
        "header": {
            "title": "Batch Benchmark — Manager Summary",
            "run_date": "2026-04-17",
            "model": "gemini-3.1-pro-preview",
            "thinking_level": "high",
            "mcp_enabled": True,
            "num_datasets": n,
        },
        "summary": {
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 4),
            "avg_tokens": round(total_tokens / n, 0),
            "avg_cost_usd": round(total_cost / n, 4),
            "cheapest": {
                "dataset": min_r["dataset"],
                "tokens": min_r["tokens"],
                "cost": round(min_r["cost"], 4),
            },
            "priciest": {
                "dataset": max_r["dataset"],
                "tokens": max_r["tokens"],
                "cost": round(max_r["cost"], 4),
            },
        },
        "per_dataset": rows,
        "correlations": {
            "cols_vs_cost": round(r_cols, 4),
            "calls_vs_cost": round(r_calls, 4),
            "rows_vs_cost": round(r_rows, 4),
        },
        "col_buckets": col_buckets,
        "row_buckets": row_buckets,
        "formula": {
            "intercept": round(intercept, 4),
            "slope": round(slope, 6),
            "r_squared": round(r_cols ** 2, 4),
            "examples": [
                {"dataset": "zurich_bev_3240_wiki",
                 "cols": 3,
                 "predicted": round(intercept + slope * 3, 2),
                 "actual": 0.08},
                {"dataset": "us_crash_fars_crashdata",
                 "cols": 80,
                 "predicted": round(intercept + slope * 80, 2),
                 "actual": 0.81},
                {"dataset": "cdc_social_vulnerability_index",
                 "cols": 159,
                 "predicted": round(intercept + slope * 159, 2),
                 "actual": 1.55},
            ],
        },
        "pricing_source": "https://ai.google.dev/gemini-api/docs/pricing (fetched 2026-04-20)",
    }

    OUT.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {OUT}")
    print(f"  49 datasets · ${payload['summary']['total_cost_usd']:.2f} · "
          f"{payload['summary']['total_tokens']:,} tokens")
    return 0


if __name__ == "__main__":
    sys.exit(main())

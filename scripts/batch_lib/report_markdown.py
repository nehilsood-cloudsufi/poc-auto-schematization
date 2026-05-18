"""Markdown report builder for the batch benchmark."""
from __future__ import annotations

from typing import Any, Dict, List


def _fmt(x, width=1):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{width}f}"
    return str(x)


def render_report(
    records: List[Dict[str, Any]],
    pricing_raw: Dict[str, Any],
    run_meta: Dict[str, Any],
) -> str:
    lines: List[str] = []
    lines.append("# Batch Benchmark Report")
    lines.append("")
    lines.append(f"- Generated at: `{run_meta.get('generated_at', 'unknown')}`")
    lines.append(f"- Git SHA: `{run_meta.get('git_sha', 'unknown')}`")
    lines.append(f"- CLI args: `{run_meta.get('cli_args', '')}`")
    lines.append(f"- Pricing source: `{pricing_raw.get('_source', 'unknown')}`")
    lines.append("")

    if not records:
        lines.append("No datasets in report.")
        return "\n".join(lines)

    total_tokens = sum(r["tokens_total"]["total"] for r in records)
    total_cost = round(sum(r["cost_usd"]["total"] for r in records), 2)
    total_s = round(sum(r["timing_seconds"].get("total", 0.0) or 0.0 for r in records), 1)

    passed = [r for r in records if r["status"] in ("passed", "passed_with_warnings")]
    failed = [r for r in records if r["status"] not in ("passed", "passed_with_warnings")]

    pv_values = [r["accuracy"]["pv_accuracy"] for r in passed if r["accuracy"]["pv_accuracy"] is not None]
    node_values = [r["accuracy"]["node_accuracy"] for r in passed if r["accuracy"]["node_accuracy"] is not None]
    avg_pv = round(sum(pv_values) / len(pv_values), 2) if pv_values else 0.0
    avg_node = round(sum(node_values) / len(node_values), 2) if node_values else 0.0

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Datasets: **{len(records)}** (passed/warnings: {len(passed)}, failed: {len(failed)})")
    lines.append(f"- Average PV accuracy: **{avg_pv}%**")
    lines.append(f"- Average Node accuracy: **{avg_node}%**")
    lines.append(f"- Total tokens: **{total_tokens:,}**")
    lines.append(f"- Total cost: **${total_cost:,}** (pricing may include estimates)")
    lines.append(f"- Total wall time: **{total_s:,}s**")
    lines.append("")

    lines.append("## Per-Dataset")
    lines.append("")
    lines.append("| Dataset | Status | Raw rows | PV acc | Δ PV | Node acc | Δ Node | Tokens | Duration (s) | Attempts |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in records:
        a = r["accuracy"]
        c = r["complexity"]
        lines.append(
            f"| {r['dataset']} | {r['status']} | {_fmt(c.get('raw_rows'))} | "
            f"{_fmt(a.get('pv_accuracy'))} | {_fmt(a.get('delta_pv_vs_doc_gemini3pro'))} | "
            f"{_fmt(a.get('node_accuracy'))} | {_fmt(a.get('delta_node_vs_doc_gemini3pro'))} | "
            f"{r['tokens_total']['total']:,} | "
            f"{_fmt(r['timing_seconds'].get('total'))} | "
            f"{_fmt(r['run_meta'].get('attempt_count'))} |"
        )
    lines.append("")

    agent_agg: Dict[str, Dict[str, Any]] = {}
    for r in records:
        for agent, bucket in r["tokens_by_agent"].items():
            a = agent_agg.setdefault(agent, {"model": bucket["model"], "calls": 0, "total": 0, "cost": 0.0, "duration_ms": 0})
            a["calls"] += bucket["calls"]
            a["total"] += bucket["total"]
            a["cost"] += bucket["cost_usd"]
            a["duration_ms"] += bucket.get("duration_ms", 0)
            a["model"] = bucket["model"]

    lines.append("## Per-Agent Aggregate (all datasets)")
    lines.append("")
    lines.append("| Agent | Model | Calls | Tokens | Duration (s) | Cost $ |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for agent, a in sorted(agent_agg.items(), key=lambda kv: -kv[1]["total"]):
        lines.append(
            f"| {agent} | {a['model']} | {a['calls']} | {a['total']:,} | "
            f"{a['duration_ms']/1000:.1f} | ${a['cost']:.2f} |"
        )
    lines.append("")

    if failed:
        lines.append("## Failed Datasets")
        lines.append("")
        for r in failed:
            lines.append(f"- `{r['dataset']}` — {r['status']}")

    return "\n".join(lines)

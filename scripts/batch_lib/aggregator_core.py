"""Per-dataset record builder and cross-dataset rollup helpers.

Each dataset's record has the shape documented in the design spec
(docs/plans/2026-04-17-batch-benchmark-49-datasets-design.md §5.3).
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.batch_lib.pricing import PricingTable, compute_cost

logger = logging.getLogger(__name__)


def _read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("failed to read %s: %s", path, e)
        return None


def _read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    out: List[dict] = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("%s: corrupt line %d, skipping", path, i)
    return out


def compute_accuracy(
    pvs_matched: int, pvs_modified: int, pvs_deleted: int,
    nodes_matched: int, nodes_gt: int, nodes_generated: int,
) -> Dict[str, float]:
    pv_denom = pvs_matched + pvs_modified + pvs_deleted
    pv_acc = (pvs_matched / pv_denom * 100) if pv_denom else 0.0
    node_acc = (min(nodes_matched, nodes_gt) / nodes_gt * 100) if nodes_gt else 0.0
    node_cov = (nodes_generated / nodes_gt * 100) if nodes_gt else 0.0
    return {
        "pv_accuracy": round(pv_acc, 2),
        "node_accuracy": round(node_acc, 2),
        "node_coverage": round(node_cov, 2),
    }


def _complexity_from_input(input_csv: Optional[Path]) -> Dict[str, Any]:
    if input_csv is None or not Path(input_csv).exists():
        return {"raw_rows": None, "columns": None, "file_size_mb": None}
    p = Path(input_csv)
    try:
        size_mb = round(p.stat().st_size / (1024 * 1024), 3)
    except OSError:
        size_mb = None
    raw_rows = 0
    cols = None
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
                cols = len(header)
            except StopIteration:
                header = None
            for _ in reader:
                raw_rows += 1
    except OSError:
        raw_rows = None
    return {"raw_rows": raw_rows, "columns": cols, "file_size_mb": size_mb}


def _statvar_count_from_pvmap(pvmap_csv: Path) -> Optional[int]:
    if not pvmap_csv.exists():
        return None
    try:
        with open(pvmap_csv, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            count = 0
            for row in reader:
                if row and row[0].strip() and row[0].strip() != "Node":
                    count += 1
            return count
    except OSError:
        return None


def build_dataset_record(
    dataset: str,
    run_dir: Path,
    input_csv: Optional[Path],
    pricing: PricingTable,
    baseline_pv: Optional[float],
    baseline_node: Optional[float],
    status: str,
) -> Dict[str, Any]:
    run_dir = Path(run_dir)
    calls = _read_jsonl(run_dir / "llm_calls.jsonl")
    phase = _read_json(run_dir / "phase_timings.json") or {}
    manifest = _read_json(run_dir / "run_manifest.json") or {}
    diff = _read_json(run_dir / "eval_results" / "diff_results.json")

    # Tokens rollup
    tokens_total = {"prompt": 0, "thoughts": 0, "response": 0, "total": 0}
    tokens_by_agent: Dict[str, Dict[str, Any]] = {}
    for c in calls:
        agent = c.get("agent", "unknown")
        model = c.get("model", "unknown")
        pt = c.get("prompt_tokens") or 0
        tt = c.get("thoughts_tokens") or 0
        rt = c.get("response_tokens") or 0
        tot = c.get("total_tokens") or (pt + tt + rt)
        dur = c.get("duration_ms") or 0
        tokens_total["prompt"] += pt
        tokens_total["thoughts"] += tt
        tokens_total["response"] += rt
        tokens_total["total"] += tot
        bucket = tokens_by_agent.setdefault(agent, {
            "model": model, "calls": 0,
            "prompt": 0, "thoughts": 0, "response": 0, "total": 0,
            "duration_ms": 0, "cost_usd": 0.0,
        })
        bucket["calls"] += 1
        bucket["prompt"] += pt
        bucket["thoughts"] += tt
        bucket["response"] += rt
        bucket["total"] += tot
        bucket["duration_ms"] += dur
        cost = compute_cost(pt, rt, tt, model, pricing)
        bucket["cost_usd"] = round(bucket["cost_usd"] + cost["cost_usd"], 6)
        bucket["model"] = model  # last-write-wins if agent mixes models

    cost_total = round(sum(b["cost_usd"] for b in tokens_by_agent.values()), 6)

    # Accuracy
    if diff:
        pvs_matched = int(diff.get("PVs-matched", 0))
        pvs_modified = int(diff.get("pvs-modified", 0))
        pvs_deleted = int(diff.get("pvs-deleted", 0))
        nodes_matched = int(diff.get("nodes-matched", 0))
        nodes_gt = int(diff.get("nodes-ground-truth", 0))
        nodes_generated = int(diff.get("nodes-auto-generated", 0))
        acc = compute_accuracy(pvs_matched, pvs_modified, pvs_deleted,
                               nodes_matched, nodes_gt, nodes_generated)
        accuracy = {
            **acc,
            "pvs_matched": pvs_matched, "pvs_modified": pvs_modified, "pvs_deleted": pvs_deleted,
            "nodes_matched": nodes_matched, "nodes_gt": nodes_gt, "nodes_generated": nodes_generated,
            "delta_pv_vs_doc_gemini3pro": round(acc["pv_accuracy"] - baseline_pv, 2) if baseline_pv is not None else None,
            "delta_node_vs_doc_gemini3pro": round(acc["node_accuracy"] - baseline_node, 2) if baseline_node is not None else None,
        }
    else:
        accuracy = {
            "pv_accuracy": None, "node_accuracy": None, "node_coverage": None,
            "pvs_matched": None, "pvs_modified": None, "pvs_deleted": None,
            "nodes_matched": None, "nodes_gt": None, "nodes_generated": None,
            "delta_pv_vs_doc_gemini3pro": None, "delta_node_vs_doc_gemini3pro": None,
        }

    # Adjust status: PVMAP produced but eval missing -> passed_with_warnings
    effective_status = status
    if status == "passed" and diff is None and (run_dir / "generated_pvmap.csv").exists():
        effective_status = "passed_with_warnings"

    complexity = _complexity_from_input(input_csv)
    complexity["cleaned_rows"] = None
    complexity["observation_rows"] = None
    complexity["skeleton_bytes"] = None

    timing = {
        k: (v.get("duration_s") if isinstance(v, dict) else v)
        for k, v in phase.items()
    }

    return {
        "dataset": dataset,
        "status": effective_status,
        "complexity": complexity,
        "accuracy": accuracy,
        "tokens_total": tokens_total,
        "tokens_by_agent": tokens_by_agent,
        "cost_usd": {
            "total": cost_total,
            "by_agent": {k: v["cost_usd"] for k, v in tokens_by_agent.items()},
            "pricing_version": pricing.raw.get("_source", "unknown"),
        },
        "timing_seconds": timing,
        "run_meta": {
            "attempt_count": None,
            "best_attempt_used": None,
            "schema_category": None,
            "sampling_strategy": None,
            "output_statvar_count": _statvar_count_from_pvmap(run_dir / "generated_pvmap.csv"),
            "prompt_bytes_generator": next(
                (c.get("prompt_bytes") for c in calls if c.get("agent") in ("Generator", "PVMAPGenerator")),
                None,
            ),
            "worker_id": manifest.get("worker_id"),
            "mcp_port": manifest.get("mcp_port"),
            "git_sha": manifest.get("git_sha"),
            "started_at": manifest.get("started_at"),
            "ended_at": phase.get("total", {}).get("end") if isinstance(phase.get("total"), dict) else None,
        },
        "pipeline_log": str((run_dir / "pipeline.log")) if (run_dir / "pipeline.log").exists() else None,
        "generated_pvmap": str((run_dir / "generated_pvmap.csv")) if (run_dir / "generated_pvmap.csv").exists() else None,
    }

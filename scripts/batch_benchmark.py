#!/usr/bin/env python3
"""Batch benchmark orchestrator.

Runs src/run_pipeline.py as a subprocess for each dataset in the list, up to
`--concurrency` at a time, each with its own MCP_PORT. Appends results to
checkpoint.jsonl and writes failed.json at end.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shlex
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List

from scripts.batch_lib.checkpoint import Checkpoint

logger = logging.getLogger("batch_benchmark")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Batch benchmark orchestrator")
    p.add_argument("--datasets-file", required=True, help="Text file, one dataset name per line")
    p.add_argument("--output-dir", required=True, help="Batch root output dir")
    p.add_argument("--concurrency", type=int, default=3)
    p.add_argument("--timeout", type=int, default=2700, help="Per-dataset timeout (s)")
    p.add_argument("--mcp-port-base", type=int, default=3000)
    p.add_argument("--pipeline-args", default="", help="Extra args forwarded to src/run_pipeline.py")
    p.add_argument("--resume-failed", default=None, help="Path to a failed.json from a previous run")
    p.add_argument("--limit", type=int, default=None, help="Dry-run: only process first N datasets after filtering")
    return p


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) != 0


def _pick_port(base: int, slot: int, max_retries: int = 3) -> int:
    port = base + slot
    for _ in range(max_retries):
        if _port_free(port):
            return port
        port += 10
    return port  # last resort; pipeline may fail — we'll log


def _load_datasets(args) -> List[str]:
    if args.resume_failed:
        data = json.loads(Path(args.resume_failed).read_text())
        datasets = [r["dataset"] for r in data]
    else:
        datasets = [ln.strip() for ln in Path(args.datasets_file).read_text().splitlines() if ln.strip()]
    if args.limit:
        datasets = datasets[:args.limit]
    return datasets


def run_one(dataset: str, slot: int, port: int, output_dir: Path, pipeline_args: str, timeout: int) -> dict:
    ds_out = output_dir / "runs" / dataset
    ds_out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "MCP_PORT": str(port), "BATCH_WORKER_ID": str(slot),
           "PYTHONPATH": f"{os.environ.get('PYTHONPATH','')}:{os.getcwd()}:{os.getcwd()}/src"}
    log = ds_out / "pipeline.log"
    cmd = [
        sys.executable, "src/run_pipeline.py",
        "--dataset", dataset,
        "--output-dir", str(ds_out),
        *shlex.split(pipeline_args),
    ]
    t0 = time.time()
    try:
        with open(log, "w", encoding="utf-8") as f:
            proc = subprocess.run(
                cmd, env=env, stdout=f, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            )
        status = "ok" if proc.returncode == 0 else f"exit_{proc.returncode}"
    except subprocess.TimeoutExpired:
        status = "timeout"
    except Exception as e:  # unexpected
        status = f"exception_{type(e).__name__}"
    return {
        "dataset": dataset, "status": status,
        "duration_s": round(time.time() - t0, 2),
        "worker_slot": slot, "mcp_port": port,
        "log": str(log),
    }


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    output_dir = Path(args.output_dir)
    (output_dir / "runs").mkdir(parents=True, exist_ok=True)

    datasets = _load_datasets(args)
    logger.info("orchestrator: %d datasets, concurrency=%d, timeout=%ds", len(datasets), args.concurrency, args.timeout)

    checkpoint = Checkpoint(output_dir / "checkpoint.jsonl")
    already_done = checkpoint.read_completed_datasets()
    pending = [d for d in datasets if d not in already_done]
    logger.info("orchestrator: resume skips %d already-completed datasets", len(datasets) - len(pending))

    failed: List[dict] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {}
        for i, ds in enumerate(pending):
            slot = i % args.concurrency
            port = _pick_port(args.mcp_port_base, slot)
            futs[ex.submit(run_one, ds, slot, port, output_dir, args.pipeline_args, args.timeout)] = ds
        for fut in as_completed(futs):
            r = fut.result()
            checkpoint.append(r)
            logger.info("done: %s status=%s duration=%.1fs", r["dataset"], r["status"], r["duration_s"])
            if r["status"] != "ok":
                failed.append(r)

    (output_dir / "failed.json").write_text(json.dumps(failed, indent=2))
    logger.info("orchestrator: %d failed (see %s)", len(failed), output_dir / "failed.json")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

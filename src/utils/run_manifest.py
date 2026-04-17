"""Run manifest writer: captures git state, CLI args, and pipeline config.

Writes run_manifest.json to the dataset output directory at pipeline start.
Captures git sha/branch/dirty for reproducibility. All fields are optional —
git failures do not block the pipeline.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


def _run_git(args: list[str]) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", *args],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if r.returncode != 0:
            return None
        return r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _git_sha() -> Optional[str]:
    return _run_git(["rev-parse", "HEAD"])


def _git_branch() -> Optional[str]:
    return _run_git(["rev-parse", "--abbrev-ref", "HEAD"])


def _git_dirty() -> Optional[bool]:
    out = _run_git(["status", "--porcelain"])
    if out is None:
        return None
    return bool(out)


def write_run_manifest(
    output_dir: Path,
    dataset: str,
    cli_args: Dict[str, Any],
    pipeline_config: Dict[str, Any],
    worker_id: Optional[int] = None,
    mcp_port: Optional[int] = None,
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "dataset": dataset,
        "git_sha": _git_sha(),
        "git_branch": _git_branch(),
        "git_dirty": _git_dirty(),
        "started_at": datetime.now().isoformat(),
        "cli_args": cli_args,
        "pipeline_config": pipeline_config,
        "worker_id": worker_id,
        "mcp_port": mcp_port,
    }
    path = output_dir / "run_manifest.json"
    path.write_text(json.dumps(manifest, indent=2))
    return path

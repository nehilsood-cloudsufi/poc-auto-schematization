"""In-memory run state management.

Tracks active pipeline runs. Completed run data lives on disk (output dirs,
manifests, feedback JSONs). This module only tracks in-flight state for
WebSocket broadcasting and API responses.
"""
import json
import os
import queue
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_lock = threading.Lock()
_runs: dict[str, "RunState"] = {}


@dataclass
class RunState:
    """State for a single pipeline run."""

    run_id: str
    dataset_name: str
    run_dir: str
    config: dict
    status: str = "pending"  # pending | running | complete | error | stopped | plan_ready
    result: dict = field(default_factory=dict)
    error: Optional[str] = None
    progress_queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=0))  # 0 = unbounded
    thread: Optional[threading.Thread] = None
    created_at: float = field(default_factory=time.time)
    # Cancellation (checked between pipeline phases)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    # Plan approval (for interactive plan review flow)
    plan_approved_event: threading.Event = field(default_factory=threading.Event)
    approved_plan: Optional[str] = None


def create_run(
    run_id: str,
    dataset_name: str,
    run_dir: str,
    config: dict,
) -> RunState:
    """Create and register a new run."""
    run = RunState(
        run_id=run_id,
        dataset_name=dataset_name,
        run_dir=run_dir,
        config=config,
    )
    with _lock:
        _runs[run_id] = run
    return run


def get_run(run_id: str) -> Optional[RunState]:
    """Get a run by ID, or None if not found."""
    with _lock:
        return _runs.get(run_id)


def get_or_load_run(run_id: str, base_dir: Path) -> Optional[RunState]:
    """Get from memory or load from disk for historical runs.

    Checks the in-memory store first. If not found, scans base_dir/{run_id}/
    on disk and, if the directory structure looks valid, reconstructs a
    RunState with status='complete' and registers it in memory.
    """
    with _lock:
        run = _runs.get(run_id)
        if run is not None:
            return run

    # Check disk
    run_dir = base_dir / run_id
    if not run_dir.is_dir():
        return None

    # Need an output subdirectory
    output_dir = run_dir / "output"
    if not output_dir.exists():
        return None

    # Try to read custom name from run_info.json
    dataset_name = ""
    run_info_path = run_dir / "run_info.json"
    if run_info_path.exists():
        try:
            info = json.loads(run_info_path.read_text())
            dataset_name = info.get("dataset_name", "")
        except (json.JSONDecodeError, OSError):
            pass

    if not dataset_name:
        # Fallback: find from output subdirectory (skip 'logs')
        for item in output_dir.iterdir():
            if item.is_dir() and item.name != "logs":
                dataset_name = item.name
                break

    if not dataset_name:
        return None

    # Detect run status
    dataset_dir = output_dir / dataset_name if dataset_name else None
    phase1_exists = (run_dir / "phase1_state.json").exists()
    has_pvmap = (dataset_dir / "generated_pvmap.csv").exists() if dataset_dir else False
    checkpoint_exists = (run_dir / "checkpoint.json").exists()

    # Check if run_info.json recorded a "running" status (interrupted by server restart)
    persisted_status = None
    if run_info_path.exists():
        try:
            info = json.loads(run_info_path.read_text())
            persisted_status = info.get("status")
        except (json.JSONDecodeError, OSError):
            pass

    if persisted_status == "running":
        # Pipeline was interrupted mid-execution (e.g., server hot-reload killed it)
        status = "error"
    elif checkpoint_exists:
        status = "stopped"
    elif phase1_exists and not has_pvmap:
        status = "plan_ready"
    else:
        status = "complete"

    # Read validation result from attempt JSONs on disk
    result = {}
    if dataset_dir:
        response_dir = dataset_dir / "generated_response"
        if response_dir.exists():
            attempt_files = sorted(response_dir.glob("attempt_*.json"))
            if attempt_files:
                try:
                    last = json.loads(attempt_files[-1].read_text())
                    validation_passed = last.get(
                        "validation_passed",
                        last.get("validation_success", False),
                    )
                    result = {
                        "validation_passed": validation_passed,
                        "exit_reason": "max_retries" if len(attempt_files) > 1 else "complete",
                        "retry_count": max(0, len(attempt_files) - 1),
                    }
                except (json.JSONDecodeError, OSError):
                    pass

    # Load into memory
    run = RunState(
        run_id=run_id,
        dataset_name=dataset_name,
        run_dir=str(run_dir),
        config={},
        status=status,
        result=result,
    )
    with _lock:
        # Re-check in case another thread loaded it while we were reading disk
        existing = _runs.get(run_id)
        if existing is not None:
            return existing
        _runs[run_id] = run
    return run


def list_runs() -> list[RunState]:
    """List all tracked runs."""
    with _lock:
        return list(_runs.values())


def delete_run(run_id: str) -> bool:
    """Remove a run from tracking. Returns True if it existed."""
    with _lock:
        return _runs.pop(run_id, None) is not None


def read_run_info(run_dir: Path) -> dict:
    """Read run_info.json from a run directory, applying default values.

    Defaults applied when fields are absent:
      - display_name: falls back to dataset_name
      - notes: ""
      - archived: False

    Returns {} if run_info.json does not exist.
    """
    info_path = run_dir / "run_info.json"
    if not info_path.exists():
        return {}

    try:
        info = json.loads(info_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}

    # Apply defaults for optional UI fields
    if "display_name" not in info:
        info["display_name"] = info.get("dataset_name", "")
    if "notes" not in info:
        info["notes"] = ""
    if "archived" not in info:
        info["archived"] = False

    return info


def write_run_info(run_dir: Path, updates: dict) -> dict:
    """Merge updates into run_info.json and write back atomically.

    Reads existing content first so non-updated fields are preserved.
    Uses temp file + os.replace for atomic writes (no TOCTOU race).
    Returns the full updated dict.
    """
    info_path = run_dir / "run_info.json"

    # Load existing content (if any)
    existing: dict = {}
    if info_path.exists():
        try:
            existing = json.loads(info_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    existing.update(updates)

    # Atomic write: write to temp file then replace
    run_dir.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_name = tempfile.mkstemp(dir=str(run_dir), suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as tmp:
            json.dump(existing, tmp, indent=2, default=str)
        os.replace(tmp_name, str(info_path))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return existing

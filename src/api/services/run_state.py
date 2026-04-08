"""In-memory run state management.

Tracks active pipeline runs. Completed run data lives on disk (output dirs,
manifests, feedback JSONs). This module only tracks in-flight state for
WebSocket broadcasting and API responses.
"""
import json
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_runs: dict[str, "RunState"] = {}


@dataclass
class RunState:
    """State for a single pipeline run."""

    run_id: str
    dataset_name: str
    run_dir: str
    config: dict
    status: str = "pending"  # pending | running | complete | error | stopped
    result: dict = field(default_factory=dict)
    error: Optional[str] = None
    progress_queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=200))
    thread: Optional[threading.Thread] = None
    created_at: float = field(default_factory=time.time)
    # Cancellation (checked between pipeline phases)
    cancel_event: threading.Event = field(default_factory=threading.Event)


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
    _runs[run_id] = run
    return run


def get_run(run_id: str) -> Optional[RunState]:
    """Get a run by ID, or None if not found."""
    return _runs.get(run_id)


def get_or_load_run(run_id: str, base_dir: Path) -> Optional[RunState]:
    """Get from memory or load from disk for historical runs.

    Checks the in-memory store first. If not found, scans base_dir/{run_id}/
    on disk and, if the directory structure looks valid, reconstructs a
    RunState with status='complete' and registers it in memory.
    """
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

    if phase1_exists and not has_pvmap:
        status = "plan_ready"
    elif checkpoint_exists:
        status = "stopped"
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
    _runs[run_id] = run
    return run


def list_runs() -> list[RunState]:
    """List all tracked runs."""
    return list(_runs.values())


def delete_run(run_id: str) -> bool:
    """Remove a run from tracking. Returns True if it existed."""
    return _runs.pop(run_id, None) is not None

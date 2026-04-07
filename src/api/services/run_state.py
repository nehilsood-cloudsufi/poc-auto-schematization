"""In-memory run state management.

Tracks active pipeline runs. Completed run data lives on disk (output dirs,
manifests, feedback JSONs). This module only tracks in-flight state for
WebSocket broadcasting and API responses.
"""
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
    status: str = "pending"  # pending | running | complete | error
    result: dict = field(default_factory=dict)
    error: Optional[str] = None
    progress_queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=200))
    thread: Optional[threading.Thread] = None
    created_at: float = field(default_factory=time.time)


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

    # Find dataset name from the output subdirectory (skip 'logs')
    dataset_name = ""
    for item in output_dir.iterdir():
        if item.is_dir() and item.name != "logs":
            dataset_name = item.name
            break

    if not dataset_name:
        return None

    # Load into memory as a completed run
    run = RunState(
        run_id=run_id,
        dataset_name=dataset_name,
        run_dir=str(run_dir),
        config={},
        status="complete",
    )
    _runs[run_id] = run
    return run


def list_runs() -> list[RunState]:
    """List all tracked runs."""
    return list(_runs.values())


def delete_run(run_id: str) -> bool:
    """Remove a run from tracking. Returns True if it existed."""
    return _runs.pop(run_id, None) is not None

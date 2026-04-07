"""In-memory run state management.

Tracks active pipeline runs. Completed run data lives on disk (output dirs,
manifests, feedback JSONs). This module only tracks in-flight state for
WebSocket broadcasting and API responses.
"""
import queue
import threading
import time
from dataclasses import dataclass, field
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


def list_runs() -> list[RunState]:
    """List all tracked runs."""
    return list(_runs.values())


def delete_run(run_id: str) -> bool:
    """Remove a run from tracking. Returns True if it existed."""
    return _runs.pop(run_id, None) is not None

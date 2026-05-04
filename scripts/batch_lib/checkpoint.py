"""Append-only JSONL checkpoint with fcntl file lock.

The orchestrator appends one record per completed dataset. Multiple workers
may call append() concurrently; a POSIX exclusive lock serializes the writes.
read_completed_datasets() parses the file (tolerating corrupt lines) and
returns the set of dataset names that have a record.
"""
from __future__ import annotations

import fcntl
import json
import logging
from pathlib import Path
from typing import Any, Dict, Set

logger = logging.getLogger(__name__)


class Checkpoint:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: Dict[str, Any]) -> None:
        line = json.dumps(record) + "\n"
        # Open in append mode + lock so concurrent writers interleave cleanly
        with open(self.path, "a", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(line)
                f.flush()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def read_completed_datasets(self) -> Set[str]:
        if not self.path.exists():
            return set()
        done: Set[str] = set()
        with open(self.path, "r", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                for i, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("checkpoint: skipping corrupt line %d", i)
                        continue
                    ds = rec.get("dataset")
                    if ds:
                        done.add(ds)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return done

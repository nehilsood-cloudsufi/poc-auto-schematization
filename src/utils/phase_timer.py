"""Per-phase wall-time tracking for pipeline runs.

Writes a flat JSON document mapping phase name -> {start, end, duration_s}, plus
a synthetic 'total' phase spanning the whole PhaseTimer lifetime.

Design notes:
- No threading synchronization: pipeline phases run serially in a single asyncio
  loop, so concurrent use isn't expected.
- finalize() writes atomically via tmp file + os.replace so partial dumps are
  never observed by a concurrent reader.
- Works even if a phase raises: __exit__ still records the end time.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator


class PhaseTimer:
    def __init__(self, output_path: Path):
        self._output_path = Path(output_path)
        self._start_wall = time.time()
        self._start_iso = datetime.fromtimestamp(self._start_wall).isoformat()
        self._phases: Dict[str, Dict[str, object]] = {}

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        start_wall = time.time()
        start_iso = datetime.fromtimestamp(start_wall).isoformat()
        try:
            yield
        finally:
            end_wall = time.time()
            self._phases[name] = {
                "start": start_iso,
                "end": datetime.fromtimestamp(end_wall).isoformat(),
                "duration_s": round(end_wall - start_wall, 3),
            }

    def finalize(self) -> None:
        end_wall = time.time()
        data = dict(self._phases)
        data["total"] = {
            "start": self._start_iso,
            "end": datetime.fromtimestamp(end_wall).isoformat(),
            "duration_s": round(end_wall - self._start_wall, 3),
        }
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix=self._output_path.name + ".tmp",
            dir=self._output_path.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self._output_path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

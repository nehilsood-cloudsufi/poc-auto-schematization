"""Tests for PhaseTimer context manager."""
import json
import time
from pathlib import Path

import pytest

from src.utils.phase_timer import PhaseTimer


def test_phase_timer_records_duration(tmp_path: Path):
    output = tmp_path / "phase_timings.json"
    timer = PhaseTimer(output_path=output)
    with timer.phase("sampling"):
        time.sleep(0.01)
    timer.finalize()

    data = json.loads(output.read_text())
    assert "sampling" in data
    assert data["sampling"]["duration_s"] >= 0.01
    assert "start" in data["sampling"]
    assert "end" in data["sampling"]
    assert "total" in data
    assert data["total"]["duration_s"] >= 0.01


def test_phase_timer_multiple_phases(tmp_path: Path):
    output = tmp_path / "phase_timings.json"
    timer = PhaseTimer(output_path=output)
    with timer.phase("discovery"):
        time.sleep(0.005)
    with timer.phase("sampling"):
        time.sleep(0.005)
    timer.finalize()

    data = json.loads(output.read_text())
    assert set(data.keys()) >= {"discovery", "sampling", "total"}
    # total >= sum of phases (serial execution)
    assert data["total"]["duration_s"] >= data["discovery"]["duration_s"] + data["sampling"]["duration_s"] - 0.001


def test_phase_timer_writes_on_exception(tmp_path: Path):
    """If a phase raises, timings captured so far are still written by finalize()."""
    output = tmp_path / "phase_timings.json"
    timer = PhaseTimer(output_path=output)
    with timer.phase("discovery"):
        time.sleep(0.005)
    try:
        with timer.phase("sampling"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    timer.finalize()

    data = json.loads(output.read_text())
    assert "discovery" in data
    assert "sampling" in data  # end time recorded even on exception


def test_phase_timer_atomic_write(tmp_path: Path):
    """finalize() writes atomically via temp file + rename."""
    output = tmp_path / "phase_timings.json"
    timer = PhaseTimer(output_path=output)
    with timer.phase("x"):
        pass
    timer.finalize()
    # No leftover temp files
    assert not list(tmp_path.glob("phase_timings.json.tmp*"))
    assert output.exists()

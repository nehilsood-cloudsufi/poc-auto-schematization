"""Tests for Checkpoint JSONL helper."""
import json
from pathlib import Path

import pytest

from scripts.batch_lib.checkpoint import Checkpoint


def test_checkpoint_appends(tmp_path: Path):
    cp_path = tmp_path / "checkpoint.jsonl"
    cp = Checkpoint(cp_path)
    cp.append({"dataset": "a", "status": "ok"})
    cp.append({"dataset": "b", "status": "timeout"})

    lines = cp_path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["dataset"] == "a"
    assert json.loads(lines[1])["dataset"] == "b"


def test_checkpoint_read_completed(tmp_path: Path):
    cp_path = tmp_path / "checkpoint.jsonl"
    cp = Checkpoint(cp_path)
    cp.append({"dataset": "a", "status": "ok"})
    cp.append({"dataset": "b", "status": "ok"})

    done = cp.read_completed_datasets()
    assert done == {"a", "b"}


def test_checkpoint_read_empty_when_missing(tmp_path: Path):
    cp_path = tmp_path / "nope.jsonl"
    cp = Checkpoint(cp_path)
    assert cp.read_completed_datasets() == set()


def test_checkpoint_handles_corrupt_line(tmp_path: Path):
    """A garbled line should not crash resumption; it's skipped with a warning."""
    cp_path = tmp_path / "checkpoint.jsonl"
    cp_path.write_text('{"dataset":"a","status":"ok"}\n<garbage>\n{"dataset":"b","status":"ok"}\n')
    cp = Checkpoint(cp_path)
    done = cp.read_completed_datasets()
    assert done == {"a", "b"}

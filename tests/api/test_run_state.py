"""Tests for in-memory run state management."""
import queue
from pathlib import Path

import pytest

from src.api.services.run_state import RunState, create_run, get_run, get_or_load_run, list_runs, delete_run


class TestRunState:
    def setup_method(self):
        """Clear global state between tests."""
        from src.api.services import run_state
        run_state._runs.clear()

    def test_create_run(self):
        run = create_run(
            run_id="abc123",
            dataset_name="test_dataset",
            run_dir="/tmp/test",
            config={"model": "gemini-3.1-pro-preview"},
        )
        assert run.run_id == "abc123"
        assert run.status == "pending"
        assert run.dataset_name == "test_dataset"
        assert isinstance(run.progress_queue, queue.Queue)

    def test_get_run_exists(self):
        create_run(run_id="abc123", dataset_name="test", run_dir="/tmp/test", config={})
        run = get_run("abc123")
        assert run is not None
        assert run.run_id == "abc123"

    def test_get_run_missing(self):
        assert get_run("nonexistent") is None

    def test_list_runs(self):
        create_run(run_id="run1", dataset_name="ds1", run_dir="/tmp/r1", config={})
        create_run(run_id="run2", dataset_name="ds2", run_dir="/tmp/r2", config={})
        runs = list_runs()
        assert len(runs) == 2
        ids = {r.run_id for r in runs}
        assert ids == {"run1", "run2"}

    def test_delete_run(self):
        create_run(run_id="run1", dataset_name="ds1", run_dir="/tmp/r1", config={})
        deleted = delete_run("run1")
        assert deleted is True
        assert get_run("run1") is None

    def test_delete_run_missing(self):
        assert delete_run("nonexistent") is False

    def test_run_state_defaults(self):
        run = create_run(run_id="r1", dataset_name="ds", run_dir="/tmp", config={})
        assert run.result == {}
        assert run.error is None
        assert run.thread is None


class TestGetOrLoadRun:
    def setup_method(self):
        from src.api.services import run_state
        run_state._runs.clear()

    def test_returns_in_memory_run(self, tmp_path):
        """Returns existing in-memory run without touching disk."""
        create_run(run_id="r1", dataset_name="ds1", run_dir="/tmp/r1", config={})
        run = get_or_load_run("r1", tmp_path)
        assert run is not None
        assert run.run_id == "r1"
        assert run.dataset_name == "ds1"

    def test_loads_run_from_disk(self, tmp_path):
        """Reconstructs a RunState from a valid on-disk run directory."""
        run_dir = tmp_path / "hist_run"
        output_ds = run_dir / "output" / "my_dataset"
        output_ds.mkdir(parents=True)

        run = get_or_load_run("hist_run", tmp_path)
        assert run is not None
        assert run.run_id == "hist_run"
        assert run.dataset_name == "my_dataset"
        assert run.status == "complete"

    def test_loaded_run_registered_in_memory(self, tmp_path):
        """A disk-loaded run is added to _runs so subsequent calls are fast."""
        run_dir = tmp_path / "hist_run"
        (run_dir / "output" / "my_dataset").mkdir(parents=True)

        get_or_load_run("hist_run", tmp_path)
        # Second call should hit memory, not disk
        run2 = get_or_load_run("hist_run", tmp_path)
        assert run2 is not None
        assert run2.run_id == "hist_run"

    def test_returns_none_when_run_dir_missing(self, tmp_path):
        """Returns None if base_dir/{run_id} does not exist."""
        run = get_or_load_run("no_such_run", tmp_path)
        assert run is None

    def test_returns_none_when_no_output_subdir(self, tmp_path):
        """Returns None if run_dir exists but has no output/ subdirectory."""
        (tmp_path / "orphan_run").mkdir()
        run = get_or_load_run("orphan_run", tmp_path)
        assert run is None

    def test_returns_none_when_output_has_no_dataset_dir(self, tmp_path):
        """Returns None if output/ exists but has no non-logs subdirectory."""
        run_dir = tmp_path / "empty_run"
        (run_dir / "output" / "logs").mkdir(parents=True)

        run = get_or_load_run("empty_run", tmp_path)
        assert run is None

    def test_ignores_logs_dir_when_finding_dataset(self, tmp_path):
        """Skips the 'logs' directory when scanning for dataset name."""
        run_dir = tmp_path / "run_with_logs"
        (run_dir / "output" / "logs").mkdir(parents=True)
        (run_dir / "output" / "real_dataset").mkdir(parents=True)

        run = get_or_load_run("run_with_logs", tmp_path)
        assert run is not None
        assert run.dataset_name == "real_dataset"

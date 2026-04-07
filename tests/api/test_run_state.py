"""Tests for in-memory run state management."""
import queue

import pytest

from src.api.services.run_state import RunState, create_run, get_run, list_runs, delete_run


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

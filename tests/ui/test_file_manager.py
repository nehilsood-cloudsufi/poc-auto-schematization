"""Tests for src.ui.services.file_manager."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Mock streamlit before any src.ui imports
_mock_st = MagicMock()
_mock_st.session_state = {}
sys.modules.setdefault("streamlit", _mock_st)

from src.ui.services.file_manager import (
    create_run_directory,
    save_uploaded_file,
    get_output_files,
    snapshot_version,
    save_run_manifest,
    save_edited_files,
    get_latest_version,
    discover_historical_runs,
    cleanup_old_runs,
)


# ---------------------------------------------------------------------------
# create_run_directory
# ---------------------------------------------------------------------------
class TestCreateRunDirectory:

    def test_creates_input_and_output_subdirs(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.ui.services.file_manager.UI_OUTPUT_DIR", tmp_path)
        run_dir = create_run_directory("run-001")
        assert (run_dir / "input").is_dir()
        assert (run_dir / "output").is_dir()

    def test_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.ui.services.file_manager.UI_OUTPUT_DIR", tmp_path)
        d1 = create_run_directory("run-001")
        d2 = create_run_directory("run-001")
        assert d1 == d2


# ---------------------------------------------------------------------------
# save_uploaded_file
# ---------------------------------------------------------------------------
class TestSaveUploadedFile:

    def test_writes_bytes(self, tmp_path):
        uploaded = MagicMock()
        uploaded.name = "data.csv"
        uploaded.getvalue.return_value = b"a,b\n1,2\n"

        path = save_uploaded_file(uploaded, tmp_path)
        assert path.name == "data.csv"
        assert path.read_bytes() == b"a,b\n1,2\n"

    def test_custom_filename(self, tmp_path):
        uploaded = MagicMock()
        uploaded.name = "original.csv"
        uploaded.getvalue.return_value = b"x"

        path = save_uploaded_file(uploaded, tmp_path, filename="renamed.csv")
        assert path.name == "renamed.csv"

    def test_creates_target_dir(self, tmp_path):
        uploaded = MagicMock()
        uploaded.name = "f.csv"
        uploaded.getvalue.return_value = b"data"
        deep = tmp_path / "a" / "b"
        path = save_uploaded_file(uploaded, deep)
        assert path.exists()


# ---------------------------------------------------------------------------
# get_output_files
# ---------------------------------------------------------------------------
class TestGetOutputFiles:

    def test_returns_only_existing(self, tmp_path):
        (tmp_path / "generated_pvmap.csv").write_text("col\n")
        (tmp_path / "generation_notes.md").write_text("# Notes\n")

        result = get_output_files(tmp_path)
        assert "generated_pvmap.csv" in result
        assert "generation_notes.md" in result
        assert "processed.csv" not in result

    def test_empty_dir(self, tmp_path):
        assert get_output_files(tmp_path) == {}


# ---------------------------------------------------------------------------
# snapshot_version
# ---------------------------------------------------------------------------
class TestSnapshotVersion:

    def test_copies_files_to_version_dir(self, tmp_path):
        (tmp_path / "generated_pvmap.csv").write_text("col\n")
        (tmp_path / "processed.csv").write_text("data\n")

        v_dir = snapshot_version(tmp_path, 1)
        assert v_dir.name == "v1"
        assert (v_dir / "generated_pvmap.csv").read_text() == "col\n"
        assert (v_dir / "processed.csv").read_text() == "data\n"

    def test_copies_generated_response_dir(self, tmp_path):
        resp_dir = tmp_path / "generated_response"
        resp_dir.mkdir()
        (resp_dir / "attempt_1.md").write_text("attempt")

        snapshot_version(tmp_path, 2)
        assert (tmp_path / "v2" / "generated_response" / "attempt_1.md").exists()

    def test_skips_non_file_non_generated_response(self, tmp_path):
        (tmp_path / "other_dir").mkdir()
        (tmp_path / "a.txt").write_text("x")
        v_dir = snapshot_version(tmp_path, 1)
        assert not (v_dir / "other_dir").exists()
        assert (v_dir / "a.txt").exists()


# ---------------------------------------------------------------------------
# save_run_manifest
# ---------------------------------------------------------------------------
class TestSaveRunManifest:

    def test_writes_valid_json(self, tmp_path):
        config = {"run_id": "r1", "dataset_name": "ds", "model": "gemini"}
        result = {"retry_count": 2, "exit_reason": "max_retries", "validation_passed": True}

        manifest_path = save_run_manifest(tmp_path, 1, config, result)
        data = json.loads(manifest_path.read_text())
        assert data["run_id"] == "r1"
        assert data["dataset_name"] == "ds"
        assert data["attempts"] == 3  # retry_count + 1
        assert data["validation_passed"] is True
        assert "timestamp" in data

    def test_handles_missing_quality_metrics(self, tmp_path):
        config = {}
        result = {}
        manifest_path = save_run_manifest(tmp_path, 1, config, result)
        data = json.loads(manifest_path.read_text())
        assert data["heuristic_score"] == 0

    def test_handles_non_dict_quality_metrics(self, tmp_path):
        config = {}
        result = {"quality_metrics": "not_a_dict"}
        manifest_path = save_run_manifest(tmp_path, 1, config, result)
        data = json.loads(manifest_path.read_text())
        assert data["heuristic_score"] == 0


# ---------------------------------------------------------------------------
# save_edited_files
# ---------------------------------------------------------------------------
class TestSaveEditedFiles:

    def test_saves_pvmap_csv(self, tmp_path):
        import pandas as pd
        df = pd.DataFrame({"col": [1, 2, 3]})
        feedback_dir = save_edited_files(tmp_path, 1, edited_pvmap_df=df)
        assert (feedback_dir / "edited_pvmap.csv").exists()

    def test_saves_metadata_csv(self, tmp_path):
        import pandas as pd
        df = pd.DataFrame({"key": ["a"], "value": ["b"]})
        feedback_dir = save_edited_files(tmp_path, 1, edited_metadata_df=df)
        assert (feedback_dir / "edited_metadata.csv").exists()

    def test_no_files_when_none(self, tmp_path):
        feedback_dir = save_edited_files(tmp_path, 1)
        assert feedback_dir.is_dir()
        assert list(feedback_dir.iterdir()) == []


# ---------------------------------------------------------------------------
# get_latest_version
# ---------------------------------------------------------------------------
class TestGetLatestVersion:

    def test_returns_zero_for_empty(self, tmp_path):
        assert get_latest_version(tmp_path) == 0

    def test_returns_highest(self, tmp_path):
        (tmp_path / "v1").mkdir()
        (tmp_path / "v3").mkdir()
        (tmp_path / "v2").mkdir()
        assert get_latest_version(tmp_path) == 3

    def test_ignores_non_version_dirs(self, tmp_path):
        (tmp_path / "v1").mkdir()
        (tmp_path / "logs").mkdir()
        (tmp_path / "vnotanumber").mkdir()
        assert get_latest_version(tmp_path) == 1

    def test_nonexistent_dir(self, tmp_path):
        assert get_latest_version(tmp_path / "no_such_dir") == 0


# ---------------------------------------------------------------------------
# discover_historical_runs
# ---------------------------------------------------------------------------
class TestDiscoverHistoricalRuns:

    def test_empty_when_no_output_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.ui.services.file_manager.UI_OUTPUT_DIR", tmp_path / "nope")
        assert discover_historical_runs() == []

    def test_finds_run_with_pvmap(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.ui.services.file_manager.UI_OUTPUT_DIR", tmp_path)
        # Create structure: {run_id}/output/{dataset}/generated_pvmap.csv
        ds_dir = tmp_path / "run-abc" / "output" / "my_dataset"
        ds_dir.mkdir(parents=True)
        (ds_dir / "generated_pvmap.csv").write_text("col\n")

        runs = discover_historical_runs()
        assert len(runs) == 1
        assert runs[0]["dataset_name"] == "my_dataset"
        assert runs[0]["has_pvmap"] is True

    def test_skips_run_without_output(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.ui.services.file_manager.UI_OUTPUT_DIR", tmp_path)
        (tmp_path / "run-x" / "input").mkdir(parents=True)
        assert discover_historical_runs() == []

    def test_reads_attempt_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.ui.services.file_manager.UI_OUTPUT_DIR", tmp_path)
        ds_dir = tmp_path / "run-j" / "output" / "ds"
        resp_dir = ds_dir / "generated_response"
        resp_dir.mkdir(parents=True)
        (resp_dir / "attempt_1.json").write_text(json.dumps({
            "model": "gemini-test", "start_time": "2026-01-01T00:00:00",
            "validation_success": False,
        }))
        (resp_dir / "attempt_2.json").write_text(json.dumps({
            "model": "gemini-test", "start_time": "2026-01-01T00:01:00",
            "validation_success": True,
        }))

        runs = discover_historical_runs()
        assert len(runs) == 1
        assert runs[0]["model"] == "gemini-test"
        assert runs[0]["attempts"] == 2
        assert runs[0]["result"]["validation_passed"] is True


# ---------------------------------------------------------------------------
# cleanup_old_runs
# ---------------------------------------------------------------------------
class TestCleanupOldRuns:

    def test_removes_old_dirs(self, tmp_path, monkeypatch):
        import os, time
        monkeypatch.setattr("src.ui.services.file_manager.UI_OUTPUT_DIR", tmp_path)

        old_dir = tmp_path / "old-run"
        old_dir.mkdir()
        # Set mtime 48 hours ago
        old_time = time.time() - 48 * 3600
        os.utime(old_dir, (old_time, old_time))

        new_dir = tmp_path / "new-run"
        new_dir.mkdir()

        cleanup_old_runs(max_age_hours=24)
        assert not old_dir.exists()
        assert new_dir.exists()

    def test_noop_when_no_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.ui.services.file_manager.UI_OUTPUT_DIR", tmp_path / "nope")
        cleanup_old_runs()  # should not raise

"""Tests for framework-agnostic file manager."""
import json
import tempfile
from pathlib import Path

import pytest

from src.api.services.file_manager import (
    create_run_directory,
    save_uploaded_bytes,
    get_output_files,
    snapshot_version,
    get_latest_version,
    discover_historical_runs,
)


class TestFileManager:
    def test_create_run_directory(self, tmp_path):
        run_dir = create_run_directory("test123", base_dir=tmp_path)
        assert (run_dir / "input").is_dir()
        assert (run_dir / "output").is_dir()

    def test_save_uploaded_bytes(self, tmp_path):
        target_dir = tmp_path / "input"
        path = save_uploaded_bytes(b"col1,col2\na,b\n", target_dir, "data.csv")
        assert path.exists()
        assert path.read_bytes() == b"col1,col2\na,b\n"

    def test_get_output_files(self, tmp_path):
        (tmp_path / "generated_pvmap.csv").write_text("a,b\n1,2")
        (tmp_path / "generation_notes.md").write_text("# Notes")
        (tmp_path / "random_file.txt").write_text("ignored")
        files = get_output_files(tmp_path)
        assert "generated_pvmap.csv" in files
        assert "generation_notes.md" in files
        assert "random_file.txt" not in files

    def test_snapshot_version(self, tmp_path):
        (tmp_path / "generated_pvmap.csv").write_text("a,b")
        version_dir = snapshot_version(tmp_path, 1)
        assert (version_dir / "generated_pvmap.csv").read_text() == "a,b"

    def test_get_latest_version_empty(self, tmp_path):
        assert get_latest_version(tmp_path) == 0

    def test_get_latest_version_with_versions(self, tmp_path):
        (tmp_path / "v1").mkdir()
        (tmp_path / "v3").mkdir()
        assert get_latest_version(tmp_path) == 3

    def test_discover_historical_runs_empty(self, tmp_path):
        assert discover_historical_runs(base_dir=tmp_path) == []

"""Tests for write_run_manifest."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.run_manifest import write_run_manifest


def test_write_run_manifest_basic(tmp_path: Path):
    with patch("src.utils.run_manifest._git_sha", return_value="abc1234"), \
         patch("src.utils.run_manifest._git_branch", return_value="feature/x"), \
         patch("src.utils.run_manifest._git_dirty", return_value=False):
        path = write_run_manifest(
            output_dir=tmp_path,
            dataset="some_ds",
            cli_args={"model": "gemini-3.1-pro-preview", "thinking_level": "high"},
            pipeline_config={"enable_mcp": True, "prompt_version": "v3"},
            worker_id=0,
            mcp_port=3000,
        )

    assert path == tmp_path / "run_manifest.json"
    data = json.loads(path.read_text())
    assert data["dataset"] == "some_ds"
    assert data["git_sha"] == "abc1234"
    assert data["git_branch"] == "feature/x"
    assert data["git_dirty"] is False
    assert data["cli_args"]["model"] == "gemini-3.1-pro-preview"
    assert data["pipeline_config"]["enable_mcp"] is True
    assert data["worker_id"] == 0
    assert data["mcp_port"] == 3000
    assert "started_at" in data


def test_write_run_manifest_handles_git_failure(tmp_path: Path):
    """If git isn't available, manifest still writes with null git fields."""
    with patch("src.utils.run_manifest._git_sha", return_value=None), \
         patch("src.utils.run_manifest._git_branch", return_value=None), \
         patch("src.utils.run_manifest._git_dirty", return_value=None):
        path = write_run_manifest(
            output_dir=tmp_path,
            dataset="x",
            cli_args={},
            pipeline_config={},
            worker_id=None,
            mcp_port=None,
        )
    data = json.loads(path.read_text())
    assert data["git_sha"] is None
    assert data["git_branch"] is None

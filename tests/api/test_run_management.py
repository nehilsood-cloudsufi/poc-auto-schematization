"""Tests for run management: run info helpers, PATCH, archive, and DELETE endpoints."""
import json
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from src.api.main import create_app
from src.api.services import run_state
from src.api.services.run_state import read_run_info, write_run_info


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def run_dir(tmp_path):
    """A temp run directory with a minimal run_info.json."""
    d = tmp_path / "test-run-123"
    d.mkdir()
    (d / "run_info.json").write_text(
        json.dumps({"run_id": "test-run-123", "dataset_name": "test_dataset"})
    )
    return d


@pytest.fixture
def client(tmp_path):
    run_state._runs.clear()
    app = create_app(output_dir=tmp_path)
    yield TestClient(app)
    run_state._runs.clear()


@pytest.fixture
def run_dir_in_output(tmp_path):
    """Create a run directory inside tmp_path (which is the output_dir for client)."""
    run_id = "test-run-123"
    d = tmp_path / run_id
    (d / "output" / "test_dataset").mkdir(parents=True)
    (d / "run_info.json").write_text(
        json.dumps({"run_id": run_id, "dataset_name": "test_dataset"})
    )
    return d, run_id, tmp_path


# ---------------------------------------------------------------------------
# Task 1: read_run_info / write_run_info helpers
# ---------------------------------------------------------------------------

class TestReadRunInfo:
    def test_read_run_info_returns_defaults_for_missing_fields(self, run_dir):
        """Fields missing from run_info.json get sensible defaults."""
        info = read_run_info(run_dir)
        # dataset_name was in the file
        assert info["dataset_name"] == "test_dataset"
        # display_name defaults to dataset_name
        assert info["display_name"] == "test_dataset"
        # notes defaults to ""
        assert info["notes"] == ""
        # archived defaults to False
        assert info["archived"] is False

    def test_read_run_info_missing_file(self, tmp_path):
        """Returns {} when run_info.json does not exist."""
        empty_dir = tmp_path / "no-such-run"
        empty_dir.mkdir()
        info = read_run_info(empty_dir)
        assert info == {}

    def test_read_run_info_honours_existing_display_name(self, tmp_path):
        """Does not override display_name if already set in file."""
        d = tmp_path / "myrun"
        d.mkdir()
        (d / "run_info.json").write_text(
            json.dumps({
                "run_id": "myrun",
                "dataset_name": "ds",
                "display_name": "My Custom Name",
            })
        )
        info = read_run_info(d)
        assert info["display_name"] == "My Custom Name"


class TestWriteRunInfo:
    def test_write_run_info_updates_fields(self, run_dir):
        """Updated fields are persisted and returned."""
        result = write_run_info(run_dir, {"display_name": "Pretty Name"})
        assert result["display_name"] == "Pretty Name"

        # Verify it's actually on disk
        on_disk = json.loads((run_dir / "run_info.json").read_text())
        assert on_disk["display_name"] == "Pretty Name"

    def test_write_run_info_preserves_existing_fields(self, run_dir):
        """Fields not in updates are preserved from existing file."""
        write_run_info(run_dir, {"display_name": "Pretty Name"})
        result = write_run_info(run_dir, {"notes": "some notes"})

        # Both display_name (from previous write) and notes should be present
        assert result["notes"] == "some notes"
        assert result["dataset_name"] == "test_dataset"
        assert result["run_id"] == "test-run-123"

    def test_write_run_info_creates_file_if_missing(self, tmp_path):
        """write_run_info creates run_info.json even if it did not exist."""
        d = tmp_path / "newrun"
        d.mkdir()
        result = write_run_info(d, {"run_id": "newrun", "dataset_name": "ds"})
        assert result["run_id"] == "newrun"
        assert (d / "run_info.json").exists()


# ---------------------------------------------------------------------------
# Task 2: PATCH /runs/{run_id}
# ---------------------------------------------------------------------------

class TestPatchRun:
    def _make_client_with_run(self, tmp_path, run_id="run-patch-test"):
        run_state._runs.clear()
        app = create_app(output_dir=tmp_path)
        d = tmp_path / run_id
        (d / "output" / "ds").mkdir(parents=True)
        (d / "run_info.json").write_text(
            json.dumps({"run_id": run_id, "dataset_name": "ds"})
        )
        return TestClient(app), run_id

    def test_patch_run_updates_display_name(self, tmp_path):
        client, run_id = self._make_client_with_run(tmp_path)
        resp = client.patch(f"/api/runs/{run_id}", json={"display_name": "My Run"})
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "My Run"
        run_state._runs.clear()

    def test_patch_run_updates_notes(self, tmp_path):
        client, run_id = self._make_client_with_run(tmp_path)
        resp = client.patch(f"/api/runs/{run_id}", json={"notes": "Interesting results"})
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Interesting results"
        run_state._runs.clear()

    def test_patch_run_404_for_unknown(self, tmp_path):
        run_state._runs.clear()
        app = create_app(output_dir=tmp_path)
        client = TestClient(app)
        resp = client.patch("/api/runs/ghost-run-xyz", json={"display_name": "X"})
        assert resp.status_code == 404
        run_state._runs.clear()

    def test_patch_run_ignores_none_fields(self, tmp_path):
        """Sending null for a field should not overwrite existing value."""
        client, run_id = self._make_client_with_run(tmp_path)
        # First set a display_name
        client.patch(f"/api/runs/{run_id}", json={"display_name": "Keep Me"})
        # Then patch with only notes (display_name omitted / null)
        resp = client.patch(f"/api/runs/{run_id}", json={"notes": "hello"})
        assert resp.json()["display_name"] == "Keep Me"
        run_state._runs.clear()


# ---------------------------------------------------------------------------
# Task 3: POST /runs/{run_id}/archive + list filtering
# ---------------------------------------------------------------------------

class TestArchiveRun:
    def _setup(self, tmp_path, run_id="run-archive-test"):
        run_state._runs.clear()
        app = create_app(output_dir=tmp_path)
        d = tmp_path / run_id
        (d / "output" / "ds").mkdir(parents=True)
        (d / "run_info.json").write_text(
            json.dumps({"run_id": run_id, "dataset_name": "ds"})
        )
        return TestClient(app), run_id

    def test_archive_run_toggles_archived(self, tmp_path):
        client, run_id = self._setup(tmp_path)
        # First call: archive
        resp = client.post(f"/api/runs/{run_id}/archive")
        assert resp.status_code == 200
        assert resp.json()["archived"] is True

        # Second call: unarchive
        resp = client.post(f"/api/runs/{run_id}/archive")
        assert resp.status_code == 200
        assert resp.json()["archived"] is False
        run_state._runs.clear()

    def test_archive_run_404_for_unknown(self, tmp_path):
        run_state._runs.clear()
        app = create_app(output_dir=tmp_path)
        client = TestClient(app)
        resp = client.post("/api/runs/ghost-run/archive")
        assert resp.status_code == 404
        run_state._runs.clear()

    def test_list_runs_excludes_archived_by_default(self, tmp_path):
        run_state._runs.clear()
        app = create_app(output_dir=tmp_path)
        client = TestClient(app)

        # Create two runs, archive one
        for run_id, ds in [("run-a", "ds_a"), ("run-b", "ds_b")]:
            d = tmp_path / run_id
            (d / "output" / ds).mkdir(parents=True)
            (d / "run_info.json").write_text(
                json.dumps({"run_id": run_id, "dataset_name": ds})
            )

        # Archive run-a
        client.post("/api/runs/run-a/archive")

        resp = client.get("/api/runs")
        assert resp.status_code == 200
        run_ids = [r["run_id"] for r in resp.json()]
        assert "run-a" not in run_ids
        assert "run-b" in run_ids
        run_state._runs.clear()

    def test_list_runs_includes_archived_when_requested(self, tmp_path):
        run_state._runs.clear()
        app = create_app(output_dir=tmp_path)
        client = TestClient(app)

        for run_id, ds in [("run-a", "ds_a"), ("run-b", "ds_b")]:
            d = tmp_path / run_id
            (d / "output" / ds).mkdir(parents=True)
            (d / "run_info.json").write_text(
                json.dumps({"run_id": run_id, "dataset_name": ds})
            )

        client.post("/api/runs/run-a/archive")

        resp = client.get("/api/runs?include_archived=true")
        assert resp.status_code == 200
        run_ids = [r["run_id"] for r in resp.json()]
        assert "run-a" in run_ids
        assert "run-b" in run_ids
        run_state._runs.clear()


# ---------------------------------------------------------------------------
# Task 4: DELETE /runs/{run_id}
# ---------------------------------------------------------------------------

class TestDeleteRun:
    def _setup(self, tmp_path, run_id="run-del-test"):
        run_state._runs.clear()
        app = create_app(output_dir=tmp_path)
        d = tmp_path / run_id
        (d / "output" / "ds").mkdir(parents=True)
        (d / "run_info.json").write_text(
            json.dumps({"run_id": run_id, "dataset_name": "ds"})
        )
        return TestClient(app), run_id, d

    def test_delete_run_removes_directory(self, tmp_path):
        client, run_id, run_dir = self._setup(tmp_path)
        assert run_dir.exists()
        resp = client.delete(
            f"/api/runs/{run_id}",
            headers={"X-Confirm-Delete": "true"},
        )
        assert resp.status_code == 204
        assert not run_dir.exists()
        run_state._runs.clear()

    def test_delete_run_requires_confirmation_header(self, tmp_path):
        client, run_id, run_dir = self._setup(tmp_path)
        resp = client.delete(f"/api/runs/{run_id}")
        assert resp.status_code == 400
        assert run_dir.exists()  # directory not removed
        run_state._runs.clear()

    def test_delete_run_404_for_unknown(self, tmp_path):
        run_state._runs.clear()
        app = create_app(output_dir=tmp_path)
        client = TestClient(app)
        resp = client.delete(
            "/api/runs/ghost-run-abc",
            headers={"X-Confirm-Delete": "true"},
        )
        assert resp.status_code == 404
        run_state._runs.clear()

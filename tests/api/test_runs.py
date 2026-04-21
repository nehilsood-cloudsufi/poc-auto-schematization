"""Tests for pipeline runs endpoints."""
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.services import run_state


@pytest.fixture
def client(tmp_path):
    run_state._runs.clear()
    app = create_app(output_dir=tmp_path)
    yield TestClient(app)
    run_state._runs.clear()


class TestListRuns:
    def test_list_empty(self, client):
        response = client.get("/api/runs")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_with_active_run(self, client):
        run_state.create_run("r1", "ds1", "/tmp/r1", {"model": "test"})
        response = client.get("/api/runs")
        data = response.json()
        assert len(data) >= 1
        assert any(r["run_id"] == "r1" for r in data)


class TestGetRun:
    def test_get_existing_run(self, client):
        run_state.create_run("r1", "ds1", "/tmp/r1", {"model": "test"})
        response = client.get("/api/runs/r1")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "r1"
        assert data["status"] == "pending"

    def test_get_missing_run(self, client):
        response = client.get("/api/runs/nonexistent")
        assert response.status_code == 404


class TestGetHistoricalRun:
    def test_get_historical_run_from_disk(self, tmp_path):
        """GET /api/runs/{id} loads a historical run from disk when not in memory."""
        run_state._runs.clear()
        app = create_app(output_dir=tmp_path)
        client = TestClient(app)

        # Create on-disk structure without registering in memory
        run_dir = tmp_path / "hist123"
        (run_dir / "output" / "old_dataset").mkdir(parents=True)

        response = client.get("/api/runs/hist123")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "hist123"
        assert data["dataset_name"] == "old_dataset"
        assert data["status"] == "complete"

    def test_get_historical_run_not_on_disk(self, tmp_path):
        """GET /api/runs/{id} returns 404 when run doesn't exist in memory or on disk."""
        run_state._runs.clear()
        app = create_app(output_dir=tmp_path)
        client = TestClient(app)

        response = client.get("/api/runs/ghost_run")
        assert response.status_code == 404


class TestStartRun:
    def test_start_run_missing_run_id(self, client):
        response = client.post("/api/runs", json={
            "run_id": "nonexistent",
            "dataset_name": "test",
        })
        assert response.status_code == 404


class TestRunOwnerAuthorization:
    """Verify that run-specific endpoints reject non-owners with 403."""

    def _create_owned_run(self, tmp_path, run_id: str, owner: str) -> str:
        run_dir = tmp_path / run_id
        (run_dir / "output" / "ds").mkdir(parents=True)
        (run_dir / "run_info.json").write_text(
            f'{{"run_id": "{run_id}", "dataset_name": "ds", "owner": "{owner}"}}'
        )
        return str(run_dir)

    def test_get_run_denies_non_owner(self, tmp_path):
        run_state._runs.clear()
        self._create_owned_run(tmp_path, "owned1", owner="someone.else@google.com")
        # TestClient hits BaseHTTPMiddleware with CLOUD_RUN=False → request.state.user_email = local-dev@localhost
        app = create_app(output_dir=tmp_path)
        client = TestClient(app)
        response = client.get("/api/runs/owned1")
        assert response.status_code == 403
        run_state._runs.clear()

    def test_patch_run_denies_non_owner(self, tmp_path):
        run_state._runs.clear()
        self._create_owned_run(tmp_path, "owned2", owner="stranger@cloudsufi.com")
        app = create_app(output_dir=tmp_path)
        client = TestClient(app)
        response = client.patch("/api/runs/owned2", json={"display_name": "x"})
        assert response.status_code == 403
        run_state._runs.clear()

    def test_delete_run_denies_non_owner(self, tmp_path):
        run_state._runs.clear()
        self._create_owned_run(tmp_path, "owned3", owner="stranger@google.com")
        app = create_app(output_dir=tmp_path)
        client = TestClient(app)
        response = client.delete("/api/runs/owned3", headers={"X-Confirm-Delete": "true"})
        assert response.status_code == 403
        # Confirm directory still exists
        assert (tmp_path / "owned3").exists()
        run_state._runs.clear()

    def test_get_legacy_run_without_owner_is_accessible(self, tmp_path):
        """Backwards-compat: runs written before the owner field existed stay readable."""
        run_state._runs.clear()
        run_dir = tmp_path / "legacy1"
        (run_dir / "output" / "ds").mkdir(parents=True)
        (run_dir / "run_info.json").write_text(
            '{"run_id": "legacy1", "dataset_name": "ds"}'
        )
        app = create_app(output_dir=tmp_path)
        client = TestClient(app)
        response = client.get("/api/runs/legacy1")
        assert response.status_code == 200
        run_state._runs.clear()

    def test_get_owned_run_returns_data_for_owner(self, tmp_path):
        """Owner (local-dev@localhost in tests) sees their own run."""
        run_state._runs.clear()
        self._create_owned_run(tmp_path, "mine1", owner="local-dev@localhost")
        app = create_app(output_dir=tmp_path)
        client = TestClient(app)
        response = client.get("/api/runs/mine1")
        assert response.status_code == 200
        assert response.json()["run_id"] == "mine1"
        run_state._runs.clear()

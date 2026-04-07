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

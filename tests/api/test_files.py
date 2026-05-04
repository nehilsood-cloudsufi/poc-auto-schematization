"""Tests for file serving and editing endpoints."""
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.services import run_state


@pytest.fixture
def client_with_run(tmp_path):
    app = create_app(output_dir=tmp_path)
    client = TestClient(app)

    run_dir = tmp_path / "run1"
    output_dir = run_dir / "output" / "test_ds"
    output_dir.mkdir(parents=True)
    (output_dir / "generated_pvmap.csv").write_text("col1,col2\nA,B\nC,D\n")
    (output_dir / "generation_notes.md").write_text("# Notes\nSome notes here.")
    (output_dir / "processed.mcf").write_text("Node: E:test\ntypeOf: schema:Thing")

    run = run_state.create_run("run1", "test_ds", str(run_dir), {})
    run.status = "complete"

    yield client
    run_state._runs.clear()


class TestListFiles:
    def test_list_files(self, client_with_run):
        response = client_with_run.get("/api/runs/run1/files")
        assert response.status_code == 200
        data = response.json()
        assert "generated_pvmap.csv" in data["files"]
        assert "generation_notes.md" in data["files"]

    def test_list_files_missing_run(self, client_with_run):
        response = client_with_run.get("/api/runs/nonexistent/files")
        assert response.status_code == 404


class TestGetFile:
    def test_get_csv_file(self, client_with_run):
        response = client_with_run.get("/api/runs/run1/files/generated_pvmap.csv")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "csv"
        assert len(data["rows"]) == 2
        assert data["rows"][0]["col1"] == "A"

    def test_get_text_file(self, client_with_run):
        response = client_with_run.get("/api/runs/run1/files/generation_notes.md")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "text"
        assert "# Notes" in data["content"]

    def test_get_missing_file(self, client_with_run):
        response = client_with_run.get("/api/runs/run1/files/nonexistent.csv")
        assert response.status_code == 404


class TestUpdateFile:
    def test_update_csv(self, client_with_run):
        response = client_with_run.put(
            "/api/runs/run1/files/generated_pvmap.csv",
            json={"rows": [{"col1": "X", "col2": "Y"}]},
        )
        assert response.status_code == 200
        assert response.json()["saved"] is True

        get_response = client_with_run.get("/api/runs/run1/files/generated_pvmap.csv")
        assert get_response.json()["rows"][0]["col1"] == "X"

    def test_update_text(self, client_with_run):
        response = client_with_run.put(
            "/api/runs/run1/files/processed.mcf",
            json={"content": "Node: E:updated\ntypeOf: schema:NewThing"},
        )
        assert response.status_code == 200


class TestDownload:
    def test_download_zip(self, client_with_run):
        response = client_with_run.get("/api/runs/run1/download")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert len(response.content) > 0


class TestHistoricalRunFiles:
    def test_list_files_for_historical_run(self, tmp_path):
        """File listing works for runs loaded from disk (never in memory)."""
        run_state._runs.clear()
        app = create_app(output_dir=tmp_path)
        client = TestClient(app)

        # Create on-disk structure without registering in memory
        run_dir = tmp_path / "hist_run"
        output_dir = run_dir / "output" / "hist_ds"
        output_dir.mkdir(parents=True)
        (output_dir / "generated_pvmap.csv").write_text("col1,col2\nA,B\n")

        response = client.get("/api/runs/hist_run/files")
        assert response.status_code == 200
        assert "generated_pvmap.csv" in response.json()["files"]

    def test_get_file_for_historical_run(self, tmp_path):
        """File content retrieval works for runs loaded from disk."""
        run_state._runs.clear()
        app = create_app(output_dir=tmp_path)
        client = TestClient(app)

        run_dir = tmp_path / "hist_run2"
        output_dir = run_dir / "output" / "hist_ds2"
        output_dir.mkdir(parents=True)
        (output_dir / "generated_pvmap.csv").write_text("a,b\n1,2\n")

        response = client.get("/api/runs/hist_run2/files/generated_pvmap.csv")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "csv"
        assert data["rows"][0]["a"] == "1"

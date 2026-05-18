"""Tests for revalidation endpoint."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.services import run_state


@pytest.fixture
def client_with_run(tmp_path):
    app = create_app(output_dir=tmp_path)
    client = TestClient(app)

    run_dir = tmp_path / "run1"
    input_dir = run_dir / "input"
    output_dir = run_dir / "output" / "test_ds"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    (input_dir / "input.csv").write_text("col1,col2\nA,B\n")
    (output_dir / "generated_pvmap.csv").write_text("col1,col2\nA,B\n")

    run = run_state.create_run("run1", "test_ds", str(run_dir), {})
    run.status = "complete"

    yield client
    run_state._runs.clear()


class TestRevalidate:
    @patch("src.api.routes.revalidate.revalidate_pvmap")
    def test_revalidate_success(self, mock_reval, client_with_run):
        mock_reval.return_value = {"success": True, "data_rows": 42}
        response = client_with_run.post("/api/runs/run1/revalidate")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_revalidate_missing_run(self, client_with_run):
        response = client_with_run.post("/api/runs/nonexistent/revalidate")
        assert response.status_code == 404

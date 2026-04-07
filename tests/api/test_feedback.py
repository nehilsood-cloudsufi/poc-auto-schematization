"""Tests for feedback endpoints."""
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
    (output_dir / "generated_pvmap.csv").write_text("col1,col2\nA,B\n")

    run = run_state.create_run("run1", "test_ds", str(run_dir), {})
    run.status = "complete"
    run.result = {"retry_count": 0, "exit_reason": "quality_pass", "quality_metrics": {"heuristic_score": 75.0}}

    yield client
    run_state._runs.clear()


class TestFeedback:
    def test_submit_feedback(self, client_with_run):
        response = client_with_run.post(
            "/api/runs/run1/feedback",
            json={"text": "Fix column mapping", "category": "Column mapping", "severity": 4},
        )
        assert response.status_code == 200
        data = response.json()
        assert "new_run_id" in data

    def test_submit_feedback_missing_run(self, client_with_run):
        response = client_with_run.post(
            "/api/runs/nonexistent/feedback",
            json={"text": "Fix it", "category": "Other", "severity": 3},
        )
        assert response.status_code == 404


class TestDevFeedback:
    def test_submit_dev_feedback(self, client_with_run):
        response = client_with_run.post(
            "/api/runs/run1/dev-feedback",
            json={"text": "Progress bar stuck at 60%", "category": "Bug Report"},
        )
        assert response.status_code == 200
        assert response.json()["saved"] is True

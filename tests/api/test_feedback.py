"""Tests for feedback endpoints."""
import threading

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.services import run_state


@pytest.fixture
def client_with_run(tmp_path, monkeypatch):
    # Stub pipeline + MCP so feedback submission doesn't spawn a real run.
    launched: dict = {}

    def fake_launch(config, progress_queue, run_state=None):
        launched["config"] = config
        launched["run_state"] = run_state
        # Return a dummy thread whose target is a no-op so .start() is safe.
        return threading.Thread(target=lambda: None, daemon=True)

    monkeypatch.setattr("src.api.routes.feedback.launch_pipeline", fake_launch)
    monkeypatch.setattr("src.api.routes.feedback.get_or_start_mcp", lambda port: None)
    monkeypatch.setattr("src.api.routes.feedback.get_mcp_url", lambda: None)

    app = create_app(output_dir=tmp_path)
    client = TestClient(app)
    client._launched = launched  # expose to tests

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
        # Pipeline must be launched for the new run, otherwise the UI spins forever.
        launched = client_with_run._launched
        assert launched, "launch_pipeline was not called"
        cfg = launched["config"]
        assert cfg.run_id == data["new_run_id"]
        assert cfg.skip_sampling is True
        assert cfg.skip_schema_selection is True
        assert cfg.plan_only is False
        assert cfg.human_feedback and "Fix column mapping" in cfg.human_feedback
        assert "feedback_ledger_json" in cfg.extra_state
        new_run = run_state.get_run(data["new_run_id"])
        assert new_run is not None
        assert new_run.status == "running"

    def test_submit_feedback_missing_run(self, client_with_run):
        response = client_with_run.post(
            "/api/runs/nonexistent/feedback",
            json={"text": "Fix it", "category": "Other", "severity": 3},
        )
        assert response.status_code == 404


class TestDevFeedback:
    @pytest.fixture(autouse=True)
    def _mock_sheets(self, monkeypatch):
        """Prevent tests from writing to the real Google Sheet."""
        monkeypatch.setattr(
            "src.api.routes.feedback.is_sheets_configured", lambda: False
        )

    def test_submit_dev_feedback(self, client_with_run):
        response = client_with_run.post(
            "/api/runs/run1/dev-feedback",
            json={"text": "Progress bar stuck at 60%", "category": "Bug Report"},
        )
        assert response.status_code == 200
        assert response.json()["saved"] is True

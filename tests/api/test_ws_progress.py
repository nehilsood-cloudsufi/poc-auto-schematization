"""Tests for WebSocket progress endpoint."""
import queue
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.services import run_state
from src.api.adapters.progress_plugin import ProgressEvent


@pytest.fixture
def client_with_running(tmp_path):
    app = create_app(output_dir=tmp_path)
    client = TestClient(app)

    run = run_state.create_run("run1", "test_ds", str(tmp_path / "run1"), {})
    run.status = "running"

    yield client, run
    run_state._runs.clear()


class TestWebSocketProgress:
    def test_connect_to_running(self, client_with_running):
        client, run = client_with_running

        run.progress_queue.put(ProgressEvent(
            agent_name="Sampling",
            message="Sampling completed",
        ))
        run.progress_queue.put(ProgressEvent(
            agent_name="Pipeline",
            message="Done",
            is_terminal=True,
            metadata={"result": {"validation_passed": True}},
        ))

        with client.websocket_connect("/ws/progress/run1") as ws:
            msg1 = ws.receive_json()
            assert msg1["agent"] == "Sampling"

            msg2 = ws.receive_json()
            assert msg2["type"] == "complete"

    def test_connect_to_nonexistent_run(self, client_with_running):
        client, _ = client_with_running
        # Server now accepts the WebSocket and sends an error message before closing
        with client.websocket_connect("/ws/progress/nonexistent") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "error"
            assert "not found" in msg["message"]

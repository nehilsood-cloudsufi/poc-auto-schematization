"""Tests for src.ui.services.pipeline_runner."""
import queue
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Mock streamlit before any src.ui imports
# ---------------------------------------------------------------------------
_mock_st = MagicMock()
_mock_st.session_state = {}
sys.modules.setdefault("streamlit", _mock_st)

from src.ui.services.pipeline_runner import PipelineConfig, launch_pipeline, _run_in_thread
from src.ui.adapters.progress_plugin import ProgressEvent


# ---------------------------------------------------------------------------
# PipelineConfig defaults
# ---------------------------------------------------------------------------
class TestPipelineConfigDefaults:
    """Verify PipelineConfig default values match expectations."""

    def test_required_fields(self):
        cfg = PipelineConfig(
            run_id="r1",
            dataset_name="ds",
            input_dir=Path("/in"),
            output_dir=Path("/out"),
        )
        assert cfg.run_id == "r1"
        assert cfg.dataset_name == "ds"
        assert cfg.input_dir == Path("/in")
        assert cfg.output_dir == Path("/out")

    def test_default_model(self):
        cfg = PipelineConfig(
            run_id="r1", dataset_name="ds",
            input_dir=Path("/in"), output_dir=Path("/out"),
        )
        assert cfg.model == "gemini-3.1-pro-preview"

    def test_default_booleans(self):
        cfg = PipelineConfig(
            run_id="r1", dataset_name="ds",
            input_dir=Path("/in"), output_dir=Path("/out"),
        )
        assert cfg.enable_mcp is True
        assert cfg.skip_sampling is False
        assert cfg.force_resample is False
        assert cfg.skip_schema_selection is False
        assert cfg.skip_evaluation is True
        assert cfg.use_metadata is False
        assert cfg.use_schema_examples is True

    def test_default_optional_fields(self):
        cfg = PipelineConfig(
            run_id="r1", dataset_name="ds",
            input_dir=Path("/in"), output_dir=Path("/out"),
        )
        assert cfg.input_file is None
        assert cfg.mcp_url is None
        assert cfg.metadata_file_path is None
        assert cfg.human_feedback is None
        assert cfg.thinking_level is None

    def test_default_numeric_fields(self):
        cfg = PipelineConfig(
            run_id="r1", dataset_name="ds",
            input_dir=Path("/in"), output_dir=Path("/out"),
        )
        assert cfg.min_attempts == 2  # MIN_PIPELINE_ATTEMPTS
        assert cfg.max_retries == 1

    def test_extra_state_default_is_empty_dict(self):
        cfg = PipelineConfig(
            run_id="r1", dataset_name="ds",
            input_dir=Path("/in"), output_dir=Path("/out"),
        )
        assert cfg.extra_state == {}

    def test_no_prompt_version_field(self):
        """prompt_version has been removed."""
        cfg = PipelineConfig(
            run_id="r1", dataset_name="ds",
            input_dir=Path("/in"), output_dir=Path("/out"),
        )
        assert not hasattr(cfg, "prompt_version")


# ---------------------------------------------------------------------------
# launch_pipeline
# ---------------------------------------------------------------------------
class TestLaunchPipeline:
    """Verify launch_pipeline creates and starts a daemon thread."""

    @patch("src.ui.services.pipeline_runner._run_in_thread")
    def test_returns_started_daemon_thread(self, mock_run):
        cfg = PipelineConfig(
            run_id="test-run", dataset_name="ds",
            input_dir=Path("/in"), output_dir=Path("/out"),
        )
        q = queue.Queue()
        thread = launch_pipeline(cfg, q)
        assert isinstance(thread, threading.Thread)
        assert thread.daemon is True
        assert thread.name == "pipeline-test-run"
        thread.join(timeout=2)

    @patch("src.ui.services.pipeline_runner._run_in_thread")
    def test_thread_receives_config_and_queue(self, mock_run):
        cfg = PipelineConfig(
            run_id="r2", dataset_name="ds",
            input_dir=Path("/in"), output_dir=Path("/out"),
        )
        q = queue.Queue()
        thread = launch_pipeline(cfg, q)
        thread.join(timeout=2)
        mock_run.assert_called_once_with(cfg, q)


# ---------------------------------------------------------------------------
# _run_in_thread — success path
# ---------------------------------------------------------------------------
class TestRunInThreadSuccess:

    @patch("src.ui.services.pipeline_runner.ProgressTrackingPlugin")
    def test_pushes_terminal_event_on_success(self, mock_plugin_cls):
        mock_plugin_cls.return_value = MagicMock()
        fake_result = {"validation_passed": True, "exit_reason": "complete"}

        with patch.dict(sys.modules, {
            "src.pipeline.validation.log_filter": MagicMock(),
            "src.run_pipeline": MagicMock(run_dataset_pipeline=MagicMock(return_value=fake_result)),
        }):
            # Re-import to pick up patched modules
            from importlib import reload
            import src.ui.services.pipeline_runner as pr_mod
            reload(pr_mod)

            cfg = pr_mod.PipelineConfig(
                run_id="ok", dataset_name="ds",
                input_dir=Path("/in"), output_dir=Path("/out"),
            )
            q = queue.Queue()
            pr_mod._run_in_thread(cfg, q)

            event = q.get_nowait()
            assert event.is_terminal is True
            assert event.is_error is False
            assert "result" in event.metadata


# ---------------------------------------------------------------------------
# _run_in_thread — error path
# ---------------------------------------------------------------------------
class TestRunInThreadError:

    def test_pushes_error_event_on_exception(self):
        with patch.dict(sys.modules, {
            "src.pipeline.validation.log_filter": MagicMock(),
            "src.run_pipeline": MagicMock(
                run_dataset_pipeline=MagicMock(side_effect=RuntimeError("boom")),
            ),
        }):
            from importlib import reload
            import src.ui.services.pipeline_runner as pr_mod
            reload(pr_mod)

            cfg = pr_mod.PipelineConfig(
                run_id="err", dataset_name="ds",
                input_dir=Path("/in"), output_dir=Path("/out"),
            )
            q = queue.Queue()
            pr_mod._run_in_thread(cfg, q)

            event = q.get_nowait()
            assert event.is_terminal is True
            assert event.is_error is True
            assert "boom" in event.message
            assert "traceback" in event.metadata

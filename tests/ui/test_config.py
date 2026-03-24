"""Tests for src.ui.config."""
import json
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Mock streamlit before any src.ui imports
_mock_st = MagicMock()
_mock_st.session_state = {}
sys.modules.setdefault("streamlit", _mock_st)

from src.ui.config import (
    DEFAULT_MODEL,
    MCP_DEFAULT_PORT,
    MIN_PIPELINE_ATTEMPTS,
    DEFAULT_MAX_RETRIES,
    UI_OUTPUT_DIR,
    SUPPORTED_UPLOAD_TYPES,
    PHASE_LABELS,
    CloudRunFormatter,
    setup_ui_logging,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
class TestConstants:

    def test_default_model(self):
        assert DEFAULT_MODEL == "gemini-3.1-pro-preview"

    def test_mcp_port(self):
        assert MCP_DEFAULT_PORT == 3000

    def test_min_attempts(self):
        assert MIN_PIPELINE_ATTEMPTS == 2

    def test_default_max_retries(self):
        assert DEFAULT_MAX_RETRIES == 1

    def test_ui_output_dir_is_path(self):
        assert isinstance(UI_OUTPUT_DIR, Path)

    def test_supported_upload_types(self):
        assert "csv" in SUPPORTED_UPLOAD_TYPES

    def test_phase_labels_keys(self):
        expected_keys = {
            "StatePrep", "Sampling", "SchemaSelection", "SchemaSelectionAgent",
            "StatVarDiscovery", "Generator", "MetadataGenerator", "Validator",
            "MCPSpotCheck", "MCPErrorResolver", "QualityEvaluator",
            "UnifiedFeedback", "MaxRetriesCheck", "Evaluation",
        }
        assert set(PHASE_LABELS.keys()) == expected_keys

    def test_phase_labels_values_are_strings(self):
        for v in PHASE_LABELS.values():
            assert isinstance(v, str)
            assert len(v) > 0


# ---------------------------------------------------------------------------
# CloudRunFormatter
# ---------------------------------------------------------------------------
class TestCloudRunFormatter:

    def test_formats_as_json(self):
        formatter = CloudRunFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello world", args=(), exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["severity"] == "INFO"
        assert data["message"] == "hello world"

    def test_includes_extra_fields(self):
        formatter = CloudRunFormatter()
        record = logging.LogRecord(
            name="test", level=logging.WARNING, pathname="", lineno=0,
            msg="msg", args=(), exc_info=None,
        )
        record.run_id = "r1"
        record.dataset_name = "ds"
        output = formatter.format(record)
        data = json.loads(output)
        assert data["run_id"] == "r1"
        assert data["dataset_name"] == "ds"

    def test_includes_exception(self):
        formatter = CloudRunFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="", lineno=0,
            msg="fail", args=(), exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "exception" in data
        assert "ValueError" in data["exception"]


# ---------------------------------------------------------------------------
# setup_ui_logging
# ---------------------------------------------------------------------------
class TestSetupUiLogging:

    def test_creates_log_file(self, tmp_path):
        # Clear any existing handlers on the src.ui logger
        ui_logger = logging.getLogger("src.ui")
        ui_logger.handlers.clear()

        result = setup_ui_logging(tmp_path)
        assert result.name == "src.ui"
        assert (tmp_path / "logs" / "ui.log").exists()
        # Cleanup
        for h in list(result.handlers):
            h.close()
            result.removeHandler(h)

    def test_idempotent(self, tmp_path):
        ui_logger = logging.getLogger("src.ui")
        ui_logger.handlers.clear()

        logger1 = setup_ui_logging(tmp_path)
        handler_count = len(logger1.handlers)
        logger2 = setup_ui_logging(tmp_path)
        assert len(logger2.handlers) == handler_count
        # Cleanup
        for h in list(logger2.handlers):
            h.close()
            logger2.removeHandler(h)

    def test_debug_level(self, tmp_path):
        ui_logger = logging.getLogger("src.ui")
        ui_logger.handlers.clear()

        result = setup_ui_logging(tmp_path)
        assert result.level == logging.DEBUG
        # Cleanup
        for h in list(result.handlers):
            h.close()
            result.removeHandler(h)

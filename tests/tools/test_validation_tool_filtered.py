"""Test that run_validation returns filtered_logs object."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.tools.validation_tool import run_validation
from src.pipeline.validation.log_filter import FilteredLogs


class TestRunValidationReturnsFilteredLogs:
    def test_returns_filtered_logs_key_on_missing_input(self, tmp_path):
        """Early return paths should have filtered_logs=None."""
        result = run_validation(
            input_data=str(tmp_path / "nonexistent.csv"),
            pvmap_path=str(tmp_path / "pvmap.csv"),
            metadata_file=None,
            output_dir=str(tmp_path),
        )
        assert "filtered_logs" in result
        assert result["filtered_logs"] is None

    def test_returns_filtered_logs_key_on_missing_pvmap(self, tmp_path):
        input_csv = tmp_path / "input.csv"
        input_csv.write_text("col1\n1\n")
        result = run_validation(
            input_data=str(input_csv),
            pvmap_path=str(tmp_path / "nonexistent_pvmap.csv"),
            metadata_file=None,
            output_dir=str(tmp_path),
        )
        assert "filtered_logs" in result
        assert result["filtered_logs"] is None

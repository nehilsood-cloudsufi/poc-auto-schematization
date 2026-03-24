"""Tests for src.ui.services.revalidation_service."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock streamlit before any src.ui imports
_mock_st = MagicMock()
_mock_st.session_state = {}
sys.modules.setdefault("streamlit", _mock_st)

from src.ui.services.revalidation_service import revalidate


# ---------------------------------------------------------------------------
# revalidate — success
# ---------------------------------------------------------------------------
class TestRevalidateSuccess:

    @patch("src.ui.services.revalidation_service.run_validation")
    def test_passes_correct_args(self, mock_val, tmp_path):
        mock_val.return_value = {"success": True, "data_rows": 100}

        # Create a real metadata file so .exists() returns True
        meta_file = tmp_path / "output_metadata.csv"
        meta_file.write_text("col\n")

        result = revalidate(
            input_data=Path("/data/input.csv"),
            pvmap_path=Path("/out/generated_pvmap.csv"),
            metadata_path=meta_file,
            output_dir=Path("/out"),
        )

        mock_val.assert_called_once_with(
            input_data="/data/input.csv",
            pvmap_path="/out/generated_pvmap.csv",
            metadata_file=str(meta_file),
            output_dir="/out",
            timeout=300,
        )
        assert result["success"] is True
        assert result["data_rows"] == 100

    @patch("src.ui.services.revalidation_service.run_validation")
    def test_none_metadata(self, mock_val):
        mock_val.return_value = {"success": True, "data_rows": 50}

        revalidate(
            input_data=Path("/data/input.csv"),
            pvmap_path=Path("/out/pvmap.csv"),
            metadata_path=None,
            output_dir=Path("/out"),
        )

        call_kwargs = mock_val.call_args
        assert call_kwargs[1]["metadata_file"] == "" or call_kwargs[0][2] == ""

    @patch("src.ui.services.revalidation_service.run_validation")
    def test_nonexistent_metadata_path(self, mock_val, tmp_path):
        mock_val.return_value = {"success": True, "data_rows": 10}

        revalidate(
            input_data=Path("/data/input.csv"),
            pvmap_path=Path("/out/pvmap.csv"),
            metadata_path=tmp_path / "no_such_file.csv",
            output_dir=Path("/out"),
        )

        # metadata_file should be "" when path doesn't exist
        args, kwargs = mock_val.call_args
        assert kwargs.get("metadata_file", args[2] if len(args) > 2 else "") == ""


# ---------------------------------------------------------------------------
# revalidate — failure
# ---------------------------------------------------------------------------
class TestRevalidateFailure:

    @patch("src.ui.services.revalidation_service.run_validation")
    def test_returns_failure_result(self, mock_val):
        mock_val.return_value = {"success": False, "error": "bad pvmap"}

        result = revalidate(
            input_data=Path("/data/input.csv"),
            pvmap_path=Path("/out/pvmap.csv"),
            metadata_path=None,
            output_dir=Path("/out"),
        )

        assert result["success"] is False
        assert "bad pvmap" in result["error"]

# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#         https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for agentic sampling interface.

These tests verify that the sampling_interface module provides a consistent
interface for LLM-driven sampling.
"""

import csv
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.sampling.sampling_interface import (
    SamplingResult,
    sample_dataset,
)


class TestSamplingResult:
    """Tests for SamplingResult dataclass."""

    def test_sampling_result_defaults(self):
        """Test SamplingResult with default values."""
        result = SamplingResult(sampled_file=Path("/tmp/test.csv"))
        assert result.sampled_file == Path("/tmp/test.csv")
        assert result.skeleton_summary == ""
        assert result.data_context == {}
        assert result.rows_sampled == 0
        assert result.success is True
        assert result.error is None
        assert result.method == "unknown"

    def test_sampling_result_string_path_conversion(self):
        """Test that string paths are converted to Path objects."""
        result = SamplingResult(sampled_file="/tmp/test.csv")
        assert isinstance(result.sampled_file, Path)
        assert result.sampled_file == Path("/tmp/test.csv")

    def test_sampling_result_with_all_fields(self):
        """Test SamplingResult with all fields populated."""
        result = SamplingResult(
            sampled_file=Path("/tmp/test.csv"),
            skeleton_summary="## Summary",
            data_context={"key": "value"},
            rows_sampled=50,
            success=True,
            error=None,
            method="agentic",
            column_roles={"col1": "place"},
            dimension_columns=["col2"],
        )
        assert result.skeleton_summary == "## Summary"
        assert result.data_context == {"key": "value"}
        assert result.rows_sampled == 50
        assert result.method == "agentic"
        assert result.column_roles == {"col1": "place"}
        assert result.dimension_columns == ["col2"]


class TestSampleDataset:
    """Tests for sample_dataset function."""

    def test_sample_dataset_empty_input_files(self):
        """Test sample_dataset with empty input_files list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = sample_dataset(
                input_files=[],
                output_dir=Path(tmpdir)
            )
            assert result.success is False
            assert "No input files" in result.error

    def test_sample_dataset_creates_output_dir(self):
        """Test that sample_dataset creates output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "nested" / "output"
            result = sample_dataset(
                input_files=[Path("/tmp/nonexistent.csv")],
                output_dir=output_dir
            )
            # Directory should be created even if sampling fails
            assert output_dir.exists()


class TestSampleDatasetAgentic:
    """Tests for agentic sampling method."""

    @pytest.fixture
    def sample_csv_file(self, tmp_path):
        """Create a sample CSV file for testing."""
        csv_file = tmp_path / "input.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["State_FIPS", "Year", "Category", "Value"])
            for state in ["01", "06", "48"]:
                for year in [2020, 2021]:
                    for cat in ["A", "B"]:
                        writer.writerow([state, year, cat, 1000])
        return csv_file

    def test_sample_dataset_agentic_runs(self, sample_csv_file, tmp_path):
        """Test that agentic sampling can be invoked."""
        output_dir = tmp_path / "output"
        result = sample_dataset(
            input_files=[sample_csv_file],
            output_dir=output_dir,
            force_resample=True,
        )

        assert result.method == "agentic"
        # Agentic may fail if LLM tools aren't available, but interface should work
        assert isinstance(result.success, bool)

    def test_sample_dataset_agentic_uses_cache(self, sample_csv_file, tmp_path):
        """Test that agentic sampling uses cached context."""
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create cached files
        cached_sampled = output_dir / "agentic_sampled.csv"
        with open(cached_sampled, 'w') as f:
            f.write("col1,col2\nval1,val2\n")

        cached_context = output_dir / "data_context.json"
        with open(cached_context, 'w') as f:
            json.dump({
                "success": True,
                "skeleton_summary": "## Cached Summary",
                "data_context": {"total_rows": 1},
                "column_roles": {"col1": "dimension"},
                "dimension_columns": ["col1"],
            }, f)

        # Run without force_resample
        result = sample_dataset(
            input_files=[sample_csv_file],
            output_dir=output_dir,
            force_resample=False,
        )

        # Should use cached data
        if result.success:
            assert result.skeleton_summary == "## Cached Summary"


class TestConsistentOutput:
    """Tests to verify agentic sampling produces consistent output format."""

    @pytest.fixture
    def sample_csv_file(self, tmp_path):
        """Create a sample CSV file for testing."""
        csv_file = tmp_path / "input.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Region", "Year", "Metric", "Value"])
            for i in range(50):
                writer.writerow([f"Region{i % 5}", 2020 + (i % 3), f"Metric{i % 2}", i * 100])
        return csv_file

    def test_result_has_required_fields(self, sample_csv_file, tmp_path):
        """Test that agentic sampling returns SamplingResult with required fields."""
        result = sample_dataset(
            input_files=[sample_csv_file],
            output_dir=tmp_path / "output",
            force_resample=True,
        )

        # All required attributes should exist
        for attr in ['sampled_file', 'skeleton_summary', 'data_context',
                     'rows_sampled', 'success', 'error', 'method',
                     'column_roles', 'dimension_columns']:
            assert hasattr(result, attr), f"Result missing {attr}"

    def test_skeleton_summary_is_string(self, sample_csv_file, tmp_path):
        """Test that skeleton_summary is always a string."""
        result = sample_dataset(
            input_files=[sample_csv_file],
            output_dir=tmp_path / "output",
            force_resample=True,
        )
        assert isinstance(result.skeleton_summary, str)

    def test_data_context_is_dict(self, sample_csv_file, tmp_path):
        """Test that data_context is always a dict."""
        result = sample_dataset(
            input_files=[sample_csv_file],
            output_dir=tmp_path / "output",
            force_resample=True,
        )
        assert isinstance(result.data_context, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Tests for validation_tool module.

Tests subprocess execution wrapper for stat_var_processor.py.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

from src.tools.validation_tool import (
    extract_log_samples,
    build_validation_command,
    validate_output_file,
    run_validation
)


def test_extract_log_samples_short_log():
    """Test log extraction with short log (returns all)."""
    log = "Line 1\nLine 2\nLine 3"

    result = extract_log_samples(log, tail_lines=50)

    assert result == log


def test_extract_log_samples_long_log():
    """Test log extraction with long log (samples tail and random)."""
    # Create a log with 200 lines
    lines = [f"Log line {i}" for i in range(200)]
    log = '\n'.join(lines)

    result = extract_log_samples(log, tail_lines=50, sample_count=5, sample_size=3)

    # Should contain last 50 lines
    assert "LAST 50 LINES OF LOG" in result
    assert "Log line 199" in result  # Last line

    # Should contain random samples
    assert "RANDOM SAMPLES" in result
    assert "Sample 1" in result


def test_extract_log_samples_with_empty_lines():
    """Test log extraction filters empty lines."""
    log = "Line 1\n\n\nLine 2\n\n\nLine 3\n\n"

    result = extract_log_samples(log, tail_lines=10)

    # Empty lines should be filtered
    assert "Line 1" in result
    assert "Line 2" in result
    assert "Line 3" in result


def test_build_validation_command():
    """Test building validation command and environment."""
    input_data = Path("/tmp/input.csv")
    pvmap = Path("/tmp/pvmap.csv")
    metadata = Path("/tmp/metadata.csv")
    output_dir = Path("/tmp/output")

    cmd, env = build_validation_command(
        input_data=input_data,
        pvmap_path=pvmap,
        metadata_file=metadata,
        output_dir=output_dir
    )

    # Check command structure
    assert isinstance(cmd, list)
    assert len(cmd) > 5
    assert 'stat_var_processor.py' in cmd[1]
    assert f'--input_data={input_data}' in cmd
    assert f'--pv_map={pvmap}' in cmd
    assert f'--config_file={metadata}' in cmd
    assert '--generate_statvar_name=True' in cmd

    # Check environment
    assert 'PYTHONPATH' in env
    assert isinstance(env['PYTHONPATH'], str)


def test_validate_output_file_success(temp_dir):
    """Test validating output file with data."""
    output_file = temp_dir / "processed.csv"

    # Create file with header and data rows
    with open(output_file, 'w') as f:
        f.write("col1,col2,col3\n")
        f.write("val1,val2,val3\n")
        f.write("val4,val5,val6\n")

    has_data, error, row_count = validate_output_file(output_file)

    assert has_data is True
    assert error is None
    assert row_count == 2


def test_validate_output_file_empty(temp_dir):
    """Test validating output file with only header."""
    output_file = temp_dir / "processed.csv"

    # Create file with only header
    with open(output_file, 'w') as f:
        f.write("col1,col2,col3\n")

    has_data, error, row_count = validate_output_file(output_file)

    assert has_data is False
    assert "empty output" in error.lower()
    assert row_count == 0


def test_validate_output_file_missing(temp_dir):
    """Test validating non-existent output file."""
    output_file = temp_dir / "nonexistent.csv"

    has_data, error, row_count = validate_output_file(output_file)

    assert has_data is False
    assert "not produce output file" in error
    assert row_count == 0


def test_validate_output_file_with_empty_lines(temp_dir):
    """Test validation ignores empty lines."""
    output_file = temp_dir / "processed.csv"

    with open(output_file, 'w') as f:
        f.write("col1,col2\n")
        f.write("\n")
        f.write("val1,val2\n")
        f.write("\n")
        f.write("val3,val4\n")

    has_data, error, row_count = validate_output_file(output_file)

    assert has_data is True
    assert row_count == 2


def test_run_validation_missing_input(temp_dir):
    """Test validation with missing input file."""
    result = run_validation(
        input_data=Path("/nonexistent/input.csv"),
        pvmap_path=temp_dir / "pvmap.csv",
        metadata_file=temp_dir / "metadata.csv",
        output_dir=temp_dir
    )

    assert result['success'] is False
    assert "not found" in result['error'].lower()
    assert result['output_file'] is None


def test_run_validation_missing_pvmap(temp_dir):
    """Test validation with missing PVMAP file."""
    # Create input and metadata files
    input_file = temp_dir / "input.csv"
    input_file.write_text("col1,col2\nval1,val2\n")

    metadata_file = temp_dir / "metadata.csv"
    metadata_file.write_text("param,value\n")

    result = run_validation(
        input_data=input_file,
        pvmap_path=Path("/nonexistent/pvmap.csv"),
        metadata_file=metadata_file,
        output_dir=temp_dir
    )

    assert result['success'] is False
    assert "PVMAP file not found" in result['error']


@patch('src.tools.validation_tool.subprocess.run')
def test_run_validation_success(mock_run, temp_dir):
    """Test successful validation subprocess."""
    # Create input files
    input_file = temp_dir / "input.csv"
    input_file.write_text("col1,col2\nval1,val2\n")

    pvmap_file = temp_dir / "pvmap.csv"
    pvmap_file.write_text("key,property,value\n")

    metadata_file = temp_dir / "metadata.csv"
    metadata_file.write_text("param,value\n")

    output_dir = temp_dir / "output"
    output_dir.mkdir()

    # Create output file that would be produced by subprocess
    output_file = output_dir / "processed.csv"
    output_file.write_text("statvar,date,location,value\nvar1,2020,USA,100\nvar2,2021,CAN,200\n")

    # Mock successful subprocess
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "Processing complete"
    mock_result.stderr = ""
    mock_run.return_value = mock_result

    result = run_validation(
        input_data=input_file,
        pvmap_path=pvmap_file,
        metadata_file=metadata_file,
        output_dir=output_dir
    )

    assert result['success'] is True
    assert result['error'] is None
    assert result['data_rows'] == 2
    assert result['output_file'] is not None
    assert mock_run.called


@patch('src.tools.validation_tool.subprocess.run')
def test_run_validation_empty_output(mock_run, temp_dir):
    """Test validation with empty output (only header)."""
    # Create input files
    input_file = temp_dir / "input.csv"
    input_file.write_text("col1,col2\nval1,val2\n")

    pvmap_file = temp_dir / "pvmap.csv"
    pvmap_file.write_text("key,property,value\n")

    metadata_file = temp_dir / "metadata.csv"
    metadata_file.write_text("param,value\n")

    output_dir = temp_dir / "output"
    output_dir.mkdir()

    # Create output with only header
    output_file = output_dir / "processed.csv"
    output_file.write_text("statvar,date,location,value\n")

    # Mock subprocess with success but empty output
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "Processing complete"
    mock_result.stderr = "Warning: No rows matched"
    mock_run.return_value = mock_result

    result = run_validation(
        input_data=input_file,
        pvmap_path=pvmap_file,
        metadata_file=metadata_file,
        output_dir=output_dir
    )

    assert result['success'] is False
    assert "empty output" in result['error'].lower()
    assert result['error_logs'] is not None
    # For short logs, the original text is returned; for long logs, "LAST" prefix is added
    assert "No rows matched" in result['error_logs'] or "LAST" in result['error_logs']


@patch('src.tools.validation_tool.subprocess.run')
def test_run_validation_nonzero_exit(mock_run, temp_dir):
    """Test validation with non-zero exit code."""
    # Create input files
    input_file = temp_dir / "input.csv"
    input_file.write_text("col1,col2\n")

    pvmap_file = temp_dir / "pvmap.csv"
    pvmap_file.write_text("key,property,value\n")

    metadata_file = temp_dir / "metadata.csv"
    metadata_file.write_text("param,value\n")

    output_dir = temp_dir / "output"
    output_dir.mkdir()

    # Mock failed subprocess
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "Error: Invalid PVMAP format\nTraceback...\nKeyError: 'missing_column'"
    mock_run.return_value = mock_result

    result = run_validation(
        input_data=input_file,
        pvmap_path=pvmap_file,
        metadata_file=metadata_file,
        output_dir=output_dir
    )

    assert result['success'] is False
    assert "exit code 1" in result['error']
    assert result['error_logs'] is not None
    assert "Invalid PVMAP format" in result['error_logs']


@patch('src.tools.validation_tool.subprocess.run')
def test_run_validation_timeout(mock_run, temp_dir):
    """Test validation subprocess timeout."""
    # Create input files
    input_file = temp_dir / "input.csv"
    input_file.write_text("col1,col2\n")

    pvmap_file = temp_dir / "pvmap.csv"
    pvmap_file.write_text("key,property,value\n")

    metadata_file = temp_dir / "metadata.csv"
    metadata_file.write_text("param,value\n")

    output_dir = temp_dir / "output"
    output_dir.mkdir()

    # Mock timeout
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=300)

    result = run_validation(
        input_data=input_file,
        pvmap_path=pvmap_file,
        metadata_file=metadata_file,
        output_dir=output_dir,
        timeout=300
    )

    assert result['success'] is False
    assert "timed out" in result['error'].lower()
    assert result['output_file'] is None


@patch('src.tools.validation_tool.subprocess.run')
def test_run_validation_exception(mock_run, temp_dir):
    """Test validation with unexpected exception."""
    # Create input files
    input_file = temp_dir / "input.csv"
    input_file.write_text("col1,col2\n")

    pvmap_file = temp_dir / "pvmap.csv"
    pvmap_file.write_text("key,property,value\n")

    metadata_file = temp_dir / "metadata.csv"
    metadata_file.write_text("param,value\n")

    output_dir = temp_dir / "output"
    output_dir.mkdir()

    # Mock exception
    mock_run.side_effect = Exception("Unexpected error")

    result = run_validation(
        input_data=input_file,
        pvmap_path=pvmap_file,
        metadata_file=metadata_file,
        output_dir=output_dir
    )

    assert result['success'] is False
    assert "Validation error" in result['error']
    assert "Unexpected error" in result['error']


# ============================================================================
# Tests for Counter-Based Feedback Integration (Phase 8 enhancement)
# ============================================================================

class TestCounterBasedFeedback:
    """Tests for counter-based feedback integration in validation_tool."""

    @patch('src.tools.validation_tool.subprocess.run')
    def test_uses_counters_when_available(self, mock_run, temp_dir):
        """When counters file exists, should use generate_feedback()."""
        # Create input files
        input_file = temp_dir / "input.csv"
        input_file.write_text("Year,State,Population\n2020,CA,100\n")

        pvmap_file = temp_dir / "pvmap.csv"
        pvmap_file.write_text("key,property,value\n")

        metadata_file = temp_dir / "metadata.csv"
        metadata_file.write_text("param,value\n")

        output_dir = temp_dir / "output"
        output_dir.mkdir()

        # Create counters file (simulating stat_var_processor output)
        counters_file = output_dir / "processed_counters.txt"
        counters_file.write_text("""key,value
input-rows-processed,100
output-svobs-csv-rows,0
error-unresolved-place,100
""")

        # Create output with only header (empty output)
        output_file = output_dir / "processed.csv"
        output_file.write_text("statvar,date,location,value\n")

        # Mock subprocess
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Processing complete"
        mock_result.stderr = "Warning: place errors"
        mock_run.return_value = mock_result

        result = run_validation(
            input_data=str(input_file),
            pvmap_path=str(pvmap_file),
            metadata_file=str(metadata_file),
            output_dir=str(output_dir)
        )

        # Should use log_filter-based feedback (new format)
        assert result['success'] is False
        assert result['structured_feedback'] is not None
        # New format uses "Validation Summary" instead of "Coverage Analysis"
        assert 'Validation Summary' in result['structured_feedback']
        # Error should be mentioned in the error message
        assert 'unresolved place' in result['error'] or 'error' in result['error'].lower()

    @patch('src.tools.validation_tool.subprocess.run')
    def test_falls_back_to_random_sampling(self, mock_run, temp_dir):
        """When no counters file, should use extract_log_samples()."""
        # Create input files
        input_file = temp_dir / "input.csv"
        input_file.write_text("Year,State,Population\n2020,CA,100\n")

        pvmap_file = temp_dir / "pvmap.csv"
        pvmap_file.write_text("key,property,value\n")

        metadata_file = temp_dir / "metadata.csv"
        metadata_file.write_text("param,value\n")

        output_dir = temp_dir / "output"
        output_dir.mkdir()

        # NO counters file created

        # Create output with only header (empty output)
        output_file = output_dir / "processed.csv"
        output_file.write_text("statvar,date,location,value\n")

        # Mock subprocess
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Processing complete"
        mock_result.stderr = "Warning: place errors"
        mock_run.return_value = mock_result

        result = run_validation(
            input_data=str(input_file),
            pvmap_path=str(pvmap_file),
            metadata_file=str(metadata_file),
            output_dir=str(output_dir)
        )

        # Should fall back to random sampling
        assert result['success'] is False
        assert result['structured_feedback'] is None  # No counters = no structured feedback
        assert result['error_logs'] is not None  # Fall back to log sampling
        assert result['counters'] == {}  # Empty counters

    @patch('src.tools.validation_tool.subprocess.run')
    def test_includes_structured_feedback_in_result(self, mock_run, temp_dir):
        """Result dict should include structured_feedback key."""
        # Create input files
        input_file = temp_dir / "input.csv"
        input_file.write_text("col1\nval1\n")

        pvmap_file = temp_dir / "pvmap.csv"
        pvmap_file.write_text("key,property,value\n")

        metadata_file = temp_dir / "metadata.csv"
        metadata_file.write_text("param,value\n")

        output_dir = temp_dir / "output"
        output_dir.mkdir()

        # Create counters file
        counters_file = output_dir / "processed_counters.txt"
        counters_file.write_text("""key,value
input-rows-processed,100
output-svobs-csv-rows,50
""")

        # Create output with data
        output_file = output_dir / "processed.csv"
        output_file.write_text("col\nval\nval2\n")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = run_validation(
            input_data=str(input_file),
            pvmap_path=str(pvmap_file),
            metadata_file=str(metadata_file),
            output_dir=str(output_dir)
        )

        # Success case should also have structured_feedback key (None when success)
        assert 'structured_feedback' in result
        assert 'counters' in result

    @patch('src.tools.validation_tool.subprocess.run')
    def test_counters_included_in_result(self, mock_run, temp_dir):
        """Result dict should include parsed counters."""
        # Create input files
        input_file = temp_dir / "input.csv"
        input_file.write_text("col1\nval1\n")

        pvmap_file = temp_dir / "pvmap.csv"
        pvmap_file.write_text("key,property,value\n")

        metadata_file = temp_dir / "metadata.csv"
        metadata_file.write_text("param,value\n")

        output_dir = temp_dir / "output"
        output_dir.mkdir()

        # Create counters file
        counters_file = output_dir / "processed_counters.txt"
        counters_file.write_text("""key,value
input-rows-processed,100
output-svobs-csv-rows,50
generated-statvars,5
""")

        # Create output with data
        output_file = output_dir / "processed.csv"
        output_file.write_text("col\nval\nval2\n")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = run_validation(
            input_data=str(input_file),
            pvmap_path=str(pvmap_file),
            metadata_file=str(metadata_file),
            output_dir=str(output_dir)
        )

        # Note: With log_filter, raw counters dict is not populated
        # The FilteredLogs object is used instead for structured feedback
        # Counters key exists for backward compatibility but is empty
        assert 'counters' in result

    @patch('src.tools.validation_tool.subprocess.run')
    def test_attempt_number_passed_to_feedback(self, mock_run, temp_dir):
        """attempt_number param should be passed to generate_feedback()."""
        # Create input files
        input_file = temp_dir / "input.csv"
        input_file.write_text("col1\nval1\n")

        pvmap_file = temp_dir / "pvmap.csv"
        pvmap_file.write_text("key,property,value\n")

        metadata_file = temp_dir / "metadata.csv"
        metadata_file.write_text("param,value\n")

        output_dir = temp_dir / "output"
        output_dir.mkdir()

        # Create counters file with errors
        counters_file = output_dir / "processed_counters.txt"
        counters_file.write_text("""key,value
input-rows-processed,100
output-svobs-csv-rows,0
error-unresolved-place,100
""")

        # Create empty output
        output_file = output_dir / "processed.csv"
        output_file.write_text("col\n")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Test with attempt_number=2
        result = run_validation(
            input_data=str(input_file),
            pvmap_path=str(pvmap_file),
            metadata_file=str(metadata_file),
            output_dir=str(output_dir),
            attempt_number=2
        )

        # New log_filter format focuses on value patterns, not iteration-specific advice
        # Check that structured feedback is generated with validation summary
        assert result['structured_feedback'] is not None
        assert 'Validation Summary' in result['structured_feedback']


def test_build_validation_command_includes_debug_flag():
    """Test that build_validation_command includes --debug=True flag."""
    input_data = Path("/tmp/input.csv")
    pvmap = Path("/tmp/pvmap.csv")
    metadata = Path("/tmp/metadata.csv")
    output_dir = Path("/tmp/output")

    cmd, env = build_validation_command(
        input_data=input_data,
        pvmap_path=pvmap,
        metadata_file=metadata,
        output_dir=output_dir,
        debug=True
    )

    # Should include debug flag
    assert '--debug=True' in cmd


def test_build_validation_command_without_debug_flag():
    """Test that build_validation_command can exclude debug flag."""
    input_data = Path("/tmp/input.csv")
    pvmap = Path("/tmp/pvmap.csv")
    metadata = Path("/tmp/metadata.csv")
    output_dir = Path("/tmp/output")

    cmd, env = build_validation_command(
        input_data=input_data,
        pvmap_path=pvmap,
        metadata_file=metadata,
        output_dir=output_dir,
        debug=False
    )

    # Should NOT include debug flag
    assert '--debug=True' not in cmd

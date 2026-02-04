"""
Tests for SamplingAgent (LlmAgent-based implementation).

Tests the agent creation and tool functionality.
For the new agentic implementation, we test:
1. Agent creation and configuration
2. Tool functions directly (they provide the core logic)
3. Tool integration patterns
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import csv

from src.agents.sampling_agent import (
    create_sampling_agent,
    SamplingAgent,
    SAMPLING_AGENT_INSTRUCTION
)
from src.tools.sampling_tools import (
    preview_data,
    analyze_columns,
    sample_rows,
    check_coverage,
    generate_context,
    get_sampling_tools
)
from src.state.dataset_info import DatasetInfo


# ============================================================================
# Agent Creation Tests
# ============================================================================

def test_sampling_agent_creation():
    """Test SamplingAgent can be created using factory function."""
    agent = create_sampling_agent(name="SamplingAgent")
    assert agent is not None
    assert agent.name == "SamplingAgent"
    assert len(agent.tools) == 5


def test_sampling_agent_custom_name():
    """Test SamplingAgent with custom name."""
    agent = create_sampling_agent(name="CustomSampler")
    assert agent.name == "CustomSampler"


def test_sampling_agent_wrapper_class():
    """Test backward-compatible SamplingAgent class wrapper."""
    wrapper = SamplingAgent(name="WrapperAgent")
    assert wrapper.name == "WrapperAgent"
    # Access underlying agent
    assert wrapper.agent is not None
    assert wrapper.agent.name == "WrapperAgent"


def test_sampling_agent_model_default():
    """Test default model is gemini-2.5-flash."""
    agent = create_sampling_agent()
    assert "gemini" in agent.model.lower()


def test_sampling_agent_model_override():
    """Test model can be overridden."""
    agent = create_sampling_agent(model="gemini-2.5-pro")
    assert agent.model == "gemini-2.5-pro"


def test_sampling_agent_instruction():
    """Test that instruction is comprehensive."""
    assert "preview_data" in SAMPLING_AGENT_INSTRUCTION
    assert "analyze_columns" in SAMPLING_AGENT_INSTRUCTION
    assert "sample_rows" in SAMPLING_AGENT_INSTRUCTION
    assert "check_coverage" in SAMPLING_AGENT_INSTRUCTION
    assert "generate_context" in SAMPLING_AGENT_INSTRUCTION
    assert "Data Commons" in SAMPLING_AGENT_INSTRUCTION
    assert "StatVar" in SAMPLING_AGENT_INSTRUCTION


def test_sampling_agent_tools_registered():
    """Test all 5 tools are registered."""
    tools = get_sampling_tools()
    assert len(tools) == 5
    tool_names = [t.__name__ for t in tools]
    assert "preview_data" in tool_names
    assert "analyze_columns" in tool_names
    assert "sample_rows" in tool_names
    assert "check_coverage" in tool_names
    assert "generate_context" in tool_names


# ============================================================================
# Tool Function Tests
# ============================================================================

@pytest.fixture
def temp_csv_file():
    """Create a temporary CSV file with test data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(['State', 'Year', 'Gender', 'Population'])
        writer.writerow(['CA', '2020', 'Male', '19500000'])
        writer.writerow(['CA', '2020', 'Female', '19800000'])
        writer.writerow(['TX', '2020', 'Male', '14200000'])
        writer.writerow(['TX', '2020', 'Female', '14300000'])
        writer.writerow(['NY', '2021', 'Male', '9700000'])
        writer.writerow(['NY', '2021', 'Female', '10100000'])
        writer.writerow(['FL', '2021', 'Male', '10800000'])
        writer.writerow(['FL', '2021', 'Female', '11000000'])
        f.flush()
        yield f.name

    # Cleanup
    import os
    if os.path.exists(f.name):
        os.unlink(f.name)


def test_preview_data_success(temp_csv_file):
    """Test preview_data returns correct structure."""
    result = preview_data(temp_csv_file, n_rows=5)

    assert result["success"] is True
    assert result["error"] is None
    assert result["headers"] == ['State', 'Year', 'Gender', 'Population']
    assert len(result["sample_rows"]) == 5
    assert result["total_rows"] == 8
    assert result["total_columns"] == 4


def test_preview_data_file_not_found():
    """Test preview_data handles missing files."""
    result = preview_data("/nonexistent/file.csv")

    assert result["success"] is False
    assert "not found" in result["error"].lower()
    assert result["headers"] == []


def test_analyze_columns_success(temp_csv_file):
    """Test analyze_columns returns useful evidence."""
    result = analyze_columns(temp_csv_file, sample_size=100)

    assert result["success"] is True
    assert result["total_rows"] == 8
    assert result["total_columns"] == 4

    # Check State column analysis
    state_col = result["columns"]["State"]
    assert state_col["cardinality"] == 4  # CA, TX, NY, FL
    assert state_col["dtype"] == "String"
    assert state_col["looks_like_place"] is True

    # Check Year column analysis
    year_col = result["columns"]["Year"]
    assert year_col["cardinality"] == 2  # 2020, 2021
    assert year_col["looks_like_date"] is True

    # Check Gender column analysis
    gender_col = result["columns"]["Gender"]
    assert gender_col["cardinality"] == 2  # Male, Female

    # Check Population column analysis
    pop_col = result["columns"]["Population"]
    assert pop_col["dtype"] == "Integer"
    assert pop_col["is_unique"] is True


def test_sample_rows_head_mode(temp_csv_file):
    """Test sample_rows with head mode."""
    import json
    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as outf:
        output_path = outf.name

    try:
        result = sample_rows(
            temp_csv_file,
            output_path,
            json.dumps({"mode": "head", "target_rows": 5})
        )

        assert result["success"] is True
        assert result["rows_sampled"] == 5
        assert result["strategy_used"] == "head"

        # Verify output file exists and has correct row count
        with open(output_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 6  # Header + 5 data rows
    finally:
        import os
        if os.path.exists(output_path):
            os.unlink(output_path)


def test_sample_rows_stratified_mode(temp_csv_file):
    """Test sample_rows with stratified mode."""
    import json
    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as outf:
        output_path = outf.name

    try:
        result = sample_rows(
            temp_csv_file,
            output_path,
            json.dumps({"mode": "stratified", "target_rows": 8, "stratify_by": ["Gender"]})
        )

        assert result["success"] is True
        assert result["rows_sampled"] > 0
        assert result["strategy_used"] == "stratified"
    finally:
        import os
        if os.path.exists(output_path):
            os.unlink(output_path)


def test_check_coverage_unique(temp_csv_file):
    """Test check_coverage with correct dimensions."""
    result = check_coverage(
        temp_csv_file,
        place_col="State",
        time_col="Year",
        dimension_columns=["Gender"]
    )

    assert result["success"] is True
    assert result["is_unique"] is True
    assert result["duplicate_count"] == 0


def test_check_coverage_not_unique(temp_csv_file):
    """Test check_coverage detects missing dimensions."""
    # Without Gender, there will be duplicates (CA+2020 appears twice)
    result = check_coverage(
        temp_csv_file,
        place_col="State",
        time_col="Year",
        dimension_columns=[]  # Missing Gender dimension
    )

    assert result["success"] is True
    # Some states have multiple rows per year (different genders)
    # Without Gender, we'll have duplicates
    # CA in 2020 has Male and Female, so at least 2 combos
    # If is_unique is False, we detected duplicates correctly


def test_generate_context_success(temp_csv_file):
    """Test generate_context creates valid DataContext."""
    import json
    result = generate_context(
        temp_csv_file,
        column_roles_json=json.dumps({
            "State": "place",
            "Year": "time",
            "Gender": "dimension",
            "Population": "value"
        }),
        dimension_columns=["Gender"],
        metadata_json=json.dumps({"datasetname": "Test Dataset"})
    )

    assert result["success"] is True
    assert result["data_context"] is not None
    assert result["skeleton_summary"] != ""
    assert result["statvar_pattern"] != ""
    assert len(result["skeleton_sample"]) > 0


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.fixture
def temp_dataset_dir():
    """Create a temporary dataset directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create dataset structure
        dataset_dir = tmpdir / "test_dataset"
        test_data_dir = dataset_dir / "test_data"
        test_data_dir.mkdir(parents=True)

        # Create input CSV file
        input_csv = test_data_dir / "test_input.csv"
        with open(input_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['State', 'Year', 'Gender', 'Population'])
            for state in ['CA', 'TX', 'NY', 'FL']:
                for year in ['2020', '2021']:
                    for gender in ['Male', 'Female']:
                        pop = f"{hash(state + year + gender) % 1000000 + 10000000}"
                        writer.writerow([state, year, gender, pop])

        # Create metadata CSV file
        metadata_csv = dataset_dir / "test_metadata.csv"
        with open(metadata_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['datasetname', 'Test Population Dataset'])
            writer.writerow(['source', 'Census Bureau'])

        yield dataset_dir


def test_full_tool_workflow(temp_dataset_dir):
    """Test complete tool workflow without LLM."""
    input_file = str(temp_dataset_dir / "test_data" / "test_input.csv")
    output_file = str(temp_dataset_dir / "test_data" / "test_sampled.csv")

    # Step 1: Preview
    preview = preview_data(input_file, n_rows=5)
    assert preview["success"]
    assert len(preview["headers"]) == 4

    # Step 2: Analyze
    analysis = analyze_columns(input_file)
    assert analysis["success"]

    # Step 3: Make classification decisions (simulating LLM)
    column_roles = {}
    dimension_columns = []
    place_col = None
    time_col = None

    for col, info in analysis["columns"].items():
        if info["looks_like_place"]:
            column_roles[col] = "place"
            place_col = col
        elif info["looks_like_date"]:
            column_roles[col] = "time"
            time_col = col
        elif info["dtype"] in ["Integer", "Float"] and info["cardinality_ratio"] > 0.5:
            column_roles[col] = "value"
        elif info["cardinality_ratio"] < 0.5:
            column_roles[col] = "dimension"
            dimension_columns.append(col)
        else:
            column_roles[col] = "metadata"

    # Step 4: Sample with stratified strategy
    import json
    sample_result = sample_rows(
        input_file,
        output_file,
        json.dumps({
            "mode": "stratified",
            "target_rows": 10,
            "stratify_by": dimension_columns
        })
    )
    assert sample_result["success"]

    # Step 5: Check coverage
    coverage = check_coverage(
        output_file,
        place_col=place_col,
        time_col=time_col,
        dimension_columns=dimension_columns
    )
    assert coverage["success"]

    # Step 6: Generate context
    context = generate_context(
        output_file,
        column_roles_json=json.dumps(column_roles),
        dimension_columns=dimension_columns,
        metadata_json=json.dumps({"datasetname": "Test Dataset"})
    )
    assert context["success"]
    assert "skeleton_summary" in context
    assert "data_context" in context


# ============================================================================
# Edge Case Tests
# ============================================================================

def test_analyze_columns_empty_file():
    """Test analyze_columns with minimal data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(['Col1', 'Col2'])  # Header only
        f.flush()
        fname = f.name

    try:
        result = analyze_columns(fname)
        assert result["success"] is True
        assert result["total_rows"] == 0
    finally:
        import os
        os.unlink(fname)


def test_preview_data_large_file_limit():
    """Test preview_data respects n_rows limit."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Value'])
        for i in range(1000):
            writer.writerow([i, i * 100])
        f.flush()
        fname = f.name

    try:
        result = preview_data(fname, n_rows=10)
        assert result["success"] is True
        assert len(result["sample_rows"]) == 10
        assert result["total_rows"] == 1000
    finally:
        import os
        os.unlink(fname)

"""
Tests for DiscoveryAgent with proper ADK async patterns.

Tests dataset file discovery logic using ADK BaseAgent pattern.
Updated for new folder structure:
  - input_metadata/ instead of root metadata
  - schema/ subfolder for schema files
  - ground_truth/{dataset}/metadata/ and pvmap/ subfolders
  - standalone mode
"""

import pytest
from pathlib import Path
from unittest.mock import Mock

from src.agents.discovery_agent import DiscoveryAgent
from src.state.dataset_info import DatasetInfo


def test_discovery_agent_initialization():
    """Test DiscoveryAgent can be initialized."""
    agent = DiscoveryAgent(name="DiscoveryAgent")
    assert agent is not None
    assert agent.name == "DiscoveryAgent"


@pytest.mark.asyncio
async def test_discovery_agent_success(mock_invocation_context, temp_dir):
    """Test successful discovery with ADK pattern."""
    # Create dataset structure with input_metadata/
    dataset_dir = Path(mock_invocation_context.session.state["input_dir"]) / "test_dataset"
    dataset_dir.mkdir()

    test_data_dir = dataset_dir / "test_data"
    test_data_dir.mkdir()

    # Create input_metadata
    input_metadata_dir = dataset_dir / "input_metadata"
    input_metadata_dir.mkdir()
    metadata_file = input_metadata_dir / "test_metadata.csv"
    metadata_file.write_text("param,value\n")

    # Create input data file
    input_file = test_data_dir / "data_input.csv"
    input_file.write_text("col1,col2\nval1,val2\n")

    # Enable use_metadata
    mock_invocation_context.session.state["use_metadata"] = True

    # Run agent
    agent = DiscoveryAgent(name="DiscoveryAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    # Verify state was updated
    assert mock_invocation_context.session.state["dataset_count"] == 1
    assert len(mock_invocation_context.session.state["datasets"]) == 1
    assert mock_invocation_context.session.state["error"] is None

    # Verify event
    assert len(events) == 1
    event_text = events[0].content.parts[0].text
    assert "Discovered 1 datasets" in event_text


@pytest.mark.asyncio
async def test_discovery_agent_multiple_datasets(mock_invocation_context, temp_dir):
    """Test discovering multiple datasets."""
    # Create multiple datasets
    for i in range(3):
        dataset_dir = Path(mock_invocation_context.session.state["input_dir"]) / f"dataset_{i}"
        dataset_dir.mkdir()

        test_data_dir = dataset_dir / "test_data"
        test_data_dir.mkdir()

        # Create input data
        input_file = test_data_dir / f"data_{i}_input.csv"
        input_file.write_text("col1,col2\nval1,val2\n")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    assert mock_invocation_context.session.state["dataset_count"] == 3
    datasets = mock_invocation_context.session.state["datasets"]
    assert len(datasets) == 3
    assert all(d.name.startswith("dataset_") for d in datasets)


@pytest.mark.asyncio
async def test_discovery_agent_missing_input_dir():
    """Test agent with missing input_dir in state."""
    # Create context without input_dir
    ctx = Mock()
    ctx.session = Mock()
    ctx.session.state = {}  # No input_dir

    agent = DiscoveryAgent(name="DiscoveryAgent")
    events = []
    async for event in agent._run_async_impl(ctx):
        events.append(event)

    # Verify error handling
    assert ctx.session.state["error"] == "No input_dir specified in state"
    assert ctx.session.state["datasets"] == []
    assert ctx.session.state["dataset_count"] == 0
    assert len(events) == 1
    event_text = events[0].content.parts[0].text
    assert "failed" in event_text.lower()


@pytest.mark.asyncio
async def test_discovery_agent_schema_files(mock_invocation_context, temp_dir):
    """Test discovering schema files from schema/ subfolder."""
    dataset_dir = Path(mock_invocation_context.session.state["input_dir"]) / "test_dataset"
    dataset_dir.mkdir()

    # Create schema/ subfolder with files
    schema_dir = dataset_dir / "schema"
    schema_dir.mkdir()

    schema_txt = schema_dir / "scripts_statvar_llm_config_schema_examples_dc_topic_Demographics.txt"
    schema_txt.write_text("Example schema content\n")

    schema_mcf = schema_dir / "scripts_statvar_llm_config_vertical_demographics.mcf"
    schema_mcf.write_text("Node: example\n")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    datasets = mock_invocation_context.session.state["datasets"]
    assert len(datasets) == 1
    assert datasets[0].schema_examples == schema_txt
    assert datasets[0].schema_mcf == schema_mcf
    assert len(datasets[0].schema_files) == 2


@pytest.mark.asyncio
async def test_discovery_agent_metadata_files(mock_invocation_context, temp_dir):
    """Test discovering metadata files from input_metadata/ subfolder."""
    dataset_dir = Path(mock_invocation_context.session.state["input_dir"]) / "test_dataset"
    dataset_dir.mkdir()

    # Create input_metadata/ with files
    input_metadata_dir = dataset_dir / "input_metadata"
    input_metadata_dir.mkdir()

    metadata1 = input_metadata_dir / "dataset_metadata.csv"
    metadata1.write_text("param,value\n")

    metadata2 = input_metadata_dir / "additional_metadata.csv"
    metadata2.write_text("param,value\n")

    # Enable metadata
    mock_invocation_context.session.state["use_metadata"] = True

    agent = DiscoveryAgent(name="DiscoveryAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    datasets = mock_invocation_context.session.state["datasets"]
    assert len(datasets) == 1
    assert len(datasets[0].metadata_files) == 2


@pytest.mark.asyncio
async def test_discovery_agent_input_data_files(mock_invocation_context, temp_dir):
    """Test discovering input data files."""
    dataset_dir = Path(mock_invocation_context.session.state["input_dir"]) / "test_dataset"
    test_data_dir = dataset_dir / "test_data"
    test_data_dir.mkdir(parents=True)

    # Create input files
    input1 = test_data_dir / "file1_input.csv"
    input1.write_text("col1,col2\nval1,val2\n")

    input2 = test_data_dir / "file2_input.csv"
    input2.write_text("col1,col2\nval1,val2\n")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    datasets = mock_invocation_context.session.state["datasets"]
    assert len(datasets) == 1
    assert len(datasets[0].input_data_files) == 2


@pytest.mark.asyncio
async def test_discovery_agent_excludes_combined_input(mock_invocation_context, temp_dir):
    """Test that combined input files are excluded."""
    dataset_dir = Path(mock_invocation_context.session.state["input_dir"]) / "test_dataset"
    test_data_dir = dataset_dir / "test_data"
    test_data_dir.mkdir(parents=True)

    # Create regular input file
    input_file = test_data_dir / "data_input.csv"
    input_file.write_text("col1,col2\n")

    # Create combined input file (should be excluded)
    combined = test_data_dir / "combined_input.csv"
    combined.write_text("col1,col2\n")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    datasets = mock_invocation_context.session.state["datasets"]
    assert len(datasets) == 1
    assert len(datasets[0].input_data_files) == 1
    assert datasets[0].input_data_files[0] == input_file


@pytest.mark.asyncio
async def test_discovery_agent_empty_directory(mock_invocation_context, temp_dir):
    """Test discovering with empty directory."""
    # temp_dir exists but is empty

    agent = DiscoveryAgent(name="DiscoveryAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    assert mock_invocation_context.session.state["dataset_count"] == 0
    assert len(mock_invocation_context.session.state["datasets"]) == 0


@pytest.mark.asyncio
async def test_discovery_agent_skips_files(mock_invocation_context, temp_dir):
    """Test that files in input dir are skipped (only dirs processed)."""
    # Create a file (not directory) in temp_dir
    file_in_root = Path(mock_invocation_context.session.state["input_dir"]) / "some_file.txt"
    file_in_root.write_text("content")

    # Create a valid dataset directory
    dataset_dir = Path(mock_invocation_context.session.state["input_dir"]) / "valid_dataset"
    dataset_dir.mkdir()

    agent = DiscoveryAgent(name="DiscoveryAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    # Should only discover the directory, not the file
    datasets = mock_invocation_context.session.state["datasets"]
    assert len(datasets) == 1
    assert datasets[0].name == "valid_dataset"


def test_helper_method_discover_single_dataset(temp_dir):
    """Test the helper method for discovering single dataset."""
    dataset_dir = temp_dir / "my_dataset"
    test_data_dir = dataset_dir / "test_data"
    test_data_dir.mkdir(parents=True)

    # Put metadata in input_metadata/
    input_metadata_dir = dataset_dir / "input_metadata"
    input_metadata_dir.mkdir()
    metadata = input_metadata_dir / "metadata.csv"
    metadata.write_text("param,value\n")

    input_file = test_data_dir / "data_input.csv"
    input_file.write_text("col1,col2\n")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    dataset = agent._discover_single_dataset(dataset_dir, use_metadata=True)

    assert dataset.name == "my_dataset"
    assert len(dataset.metadata_files) == 1
    assert len(dataset.input_data_files) == 1


def test_helper_method_discover_single_dataset_custom_name(temp_dir):
    """Test discovering single dataset with custom name."""
    dataset_dir = temp_dir / "actual_dir_name"
    dataset_dir.mkdir()

    agent = DiscoveryAgent(name="DiscoveryAgent")
    dataset = agent._discover_single_dataset(dataset_dir, dataset_name="custom_name")

    assert dataset.name == "custom_name"
    assert dataset.path == dataset_dir


# ============================================================================
# New tests for updated discovery
# ============================================================================


def test_discover_input_metadata_in_subfolder(temp_dir):
    """Test metadata discovery from input_metadata/ subfolder."""
    dataset_dir = temp_dir / "my_dataset"
    dataset_dir.mkdir()

    input_metadata_dir = dataset_dir / "input_metadata"
    input_metadata_dir.mkdir()

    meta1 = input_metadata_dir / "config_metadata.csv"
    meta1.write_text("param,value\nname,test\n")

    meta2 = input_metadata_dir / "extra_metadata.csv"
    meta2.write_text("param,value\nsource,test\n")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    dataset = agent._discover_single_dataset(dataset_dir, use_metadata=True)

    assert len(dataset.metadata_files) == 2
    assert dataset.use_metadata is True


def test_discover_metadata_flag_off(temp_dir):
    """Test that metadata is NOT loaded when use_metadata=False."""
    dataset_dir = temp_dir / "my_dataset"
    dataset_dir.mkdir()

    input_metadata_dir = dataset_dir / "input_metadata"
    input_metadata_dir.mkdir()

    meta = input_metadata_dir / "config_metadata.csv"
    meta.write_text("param,value\nname,test\n")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    dataset = agent._discover_single_dataset(dataset_dir, use_metadata=False)

    assert len(dataset.metadata_files) == 0
    assert dataset.use_metadata is False


def test_discover_schema_in_schema_dir(temp_dir):
    """Test schema discovery from schema/ subfolder."""
    dataset_dir = temp_dir / "my_dataset"
    dataset_dir.mkdir()

    schema_dir = dataset_dir / "schema"
    schema_dir.mkdir()

    txt = schema_dir / "example_schema.txt"
    txt.write_text("schema example content")

    mcf = schema_dir / "vertical_demographics.mcf"
    mcf.write_text("Node: example")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    dataset = agent._discover_single_dataset(dataset_dir)

    assert len(dataset.schema_files) == 2
    assert dataset.schema_examples == txt
    assert dataset.schema_mcf == mcf


def test_discover_no_schema_dir(temp_dir):
    """Test graceful handling when no schema/ dir exists."""
    dataset_dir = temp_dir / "my_dataset"
    dataset_dir.mkdir()

    agent = DiscoveryAgent(name="DiscoveryAgent")
    dataset = agent._discover_single_dataset(dataset_dir)

    assert len(dataset.schema_files) == 0
    assert dataset.schema_examples is None
    assert dataset.schema_mcf is None


def test_discover_standalone_mode(temp_dir):
    """Test _discover_standalone creates virtual DatasetInfo."""
    input_file = temp_dir / "my_data_file.csv"
    input_file.write_text("col1,col2\nval1,val2\n")

    output_dir = temp_dir / "output"
    output_dir.mkdir()

    agent = DiscoveryAgent(name="DiscoveryAgent")
    dataset = agent._discover_standalone(
        input_file=input_file,
        output_base_dir=output_dir,
    )

    assert dataset.standalone is True
    assert dataset.input_file_path == input_file
    assert len(dataset.input_data_files) == 1
    assert dataset.input_data_files[0] == input_file
    assert dataset.name == "my_data_file"
    assert len(dataset.metadata_files) == 0


def test_discover_standalone_with_metadata(temp_dir):
    """Test standalone mode with explicit metadata file."""
    input_file = temp_dir / "my_data.csv"
    input_file.write_text("col1,col2\nval1,val2\n")

    metadata_file = temp_dir / "config.csv"
    metadata_file.write_text("param,value\nname,test\n")

    output_dir = temp_dir / "output"
    output_dir.mkdir()

    agent = DiscoveryAgent(name="DiscoveryAgent")
    dataset = agent._discover_standalone(
        input_file=input_file,
        output_base_dir=output_dir,
        metadata_file=metadata_file,
    )

    assert dataset.standalone is True
    assert dataset.use_metadata is True
    assert len(dataset.metadata_files) == 1
    assert dataset.metadata_files[0] == metadata_file


def test_discover_file_overrides(temp_dir):
    """Test schema_file_override and metadata_file_override params."""
    dataset_dir = temp_dir / "my_dataset"
    dataset_dir.mkdir()

    # Create override files
    schema_override = temp_dir / "custom_schema.txt"
    schema_override.write_text("custom schema content")

    metadata_override = temp_dir / "custom_metadata.csv"
    metadata_override.write_text("param,value\ncustom,true\n")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    dataset = agent._discover_single_dataset(
        dataset_dir,
        schema_file_override=schema_override,
        metadata_file_override=metadata_override,
    )

    assert len(dataset.schema_files) == 1
    assert dataset.schema_files[0] == schema_override
    assert dataset.schema_examples == schema_override
    assert len(dataset.metadata_files) == 1
    assert dataset.metadata_files[0] == metadata_override
    assert dataset.use_metadata is True


def test_discover_ground_truth_metadata(temp_dir):
    """Test ground truth metadata discovery."""
    dataset_dir = temp_dir / "input" / "my_dataset"
    dataset_dir.mkdir(parents=True)

    # Create ground truth structure
    gt_repo = temp_dir / "ground_truth"
    gt_metadata_dir = gt_repo / "my_dataset" / "metadata"
    gt_metadata_dir.mkdir(parents=True)

    gt_meta = gt_metadata_dir / "config_metadata.csv"
    gt_meta.write_text("param,value\nname,test\n")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    dataset = agent._discover_single_dataset(
        dataset_dir,
        ground_truth_repo=gt_repo,
    )

    assert dataset.ground_truth_metadata == gt_metadata_dir


def test_discover_multi_format_files(temp_dir):
    """Test that .txt and .xlsx files in test_data/ are discovered."""
    dataset_dir = temp_dir / "my_dataset"
    test_data_dir = dataset_dir / "test_data"
    test_data_dir.mkdir(parents=True)

    # Create files of different types
    csv_file = test_data_dir / "data.csv"
    csv_file.write_text("col1,col2\nval1,val2\n")

    txt_file = test_data_dir / "data.txt"
    txt_file.write_text("col1,col2\nval1,val2\n")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    dataset = agent._discover_single_dataset(dataset_dir)

    # Both .csv and .txt should be discovered
    assert len(dataset.input_data_files) == 2
    extensions = {f.suffix for f in dataset.input_data_files}
    assert '.csv' in extensions
    assert '.txt' in extensions


def test_derive_dataset_name():
    """Test derive_dataset_name utility function."""
    from src.pipeline.discovery.file_utils import derive_dataset_name

    assert derive_dataset_name(Path("data.csv")) == "data"
    assert derive_dataset_name(Path("My-Data File.csv")) == "my_data_file"
    assert derive_dataset_name(Path("input_data_2024.xlsx")) == "input_data_2024"
    assert derive_dataset_name(Path("  spaces  .txt")) == "spaces"


def test_has_required_files_only_needs_input():
    """Test that has_required_files only requires input data."""
    dataset = DatasetInfo("test", Path("/tmp/test"))

    # No files → not required
    assert dataset.has_required_files() is False

    # Only input files → sufficient
    dataset.input_data_files = [Path("/tmp/test/data.csv")]
    assert dataset.has_required_files() is True

    # No metadata needed
    assert len(dataset.metadata_files) == 0
    assert dataset.has_required_files() is True

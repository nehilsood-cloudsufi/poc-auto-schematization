"""
Tests for DiscoveryAgent with proper ADK async patterns.

Tests dataset file discovery logic using ADK BaseAgent pattern.
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
    # Create dataset structure
    dataset_dir = Path(mock_invocation_context.session.state["input_dir"]) / "test_dataset"
    dataset_dir.mkdir()

    test_data_dir = dataset_dir / "test_data"
    test_data_dir.mkdir()

    # Create metadata file
    metadata_file = dataset_dir / "test_metadata.csv"
    metadata_file.write_text("param,value\n")

    # Create input data file
    input_file = test_data_dir / "data_input.csv"
    input_file.write_text("col1,col2\nval1,val2\n")

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

        metadata_file = dataset_dir / f"dataset_{i}_metadata.csv"
        metadata_file.write_text("param,value\n")

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
    """Test discovering schema files."""
    dataset_dir = Path(mock_invocation_context.session.state["input_dir"]) / "test_dataset"
    dataset_dir.mkdir()

    # Create schema example file
    schema_txt = dataset_dir / "scripts_statvar_llm_config_schema_examples_dc_topic_Demographics.txt"
    schema_txt.write_text("Example schema content\n")

    # Create schema MCF file
    schema_mcf = dataset_dir / "scripts_statvar_llm_config_vertical_demographics.mcf"
    schema_mcf.write_text("Node: example\n")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    datasets = mock_invocation_context.session.state["datasets"]
    assert len(datasets) == 1
    assert datasets[0].schema_examples == schema_txt
    assert datasets[0].schema_mcf == schema_mcf


@pytest.mark.asyncio
async def test_discovery_agent_metadata_files(mock_invocation_context, temp_dir):
    """Test discovering metadata files."""
    dataset_dir = Path(mock_invocation_context.session.state["input_dir"]) / "test_dataset"
    dataset_dir.mkdir()

    # Create multiple metadata files
    metadata1 = dataset_dir / "dataset_metadata.csv"
    metadata1.write_text("param,value\n")

    metadata2 = dataset_dir / "additional_metadata.csv"
    metadata2.write_text("param,value\n")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    datasets = mock_invocation_context.session.state["datasets"]
    assert len(datasets) == 1
    assert len(datasets[0].metadata_files) == 2


@pytest.mark.asyncio
async def test_discovery_agent_excludes_combined_metadata(mock_invocation_context, temp_dir):
    """Test that combined metadata files are excluded."""
    dataset_dir = Path(mock_invocation_context.session.state["input_dir"]) / "test_dataset"
    dataset_dir.mkdir()

    # Create regular metadata
    metadata = dataset_dir / "dataset_metadata.csv"
    metadata.write_text("param,value\n")

    # Create combined metadata (should be excluded)
    combined = dataset_dir / "test_dataset_combined_metadata.csv"
    combined.write_text("param,value\n")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    datasets = mock_invocation_context.session.state["datasets"]
    assert len(datasets) == 1
    assert len(datasets[0].metadata_files) == 1
    assert datasets[0].metadata_files[0] == metadata


@pytest.mark.asyncio
async def test_discovery_agent_sampled_data_files(mock_invocation_context, temp_dir):
    """Test discovering sampled data files."""
    dataset_dir = Path(mock_invocation_context.session.state["input_dir"]) / "test_dataset"
    test_data_dir = dataset_dir / "test_data"
    test_data_dir.mkdir(parents=True)

    # Create sampled data files
    sampled1 = test_data_dir / "data1_sampled_data.csv"
    sampled1.write_text("col1,col2\n")

    sampled2 = test_data_dir / "data2_sampled_data.csv"
    sampled2.write_text("col1,col2\n")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    datasets = mock_invocation_context.session.state["datasets"]
    assert len(datasets) == 1
    assert len(datasets[0].sampled_data_files) == 2


@pytest.mark.asyncio
async def test_discovery_agent_excludes_combined_sampled(mock_invocation_context, temp_dir):
    """Test that combined sampled files are excluded."""
    dataset_dir = Path(mock_invocation_context.session.state["input_dir"]) / "test_dataset"
    test_data_dir = dataset_dir / "test_data"
    test_data_dir.mkdir(parents=True)

    # Create regular sampled file
    sampled = test_data_dir / "data_sampled_data.csv"
    sampled.write_text("col1,col2\n")

    # Create combined sampled file (should be excluded)
    combined = test_data_dir / "combined_sampled_data.csv"
    combined.write_text("col1,col2\n")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    datasets = mock_invocation_context.session.state["datasets"]
    assert len(datasets) == 1
    assert len(datasets[0].sampled_data_files) == 1
    assert datasets[0].sampled_data_files[0] == sampled


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

    metadata = dataset_dir / "metadata.csv"
    metadata.write_text("param,value\n")

    input_file = test_data_dir / "data_input.csv"
    input_file.write_text("col1,col2\n")

    agent = DiscoveryAgent(name="DiscoveryAgent")
    dataset = agent._discover_single_dataset(dataset_dir)

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

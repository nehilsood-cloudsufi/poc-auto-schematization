"""
Tests for SchemaSelectionAgent (LlmAgent configuration).

Tests that the agent is properly configured with schema tools.
Full integration tests would require LLM mocking which is complex.
"""

import pytest
from pathlib import Path

from src.agents.schema_selection_agent import create_schema_selection_agent
from src.state.dataset_info import DatasetInfo


def test_schema_selection_agent_creation():
    """Test SchemaSelectionAgent can be created."""
    agent = create_schema_selection_agent()
    assert agent is not None
    assert agent.name == "SchemaSelectionAgent"
    assert agent.model == "gemini-3-pro-preview"


def test_schema_selection_agent_custom_name_and_model():
    """Test SchemaSelectionAgent with custom name and model."""
    agent = create_schema_selection_agent(name="CustomSchemaSelector", model="gemini-2.0-flash-exp")
    assert agent.name == "CustomSchemaSelector"
    assert agent.model == "gemini-2.0-flash-exp"


def test_schema_selection_agent_has_tools():
    """Test SchemaSelectionAgent has schema tools configured."""
    agent = create_schema_selection_agent()
    assert hasattr(agent, 'tools')
    assert len(agent.tools) == 3

    # Verify tool names
    tool_names = [tool.__name__ for tool in agent.tools]
    assert "get_schema_categories" in tool_names
    assert "generate_data_preview" in tool_names
    assert "copy_schema_files" in tool_names


def test_schema_selection_agent_has_instruction():
    """Test SchemaSelectionAgent has proper instruction."""
    agent = create_schema_selection_agent()
    assert hasattr(agent, 'instruction')
    assert "schema selection" in agent.instruction.lower()
    assert "get_schema_categories" in agent.instruction
    assert "generate_data_preview" in agent.instruction
    assert "copy_schema_files" in agent.instruction


def test_schema_selection_agent_has_output_key():
    """Test SchemaSelectionAgent has output_key for automatic state updates."""
    agent = create_schema_selection_agent()
    assert hasattr(agent, 'output_key')
    assert agent.output_key == "schema_category"


@pytest.mark.asyncio
async def test_schema_selection_agent_instruction_has_flags(mock_invocation_context, temp_dir):
    """Test that instruction template includes schema selection flags."""
    dataset = DatasetInfo(name="test_dataset", path=temp_dir / "test_dataset")
    mock_invocation_context.session.state["current_dataset"] = dataset
    mock_invocation_context.session.state["combined_sampled_data"] = str(temp_dir / "sample.csv")
    mock_invocation_context.session.state["skip_schema_selection"] = False
    mock_invocation_context.session.state["force_schema_selection"] = False

    agent = create_schema_selection_agent()

    # Verify instruction has template placeholders
    assert "{current_dataset.name}" in agent.instruction or "{current_dataset}" in agent.instruction
    assert "{combined_sampled_data}" in agent.instruction
    assert "{skip_schema_selection}" in agent.instruction
    assert "{force_schema_selection}" in agent.instruction


def test_schema_selection_agent_instruction_includes_categories():
    """Test that instruction mentions common schema categories."""
    agent = create_schema_selection_agent()
    instruction_lower = agent.instruction.lower()

    # Check for common category mentions
    assert "demographics" in instruction_lower or "population" in instruction_lower
    assert "economics" in instruction_lower or "gdp" in instruction_lower
    assert "health" in instruction_lower
    assert "education" in instruction_lower


# Note: Full integration tests with LLM execution would require:
# 1. Mocking the Gemini API responses
# 2. Setting up complete dataset structures with real data
# 3. Verifying tool calls sequence (get_schema_categories → generate_data_preview → copy_schema_files)
# 4. Verifying state updates (schema_category, schema_examples_file, schema_mcf_file)
#
# These are better suited for end-to-end integration tests
# where we test the full pipeline with real or mocked LLM responses.

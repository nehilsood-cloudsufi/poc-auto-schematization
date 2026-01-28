"""
Tests for SamplingAgent (LlmAgent configuration).

Tests that the agent is properly configured with tools.
Full integration tests would require LLM mocking which is complex.
"""

import pytest
from pathlib import Path

from src.agents.sampling_agent import create_sampling_agent
from src.state.dataset_info import DatasetInfo


def test_sampling_agent_creation():
    """Test SamplingAgent can be created."""
    agent = create_sampling_agent()
    assert agent is not None
    assert agent.name == "SamplingAgent"
    assert agent.model == "gemini-3-pro-preview"


def test_sampling_agent_custom_name_and_model():
    """Test SamplingAgent with custom name and model."""
    agent = create_sampling_agent(name="CustomSampler", model="gemini-2.0-flash-exp")
    assert agent.name == "CustomSampler"
    assert agent.model == "gemini-2.0-flash-exp"


def test_sampling_agent_has_tools():
    """Test SamplingAgent has sampling tools configured."""
    agent = create_sampling_agent()
    assert hasattr(agent, 'tools')
    assert len(agent.tools) == 1
    assert agent.tools[0].__name__ == "sample_data"


def test_sampling_agent_has_instruction():
    """Test SamplingAgent has proper instruction."""
    agent = create_sampling_agent()
    assert hasattr(agent, 'instruction')
    assert "sampling" in agent.instruction.lower()
    assert "skip_sampling" in agent.instruction
    assert "force_resample" in agent.instruction


@pytest.mark.asyncio
async def test_sampling_agent_skip_flag_in_instruction(mock_invocation_context, temp_dir):
    """Test that instruction template includes skip_sampling flag."""
    dataset = DatasetInfo(name="test_dataset", path=temp_dir / "test_dataset")
    mock_invocation_context.session.state["current_dataset"] = dataset
    mock_invocation_context.session.state["skip_sampling"] = True
    mock_invocation_context.session.state["force_resample"] = False

    agent = create_sampling_agent()

    # Verify instruction has template placeholders
    assert "{current_dataset.name}" in agent.instruction or "{current_dataset}" in agent.instruction
    assert "{skip_sampling}" in agent.instruction
    assert "{force_resample}" in agent.instruction


# Note: Full integration tests with LLM execution would require:
# 1. Mocking the Gemini API responses
# 2. Setting up complete dataset structures
# 3. Verifying tool calls and state updates
#
# These are better suited for end-to-end integration tests
# where we test the full pipeline with real or mocked LLM responses.

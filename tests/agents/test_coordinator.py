"""
Tests for Pipeline Coordinator.

Tests SequentialAgent orchestration of all pipeline phases.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.agents.coordinator import create_pipeline_coordinator, PipelineCoordinator


def test_coordinator_creation():
    """Test coordinator can be created."""
    coordinator = create_pipeline_coordinator()
    assert coordinator is not None
    assert coordinator.name == "PipelineCoordinator"


def test_coordinator_custom_name():
    """Test coordinator with custom name."""
    coordinator = create_pipeline_coordinator(name="CustomPipeline")
    assert coordinator.name == "CustomPipeline"


def test_coordinator_has_sub_agents():
    """Test coordinator has all required sub-agents."""
    coordinator = create_pipeline_coordinator()
    
    # SequentialAgent should have sub_agents attribute
    assert hasattr(coordinator, 'sub_agents')
    assert len(coordinator.sub_agents) == 5
    
    # Verify agent names
    agent_names = [agent.name for agent in coordinator.sub_agents]
    assert "DiscoveryAgent" in agent_names
    assert "SamplingAgent" in agent_names
    assert "SchemaSelectionAgent" in agent_names
    assert "PVMAPGenerationAgent" in agent_names
    assert "EvaluationAgent" in agent_names


def test_coordinator_sub_agents_order():
    """Test sub-agents are in correct sequential order."""
    coordinator = create_pipeline_coordinator()
    
    agent_names = [agent.name for agent in coordinator.sub_agents]
    
    # Verify execution order
    assert agent_names[0] == "DiscoveryAgent"
    assert agent_names[1] == "SamplingAgent"
    assert agent_names[2] == "SchemaSelectionAgent"
    assert agent_names[3] == "PVMAPGenerationAgent"
    assert agent_names[4] == "EvaluationAgent"


def test_coordinator_custom_max_retries():
    """Test coordinator with custom max_retries."""
    coordinator = create_pipeline_coordinator(max_retries=5)
    
    # Find PVMAP generation agent
    pvmap_agent = None
    for agent in coordinator.sub_agents:
        if agent.name == "PVMAPGenerationAgent":
            pvmap_agent = agent
            break
    
    assert pvmap_agent is not None
    assert pvmap_agent._max_retries == 5


def test_coordinator_custom_model():
    """Test coordinator with custom model."""
    coordinator = create_pipeline_coordinator(model="gemini-2.0-flash-exp")
    
    # Find LLM agents and check model
    sampling_agent = None
    schema_agent = None
    pvmap_agent = None
    
    for agent in coordinator.sub_agents:
        if agent.name == "SamplingAgent":
            sampling_agent = agent
        elif agent.name == "SchemaSelectionAgent":
            schema_agent = agent
        elif agent.name == "PVMAPGenerationAgent":
            pvmap_agent = agent
    
    assert sampling_agent is not None
    assert sampling_agent.model == "gemini-2.0-flash-exp"
    
    assert schema_agent is not None
    assert schema_agent.model == "gemini-2.0-flash-exp"
    
    assert pvmap_agent is not None
    assert pvmap_agent._generator.model == "gemini-2.0-flash-exp"


def test_coordinator_backward_compatibility_alias():
    """Test that PipelineCoordinator alias works."""
    coordinator = PipelineCoordinator()
    assert coordinator is not None
    assert coordinator.name == "PipelineCoordinator"


@pytest.mark.asyncio
async def test_coordinator_sequential_execution_flow(mock_invocation_context, temp_dir):
    """Test that coordinator properly orchestrates sequential execution."""
    # Setup state
    dataset_dir = temp_dir / "test_dataset"
    dataset_dir.mkdir()
    
    mock_invocation_context.session.state["input_dir"] = str(temp_dir)
    
    coordinator = create_pipeline_coordinator()
    
    # Verify coordinator is a SequentialAgent
    from google.adk.agents import SequentialAgent
    assert isinstance(coordinator, SequentialAgent)
    
    # Verify it has the run_async method (inherited from BaseAgent)
    assert hasattr(coordinator, 'run_async')


def test_coordinator_agent_types():
    """Test that coordinator contains correct agent types."""
    coordinator = create_pipeline_coordinator()
    
    from google.adk.agents import BaseAgent, LlmAgent
    from src.agents.discovery_agent import DiscoveryAgent
    from src.agents.evaluation_agent import EvaluationAgent
    from src.agents.pvmap_generation_agent import PVMAPGenerationAgent
    
    # All agents should inherit from BaseAgent
    for agent in coordinator.sub_agents:
        assert isinstance(agent, BaseAgent)
    
    # Check specific types
    assert isinstance(coordinator.sub_agents[0], DiscoveryAgent)
    assert isinstance(coordinator.sub_agents[1], LlmAgent)  # SamplingAgent
    assert isinstance(coordinator.sub_agents[2], LlmAgent)  # SchemaSelectionAgent
    assert isinstance(coordinator.sub_agents[3], PVMAPGenerationAgent)
    assert isinstance(coordinator.sub_agents[4], EvaluationAgent)


# Note: Full integration tests with actual execution are in tests/integration/
# These tests focus on configuration and structure

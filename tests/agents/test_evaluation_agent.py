"""
Tests for EvaluationAgent with proper ADK async patterns.

Tests PVMAP evaluation logic using ADK BaseAgent pattern.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.agents.evaluation_agent import EvaluationAgent
from src.state.dataset_info import DatasetInfo


def test_evaluation_agent_initialization():
    """Test EvaluationAgent can be initialized."""
    agent = EvaluationAgent(name="EvaluationAgent")
    assert agent is not None
    assert agent.name == "EvaluationAgent"


@pytest.mark.asyncio
async def test_evaluation_agent_skip_flag(mock_invocation_context):
    """Test evaluation is skipped when skip_evaluation is True."""
    mock_invocation_context.session.state["skip_evaluation"] = True

    agent = EvaluationAgent(name="EvaluationAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    # Verify skip behavior
    assert mock_invocation_context.session.state["evaluation_passed"] is True
    assert mock_invocation_context.session.state["eval_metrics"] == {}
    assert len(events) == 1
    event_text = events[0].content.parts[0].text
    assert "skipped" in event_text.lower()


@pytest.mark.asyncio
async def test_evaluation_agent_missing_dataset(mock_invocation_context):
    """Test agent with missing current_dataset in state."""
    # No current_dataset in state
    mock_invocation_context.session.state.pop("current_dataset", None)

    agent = EvaluationAgent(name="EvaluationAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    # Verify error handling
    assert mock_invocation_context.session.state["evaluation_passed"] is False
    assert mock_invocation_context.session.state["error"] == "No current_dataset specified in state"
    assert len(events) == 1
    event_text = events[0].content.parts[0].text
    assert "failed" in event_text.lower()


@pytest.mark.asyncio
async def test_evaluation_agent_missing_pvmap(mock_invocation_context, temp_dir):
    """Test agent with missing pvmap_path."""
    dataset = DatasetInfo(name="test_dataset", path=temp_dir / "test_dataset")
    mock_invocation_context.session.state["current_dataset"] = dataset
    mock_invocation_context.session.state["pvmap_path"] = str(temp_dir / "nonexistent.csv")

    agent = EvaluationAgent(name="EvaluationAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    # Verify error handling
    assert mock_invocation_context.session.state["evaluation_passed"] is False
    assert "not found" in mock_invocation_context.session.state["error"].lower()
    assert len(events) == 1


@pytest.mark.asyncio
async def test_evaluation_agent_success(mock_invocation_context, temp_dir):
    """Test successful evaluation with ground truth."""
    # Setup dataset
    dataset_dir = temp_dir / "test_dataset"
    dataset_dir.mkdir()
    dataset = DatasetInfo(name="test_dataset", path=dataset_dir)

    # Create auto-generated PVMAP
    pvmap_path = dataset_dir / "auto_pvmap.csv"
    pvmap_path.write_text("key,property,value\nrow1,col1,val1\n")

    # Create ground truth PVMAP
    gt_pvmap_path = dataset_dir / "pvmap_ground_truth.csv"
    gt_pvmap_path.write_text("key,property,value\nrow1,col1,val1\n")

    mock_invocation_context.session.state["current_dataset"] = dataset
    mock_invocation_context.session.state["pvmap_path"] = str(pvmap_path)
    mock_invocation_context.session.state["output_dir"] = str(dataset_dir)

    # Mock the tool functions
    with patch('src.agents.evaluation_agent.find_ground_truth_pvmaps') as mock_find_gt, \
         patch('src.agents.evaluation_agent.compare_pvmaps') as mock_compare:

        mock_find_gt.return_value = {
            "success": True,
            "pvmaps": [gt_pvmap_path],
            "count": 1,
            "error": None
        }

        mock_compare.return_value = {
            "success": True,
            "metrics": {
                "f1_score": 0.95,
                "precision": 0.96,
                "recall": 0.94
            }
        }

        agent = EvaluationAgent(name="EvaluationAgent")
        events = []
        async for event in agent._run_async_impl(mock_invocation_context):
            events.append(event)

    # Verify state was updated
    assert mock_invocation_context.session.state["evaluation_passed"] is True
    assert mock_invocation_context.session.state["eval_metrics"]["f1_score"] == 0.95
    assert mock_invocation_context.session.state["best_ground_truth_pvmap"] == str(gt_pvmap_path)
    assert len(mock_invocation_context.session.state["ground_truth_pvmaps"]) == 1

    # Verify event
    assert len(events) == 1
    event_text = events[0].content.parts[0].text
    assert "F1=0.95" in event_text or "F1=0.950" in event_text


@pytest.mark.asyncio
async def test_evaluation_agent_no_ground_truth(mock_invocation_context, temp_dir):
    """Test evaluation when no ground truth is found."""
    dataset_dir = temp_dir / "test_dataset"
    dataset_dir.mkdir()
    dataset = DatasetInfo(name="test_dataset", path=dataset_dir)

    pvmap_path = dataset_dir / "auto_pvmap.csv"
    pvmap_path.write_text("key,property,value\n")

    mock_invocation_context.session.state["current_dataset"] = dataset
    mock_invocation_context.session.state["pvmap_path"] = str(pvmap_path)

    # Mock find_ground_truth_pvmaps to return no results
    with patch('src.agents.evaluation_agent.find_ground_truth_pvmaps') as mock_find_gt:
        mock_find_gt.return_value = {
            "success": False,
            "pvmaps": [],
            "count": 0,
            "error": "No ground truth PVMAPs found"
        }

        agent = EvaluationAgent(name="EvaluationAgent")
        events = []
        async for event in agent._run_async_impl(mock_invocation_context):
            events.append(event)

    # Verify error handling
    assert mock_invocation_context.session.state["evaluation_passed"] is False
    assert "No ground truth" in mock_invocation_context.session.state["error"]
    assert mock_invocation_context.session.state["eval_metrics"] == {}
    assert len(events) == 1


@pytest.mark.asyncio
async def test_evaluation_agent_multiple_ground_truths(mock_invocation_context, temp_dir):
    """Test evaluation with multiple ground truth files (selects best)."""
    dataset_dir = temp_dir / "test_dataset"
    dataset_dir.mkdir()
    dataset = DatasetInfo(name="test_dataset", path=dataset_dir)

    pvmap_path = dataset_dir / "auto_pvmap.csv"
    pvmap_path.write_text("key,property,value\n")

    gt1 = dataset_dir / "pvmap_gt1.csv"
    gt2 = dataset_dir / "pvmap_gt2.csv"
    gt1.write_text("key,property,value\n")
    gt2.write_text("key,property,value\n")

    mock_invocation_context.session.state["current_dataset"] = dataset
    mock_invocation_context.session.state["pvmap_path"] = str(pvmap_path)
    mock_invocation_context.session.state["output_dir"] = str(dataset_dir)

    # Mock tools - gt2 has better F1 score
    with patch('src.agents.evaluation_agent.find_ground_truth_pvmaps') as mock_find_gt, \
         patch('src.agents.evaluation_agent.compare_pvmaps') as mock_compare:

        mock_find_gt.return_value = {
            "success": True,
            "pvmaps": [gt1, gt2],
            "count": 2,
            "error": None
        }

        # Return different metrics for each comparison
        def compare_side_effect(auto_pvmap_path, gt_pvmap_path, output_dir):
            if gt_pvmap_path == gt1:
                return {
                    "success": True,
                    "metrics": {"f1_score": 0.80, "precision": 0.85, "recall": 0.75}
                }
            else:  # gt2
                return {
                    "success": True,
                    "metrics": {"f1_score": 0.92, "precision": 0.93, "recall": 0.91}
                }

        mock_compare.side_effect = compare_side_effect

        agent = EvaluationAgent(name="EvaluationAgent")
        events = []
        async for event in agent._run_async_impl(mock_invocation_context):
            events.append(event)

    # Verify best GT was selected (gt2 with F1=0.92)
    assert mock_invocation_context.session.state["evaluation_passed"] is True
    assert mock_invocation_context.session.state["eval_metrics"]["f1_score"] == 0.92
    assert mock_invocation_context.session.state["best_ground_truth_pvmap"] == str(gt2)
    assert len(mock_invocation_context.session.state["ground_truth_pvmaps"]) == 2


@pytest.mark.asyncio
async def test_evaluation_agent_comparison_failure(mock_invocation_context, temp_dir):
    """Test evaluation when all comparisons fail."""
    dataset_dir = temp_dir / "test_dataset"
    dataset_dir.mkdir()
    dataset = DatasetInfo(name="test_dataset", path=dataset_dir)

    pvmap_path = dataset_dir / "auto_pvmap.csv"
    pvmap_path.write_text("key,property,value\n")

    gt_pvmap = dataset_dir / "pvmap_gt.csv"
    gt_pvmap.write_text("key,property,value\n")

    mock_invocation_context.session.state["current_dataset"] = dataset
    mock_invocation_context.session.state["pvmap_path"] = str(pvmap_path)

    # Mock tools - comparison fails
    with patch('src.agents.evaluation_agent.find_ground_truth_pvmaps') as mock_find_gt, \
         patch('src.agents.evaluation_agent.compare_pvmaps') as mock_compare:

        mock_find_gt.return_value = {
            "success": True,
            "pvmaps": [gt_pvmap],
            "count": 1,
            "error": None
        }

        mock_compare.return_value = {
            "success": False,
            "metrics": {},
            "error": "Comparison failed"
        }

        agent = EvaluationAgent(name="EvaluationAgent")
        events = []
        async for event in agent._run_async_impl(mock_invocation_context):
            events.append(event)

    # Verify error handling
    assert mock_invocation_context.session.state["evaluation_passed"] is False
    assert "failed" in mock_invocation_context.session.state["error"].lower()
    assert mock_invocation_context.session.state["eval_metrics"] == {}

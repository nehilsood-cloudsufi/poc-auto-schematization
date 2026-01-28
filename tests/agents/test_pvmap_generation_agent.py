"""
Tests for PVMAPGenerationAgent with retry loop and inline validation.

Tests async agent with mocked LlmAgent and validation subprocess.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from src.agents.pvmap_generation_agent import PVMAPGenerationAgent
from src.state.dataset_info import DatasetInfo


@pytest.fixture
def mock_dataset(temp_dir):
    """Create mock dataset with required files."""
    dataset_dir = temp_dir / "test_dataset"
    dataset_dir.mkdir()
    
    # Create output directory
    output_dir = dataset_dir / "output"
    output_dir.mkdir()
    
    # Create sampled data file
    sampled_data = dataset_dir / "sampled_data.csv"
    sampled_data.write_text("col1,col2\n1,2\n3,4\n")
    
    # Create metadata file
    metadata = dataset_dir / "metadata.csv"
    metadata.write_text("param,value\nunit,Count\n")
    
    # Create schema examples file (optional)
    schema = dataset_dir / "schema_examples.txt"
    schema.write_text("Example schema for testing")
    
    dataset = DatasetInfo(
        name="test_dataset",
        path=dataset_dir
    )
    dataset.combined_sampled_data = sampled_data
    dataset.combined_metadata = metadata
    dataset.schema_examples = schema
    dataset.output_dir = output_dir
    
    return dataset


@pytest.fixture
def mock_template(temp_dir):
    """Create mock prompt template."""
    template_path = temp_dir / "template.txt"
    template_path.write_text(
        "Schema: {{SCHEMA_EXAMPLES}}\n"
        "Data: {{SAMPLED_DATA}}\n"
        "Metadata: {{METADATA_CONFIG}}"
    )
    return template_path


@pytest.mark.asyncio
async def test_pvmap_generation_agent_initialization():
    """Test PVMAPGenerationAgent can be initialized."""
    agent = PVMAPGenerationAgent(name="TestPVMAPGen", max_retries=2)
    assert agent is not None
    assert agent.name == "TestPVMAPGen"
    assert agent._max_retries == 2
    assert hasattr(agent, '_generator')
    assert agent._generator.model == "gemini-3-pro-preview"


@pytest.mark.asyncio
async def test_pvmap_generation_missing_dataset(mock_invocation_context):
    """Test agent with missing current_dataset in state."""
    mock_invocation_context.session.state.pop("current_dataset", None)
    
    agent = PVMAPGenerationAgent(name="TestPVMAPGen")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)
    
    # Verify error handling
    assert mock_invocation_context.session.state["generation_success"] is False
    assert "No current_dataset" in mock_invocation_context.session.state["error"]
    assert len(events) == 1


@pytest.mark.asyncio
async def test_pvmap_generation_missing_template(mock_invocation_context, mock_dataset, temp_dir):
    """Test agent with missing template file."""
    mock_invocation_context.session.state["current_dataset"] = mock_dataset
    mock_invocation_context.session.state["prompt_template_path"] = str(temp_dir / "nonexistent.txt")
    
    agent = PVMAPGenerationAgent(name="TestPVMAPGen")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)
    
    # Verify error handling
    assert mock_invocation_context.session.state["generation_success"] is False
    assert "template not found" in mock_invocation_context.session.state["error"].lower()


@pytest.mark.asyncio
async def test_pvmap_generation_single_attempt_success(
    mock_invocation_context, mock_dataset, mock_template
):
    """Test successful generation on first attempt."""
    mock_invocation_context.session.state["current_dataset"] = mock_dataset
    mock_invocation_context.session.state["prompt_template_path"] = str(mock_template)
    
    # Create mock LlmAgent
    async def mock_generator_run(ctx):
        ctx.session.state["pvmap_raw_output"] = """
Here's the PVMAP:

```csv
key,property,value
col1,prop1,{Data}
col2,prop2,{Number}
```
"""
        yield Mock(content=Mock(parts=[Mock(text="Generated PVMAP")]))
    
    # Mock validation to succeed
    mock_validation_result = {
        "success": True,
        "output_file": str(mock_dataset.output_dir / "processed.csv"),
        "error": None
    }
    
    agent = PVMAPGenerationAgent(name="TestPVMAPGen", max_retries=2)
    
    # Replace the generator's run_async with mock
    original_run_async = agent._generator.run_async
    agent._generator.run_async = mock_generator_run
    
    with patch('src.agents.pvmap_generation_agent.run_validation', return_value=mock_validation_result):
        
        events = []
        async for event in agent._run_async_impl(mock_invocation_context):
            events.append(event)
    
    # Restore
    agent._generator.run_async = original_run_async
    
    # Verify success
    assert mock_invocation_context.session.state["generation_success"] is True
    assert mock_invocation_context.session.state["error"] is None
    assert mock_invocation_context.session.state["retry_count"] == 0
    assert "pvmap_content" in mock_invocation_context.session.state
    assert "pvmap_path" in mock_invocation_context.session.state
    
    # Verify PVMAP file was written
    pvmap_path = Path(mock_invocation_context.session.state["pvmap_path"])
    assert pvmap_path.exists()
    assert "key,property,value" in pvmap_path.read_text()


@pytest.mark.asyncio
async def test_pvmap_generation_retry_on_validation_fail(
    mock_invocation_context, mock_dataset, mock_template
):
    """Test retry when validation fails then succeeds."""
    mock_invocation_context.session.state["current_dataset"] = mock_dataset
    mock_invocation_context.session.state["prompt_template_path"] = str(mock_template)
    
    # Mock LlmAgent run_async
    async def mock_generator_run(ctx):
        ctx.session.state["pvmap_raw_output"] = """
```csv
key,property,value
col1,prop1,{Data}
```
"""
        yield Mock(content=Mock(parts=[Mock(text="Generated PVMAP")]))
    
    # Mock validation to fail first, then succeed
    validation_call_count = [0]
    
    def mock_validation_side_effect(*args, **kwargs):
        validation_call_count[0] += 1
        if validation_call_count[0] == 1:
            # First attempt fails
            return {
                "success": False,
                "error": "Error: Missing mapping for column 'col2'"
            }
        else:
            # Second attempt succeeds
            return {
                "success": True,
                "output_file": str(mock_dataset.output_dir / "processed.csv"),
                "error": None
            }
    
    agent = PVMAPGenerationAgent(name="TestPVMAPGen", max_retries=2)
    agent._generator.run_async = mock_generator_run
    
    with patch('src.agents.pvmap_generation_agent.run_validation', side_effect=mock_validation_side_effect), \
         patch('src.agents.pvmap_generation_agent.extract_log_samples', return_value="Sampled error logs"):
        
        events = []
        async for event in agent._run_async_impl(mock_invocation_context):
            events.append(event)
    
    # Verify success after retry
    assert mock_invocation_context.session.state["generation_success"] is True
    assert mock_invocation_context.session.state["retry_count"] == 1
    assert validation_call_count[0] == 2  # Called twice


@pytest.mark.asyncio
async def test_pvmap_generation_max_retries_exceeded(
    mock_invocation_context, mock_dataset, mock_template
):
    """Test failure when max retries exceeded."""
    mock_invocation_context.session.state["current_dataset"] = mock_dataset
    mock_invocation_context.session.state["prompt_template_path"] = str(mock_template)
    
    # Mock LlmAgent run_async
    async def mock_generator_run(ctx):
        ctx.session.state["pvmap_raw_output"] = """
```csv
key,property,value
col1,prop1,{Data}
```
"""
        yield Mock(content=Mock(parts=[Mock(text="Generated PVMAP")]))
    
    # Mock validation to always fail
    mock_validation_result = {
        "success": False,
        "error": "Persistent validation error"
    }
    
    agent = PVMAPGenerationAgent(name="TestPVMAPGen", max_retries=2)
    agent._generator.run_async = mock_generator_run
    
    with patch('src.agents.pvmap_generation_agent.run_validation', return_value=mock_validation_result), \
         patch('src.agents.pvmap_generation_agent.extract_log_samples', return_value="Sampled error logs"):
        
        events = []
        async for event in agent._run_async_impl(mock_invocation_context):
            events.append(event)
    
    # Verify failure
    assert mock_invocation_context.session.state["generation_success"] is False
    assert "Max retries" in mock_invocation_context.session.state["error"]
    assert mock_invocation_context.session.state["retry_count"] == 2


@pytest.mark.asyncio
async def test_pvmap_generation_error_feedback_flow(
    mock_invocation_context, mock_dataset, mock_template
):
    """Test that error feedback is properly accumulated and used."""
    mock_invocation_context.session.state["current_dataset"] = mock_dataset
    mock_invocation_context.session.state["prompt_template_path"] = str(mock_template)
    
    # Mock LlmAgent run_async
    async def mock_generator_run(ctx):
        ctx.session.state["pvmap_raw_output"] = """
```csv
key,property,value
col1,prop1,{Data}
```
"""
        yield Mock(content=Mock(parts=[Mock(text="Generated PVMAP")]))
    
    # Mock validation to fail
    mock_validation_result = {
        "success": False,
        "error": "Validation error with details"
    }
    
    agent = PVMAPGenerationAgent(name="TestPVMAPGen", max_retries=0)  # Only 1 attempt
    agent._generator.run_async = mock_generator_run
    
    with patch('src.agents.pvmap_generation_agent.run_validation', return_value=mock_validation_result), \
         patch('src.agents.pvmap_generation_agent.extract_log_samples', return_value="Sampled error logs"):
        
        events = []
        async for event in agent._run_async_impl(mock_invocation_context):
            events.append(event)
    
    # Verify error feedback was stored
    assert "error_feedback" in mock_invocation_context.session.state
    assert mock_invocation_context.session.state["error_feedback"] == "Sampled error logs"


@pytest.mark.asyncio
async def test_pvmap_generation_csv_extraction_failure(
    mock_invocation_context, mock_dataset, mock_template
):
    """Test failure when CSV cannot be extracted."""
    mock_invocation_context.session.state["current_dataset"] = mock_dataset
    mock_invocation_context.session.state["prompt_template_path"] = str(mock_template)
    
    # Mock LlmAgent to return non-CSV output
    async def mock_generator_run(ctx):
        ctx.session.state["pvmap_raw_output"] = "This is not a CSV at all"
        yield Mock(content=Mock(parts=[Mock(text="Generated something")]))
    
    agent = PVMAPGenerationAgent(name="TestPVMAPGen")
    agent._generator.run_async = mock_generator_run
    
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)
    
    # Verify failure
    assert mock_invocation_context.session.state["generation_success"] is False
    assert "Could not extract CSV" in mock_invocation_context.session.state["error"]


@pytest.mark.asyncio
async def test_pvmap_generation_llm_failure(
    mock_invocation_context, mock_dataset, mock_template
):
    """Test failure when LLM generation fails."""
    mock_invocation_context.session.state["current_dataset"] = mock_dataset
    mock_invocation_context.session.state["prompt_template_path"] = str(mock_template)
    
    # Mock LlmAgent to raise exception
    async def mock_generator_run(ctx):
        raise RuntimeError("LLM API error")
        yield  # Make it a generator
    
    agent = PVMAPGenerationAgent(name="TestPVMAPGen")
    agent._generator.run_async = mock_generator_run
    
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)
    
    # Verify failure
    assert mock_invocation_context.session.state["generation_success"] is False
    assert "LLM generation failed" in mock_invocation_context.session.state["error"]

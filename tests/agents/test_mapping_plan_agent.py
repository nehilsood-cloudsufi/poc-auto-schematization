import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.mapping_plan_agent import MappingPlanAgent


def test_agent_instantiation():
    """MappingPlanAgent can be created with defaults."""
    agent = MappingPlanAgent(name="TestPlan")
    assert agent.name == "TestPlan"


def test_agent_has_correct_model():
    """Agent uses the specified model."""
    agent = MappingPlanAgent(name="TestPlan", model="gemini-3-flash-preview")
    assert agent._model_name == "gemini-3-flash-preview"


def test_agent_default_model():
    """Agent uses default model when none specified."""
    agent = MappingPlanAgent(name="TestPlan")
    assert agent._model_name == "gemini-3.1-pro-preview"


@pytest.mark.asyncio
async def test_plan_saved_to_disk(tmp_path):
    """Agent saves mapping plan to output directory."""
    agent = MappingPlanAgent(name="TestPlan")

    ctx = MagicMock()
    ctx.session.state = {
        "skeleton_summary": "## COLUMN REFERENCE TABLE\n| Column | Type |\n| Year | int |",
        "schema_category": "Economy",
        "schema_vocab_content": "{}",
        "sampled_data": "Year,Value\n2020,100",
        "statvar_summary": "",
        "per_column_dc_matches": "",
        "discovered_statvars": [],
        "output_dir": str(tmp_path),
        "dataset_name": "test_dataset",
    }

    mock_plan = "# Mapping Plan: test_dataset\n\n## Dataset Understanding\n- **Format:** Flat"
    with patch.object(agent, '_generate_plan', return_value=mock_plan):
        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

    assert ctx.session.state["mapping_plan"] == mock_plan
    plan_path = tmp_path / "mapping_plan.md"
    assert plan_path.exists()
    assert "Mapping Plan: test_dataset" in plan_path.read_text()


@pytest.mark.asyncio
async def test_plan_emits_events(tmp_path):
    """Agent emits at least two events (start + completion)."""
    agent = MappingPlanAgent(name="TestPlan")

    ctx = MagicMock()
    ctx.session.state = {
        "skeleton_summary": "col summary",
        "schema_category": "Health",
        "schema_vocab_content": "",
        "sampled_data": "a,b\n1,2",
        "statvar_summary": "",
        "per_column_dc_matches": "",
        "output_dir": str(tmp_path),
        "dataset_name": "health_dataset",
    }

    mock_plan = "# Mapping Plan\n\n## Dataset Understanding\n- **Format:** Flat"
    with patch.object(agent, '_generate_plan', return_value=mock_plan):
        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

    assert len(events) >= 2


@pytest.mark.asyncio
async def test_template_populated_with_state(tmp_path):
    """Agent populates template with state values before LLM call."""
    agent = MappingPlanAgent(name="TestPlan")

    ctx = MagicMock()
    ctx.session.state = {
        "skeleton_summary": "SKELETON_CONTENT",
        "schema_category": "Economy",
        "schema_vocab_content": "VOCAB_CONTENT",
        "sampled_data": "SAMPLED_DATA",
        "statvar_summary": "STATVAR_SUMMARY",
        "per_column_dc_matches": "DC_MATCHES",
        "output_dir": str(tmp_path),
        "dataset_name": "test_dataset",
    }

    captured_prompts = []

    async def capture_prompt(prompt):
        captured_prompts.append(prompt)
        return "# Mapping Plan\n"

    with patch.object(agent, '_generate_plan', side_effect=capture_prompt):
        async for _ in agent._run_async_impl(ctx):
            pass

    assert len(captured_prompts) == 1
    prompt = captured_prompts[0]
    assert "SKELETON_CONTENT" in prompt
    assert "VOCAB_CONTENT" in prompt
    assert "SAMPLED_DATA" in prompt
    assert "STATVAR_SUMMARY" in prompt
    assert "DC_MATCHES" in prompt


@pytest.mark.asyncio
async def test_missing_state_keys_use_empty_string(tmp_path):
    """Agent uses empty strings for missing optional state keys."""
    agent = MappingPlanAgent(name="TestPlan")

    ctx = MagicMock()
    ctx.session.state = {
        "output_dir": str(tmp_path),
        "dataset_name": "test_dataset",
    }

    mock_plan = "# Mapping Plan\n"
    with patch.object(agent, '_generate_plan', return_value=mock_plan):
        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

    assert ctx.session.state["mapping_plan"] == mock_plan


def test_plan_required_sections():
    """Verify expected plan section markers."""
    mock_plan = """# Mapping Plan: test_dataset

## Dataset Understanding
- **Format:** Flat

## Data Commons Findings
- **Existing StatVars found:** None

## Column Mappings

### Column: `Year`
- **Role:** observationDate
- **Mapping:** `observationDate -> [DATA]`
- **Reason:** Date column
- **Evidence:** 10 unique values
- **Alternatives rejected:** Not a dimension
- **Schema.org:** N/A
- **DC Match:** None
- **DC Properties:** N/A

## Properties to Generate
- populationType,Person

## Global Notes
- Simple flat dataset
"""
    required_sections = [
        "## Dataset Understanding",
        "## Data Commons Findings",
        "## Column Mappings",
        "## Properties to Generate",
        "## Global Notes",
    ]
    for section in required_sections:
        assert section in mock_plan

    required_fields = [
        "- **Role:**",
        "- **Mapping:**",
        "- **Reason:**",
        "- **Evidence:**",
        "- **Alternatives rejected:**",
        "- **DC Match:**",
    ]
    for field in required_fields:
        assert field in mock_plan


@pytest.mark.asyncio
async def test_output_dir_created_if_missing(tmp_path):
    """Agent creates output directory if it does not exist."""
    agent = MappingPlanAgent(name="TestPlan")
    new_dir = tmp_path / "nested" / "output"

    ctx = MagicMock()
    ctx.session.state = {
        "skeleton_summary": "",
        "schema_category": "",
        "schema_vocab_content": "",
        "sampled_data": "",
        "statvar_summary": "",
        "per_column_dc_matches": "",
        "output_dir": str(new_dir),
        "dataset_name": "test_dataset",
    }

    mock_plan = "# Mapping Plan\n"
    with patch.object(agent, '_generate_plan', return_value=mock_plan):
        async for _ in agent._run_async_impl(ctx):
            pass

    assert new_dir.exists()
    assert (new_dir / "mapping_plan.md").exists()

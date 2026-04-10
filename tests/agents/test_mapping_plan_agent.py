import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.mapping_plan_agent import MappingPlanAgent, _plan_to_markdown
from src.api.models.plan import (
    MappingPlan, DatasetUnderstanding, ColumnMapping, StaticProperty,
    PropertyValueCandidate, CandidateSource, ColumnRole,
)


def _make_sample_plan(dataset_name: str = "test_dataset") -> MappingPlan:
    """Create a minimal valid MappingPlan for tests."""
    return MappingPlan(
        dataset_name=dataset_name,
        understanding=DatasetUnderstanding(
            archetype="Flat",
            observation_grain="one row per country per year",
            key_insight="GDP data by country and year",
        ),
        active_columns=[
            ColumnMapping(
                column_name="Year",
                role=ColumnRole.OBSERVATION_DATE,
                candidates=[
                    PropertyValueCandidate(
                        property="observationDate",
                        value_expression="[DATA]",
                        confidence=0.95,
                        source=CandidateSource.SCHEMA_VOCAB,
                        reason="Date column with yearly values",
                    ),
                ],
                selected_index=0,
                evidence="10 unique integer values: 2010-2020",
            ),
            ColumnMapping(
                column_name="Country",
                role=ColumnRole.OBSERVATION_ABOUT,
                candidates=[
                    PropertyValueCandidate(
                        property="observationAbout",
                        value_expression="[DATA]",
                        confidence=0.90,
                        source=CandidateSource.SCHEMA_ORG,
                        reason="Geographic entity column",
                    ),
                ],
                selected_index=0,
                evidence="50 unique country names",
            ),
        ],
        ignored_columns=[
            ColumnMapping(
                column_name="Notes",
                role=ColumnRole.IGNORED,
                candidates=[],
                selected_index=0,
                evidence="Constant empty column",
            ),
        ],
        static_properties=[
            StaticProperty(
                property_name="populationType",
                candidates=[
                    PropertyValueCandidate(
                        property="populationType",
                        value_expression="Country",
                        confidence=0.85,
                        source=CandidateSource.SCHEMA_VOCAB,
                        reason="GDP measures countries",
                    ),
                ],
                selected_index=0,
            ),
        ],
        global_notes=["Simple flat dataset"],
    )


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
    """Agent saves mapping plan JSON and markdown to output directory."""
    agent = MappingPlanAgent(name="TestPlan")

    ctx = MagicMock()
    ctx.session.state = {
        "skeleton_summary": "## COLUMN REFERENCE TABLE\n| Column | Type |\n| Year | int |",
        "schema_vocab_content": "{}",
        "sampled_data": "Year,Value\n2020,100",
        "statvar_summary": "",
        "candidate_pool": "{}",
        "output_dir": str(tmp_path),
        "dataset_name": "test_dataset",
    }

    sample_plan = _make_sample_plan()
    with patch.object(agent, '_generate_plan', return_value=sample_plan):
        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

    # JSON saved to state
    assert "mapping_plan" in ctx.session.state
    assert "mapping_plan_json" in ctx.session.state
    plan_data = json.loads(ctx.session.state["mapping_plan"])
    assert plan_data["dataset_name"] == "test_dataset"

    # Files saved to disk
    json_path = tmp_path / "mapping_plan.json"
    md_path = tmp_path / "mapping_plan.md"
    assert json_path.exists()
    assert md_path.exists()
    assert "test_dataset" in json_path.read_text()
    assert "# Mapping Plan: test_dataset" in md_path.read_text()


@pytest.mark.asyncio
async def test_plan_emits_events(tmp_path):
    """Agent emits at least two events (start + completion)."""
    agent = MappingPlanAgent(name="TestPlan")

    ctx = MagicMock()
    ctx.session.state = {
        "skeleton_summary": "col summary",
        "schema_vocab_content": "",
        "sampled_data": "a,b\n1,2",
        "statvar_summary": "",
        "candidate_pool": "",
        "output_dir": str(tmp_path),
        "dataset_name": "health_dataset",
    }

    sample_plan = _make_sample_plan("health_dataset")
    with patch.object(agent, '_generate_plan', return_value=sample_plan):
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
        "schema_vocab_content": "VOCAB_CONTENT",
        "sampled_data": "SAMPLED_DATA",
        "statvar_summary": "STATVAR_SUMMARY",
        "candidate_pool": '{"columns": "CANDIDATES"}',
        "output_dir": str(tmp_path),
        "dataset_name": "test_dataset",
    }

    captured_prompts = []

    async def capture_prompt(prompt, dataset_name):
        captured_prompts.append(prompt)
        return _make_sample_plan()

    with patch.object(agent, '_generate_plan', side_effect=capture_prompt):
        async for _ in agent._run_async_impl(ctx):
            pass

    assert len(captured_prompts) == 1
    prompt = captured_prompts[0]
    assert "SKELETON_CONTENT" in prompt
    assert "VOCAB_CONTENT" in prompt
    assert "SAMPLED_DATA" in prompt
    assert "STATVAR_SUMMARY" in prompt
    assert "CANDIDATES" in prompt


@pytest.mark.asyncio
async def test_missing_state_keys_use_empty_string(tmp_path):
    """Agent uses empty strings for missing optional state keys."""
    agent = MappingPlanAgent(name="TestPlan")

    ctx = MagicMock()
    ctx.session.state = {
        "output_dir": str(tmp_path),
        "dataset_name": "test_dataset",
    }

    sample_plan = _make_sample_plan()
    with patch.object(agent, '_generate_plan', return_value=sample_plan):
        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

    assert "mapping_plan" in ctx.session.state


@pytest.mark.asyncio
async def test_output_dir_created_if_missing(tmp_path):
    """Agent creates output directory if it does not exist."""
    agent = MappingPlanAgent(name="TestPlan")
    new_dir = tmp_path / "nested" / "output"

    ctx = MagicMock()
    ctx.session.state = {
        "skeleton_summary": "",
        "schema_vocab_content": "",
        "sampled_data": "",
        "statvar_summary": "",
        "candidate_pool": "",
        "output_dir": str(new_dir),
        "dataset_name": "test_dataset",
    }

    sample_plan = _make_sample_plan()
    with patch.object(agent, '_generate_plan', return_value=sample_plan):
        async for _ in agent._run_async_impl(ctx):
            pass

    assert new_dir.exists()
    assert (new_dir / "mapping_plan.json").exists()
    assert (new_dir / "mapping_plan.md").exists()


@pytest.mark.asyncio
async def test_candidate_pool_dict_serialized_to_json(tmp_path):
    """When candidate_pool is a dict in state, it gets JSON-serialized for the prompt."""
    agent = MappingPlanAgent(name="TestPlan")

    ctx = MagicMock()
    ctx.session.state = {
        "skeleton_summary": "",
        "schema_vocab_content": "",
        "sampled_data": "",
        "statvar_summary": "",
        "candidate_pool": {"Year": [{"property": "observationDate"}]},
        "output_dir": str(tmp_path),
        "dataset_name": "test_dataset",
    }

    captured_prompts = []

    async def capture_prompt(prompt, dataset_name):
        captured_prompts.append(prompt)
        return _make_sample_plan()

    with patch.object(agent, '_generate_plan', side_effect=capture_prompt):
        async for _ in agent._run_async_impl(ctx):
            pass

    prompt = captured_prompts[0]
    assert '"observationDate"' in prompt


class TestPlanToMarkdown:
    """Tests for _plan_to_markdown conversion."""

    def test_basic_structure(self):
        """Markdown has required sections."""
        plan = _make_sample_plan()
        md = _plan_to_markdown(plan)
        assert "# Mapping Plan: test_dataset" in md
        assert "## Dataset Understanding" in md
        assert "## Active Column Mappings" in md
        assert "## Ignored Columns" in md
        assert "## Static Properties" in md
        assert "## Global Notes" in md

    def test_column_names_in_backticks(self):
        """Column names are wrapped in backticks."""
        plan = _make_sample_plan()
        md = _plan_to_markdown(plan)
        assert "### Column: `Year`" in md
        assert "### Column: `Country`" in md
        assert "### Column: `Notes`" in md

    def test_selected_candidate_marked(self):
        """Selected candidate has (selected) marker."""
        plan = _make_sample_plan()
        md = _plan_to_markdown(plan)
        assert "**(selected)**" in md

    def test_ambiguous_column_flagged(self):
        """Ambiguous columns show WARNING."""
        plan = _make_sample_plan()
        plan.active_columns[0].is_ambiguous = True
        md = _plan_to_markdown(plan)
        assert "WARNING" in md

    def test_global_notes_listed(self):
        """Global notes are listed as bullet points."""
        plan = _make_sample_plan()
        md = _plan_to_markdown(plan)
        assert "- Simple flat dataset" in md

    def test_empty_plan_no_crash(self):
        """Minimal plan with no columns doesn't crash."""
        plan = MappingPlan(
            dataset_name="empty",
            understanding=DatasetUnderstanding(
                archetype="Unknown",
                observation_grain="unknown",
                key_insight="none",
            ),
            active_columns=[],
            ignored_columns=[],
            static_properties=[],
            global_notes=[],
        )
        md = _plan_to_markdown(plan)
        assert "# Mapping Plan: empty" in md

    def test_roundtrip_json_to_markdown(self):
        """Plan serialized to JSON and back produces valid markdown."""
        plan = _make_sample_plan()
        plan_json = plan.model_dump_json()
        plan2 = MappingPlan.model_validate_json(plan_json)
        md = _plan_to_markdown(plan2)
        assert "# Mapping Plan: test_dataset" in md
        assert "### Column: `Year`" in md

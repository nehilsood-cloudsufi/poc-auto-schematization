"""Unit tests for MetadataGenerationAgent."""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from src.agents.metadata_generation_agent import MetadataGenerationAgent


# ============================================================================
# Test Fixtures
# ============================================================================

SIMPLE_PVMAP = """\
key,property,value,prop2,val2,prop3,val3
State,observationAbout,{Data},,,
Year,observationDate,{Data},,,
Population,value,{Number},populationType,Person,measuredProperty,count
"""

SIMPLE_PVMAP_OUTPUT = {
    "format_detected": "raw",
    "pvmap_rows": [
        {"key": "State", "mappings": [{"property": "observationAbout", "value": "{Data}"}]},
        {"key": "Year", "mappings": [{"property": "observationDate", "value": "{Data}"}]},
        {"key": "Population", "mappings": [
            {"property": "value", "value": "{Number}"},
            {"property": "populationType", "value": "Person"},
            {"property": "measuredProperty", "value": "count"},
        ]},
    ],
    "validation_notes": "",
    "confidence": "medium",
}


@pytest.fixture
def mock_dataset(tmp_path):
    """Create mock DatasetInfo object."""
    dataset = Mock()
    dataset.name = "test_dataset"
    dataset.output_dir = tmp_path / "output"
    dataset.output_dir.mkdir(parents=True, exist_ok=True)
    dataset.input_data_files = []
    dataset.metadata_files = []
    dataset.use_metadata = False
    dataset.ground_truth_metadata = None
    return dataset


@pytest.fixture
def mock_ctx(mock_dataset):
    """Create mock InvocationContext with basic state."""
    ctx = Mock()
    ctx.session = Mock()
    ctx.session.state = {
        "pvmap_csv": SIMPLE_PVMAP,
        "current_dataset": mock_dataset,
        "attempt_number": 0,
        "data_context": {},
    }
    return ctx


@pytest.fixture
def agent():
    """Create MetadataGenerationAgent instance."""
    return MetadataGenerationAgent(name="TestMetadataGen")


# ============================================================================
# Helpers
# ============================================================================

async def collect_events(agent, ctx):
    """Collect all events from agent's async generator."""
    events = []
    async for event in agent._run_async_impl(ctx):
        events.append(event)
    return events


def run_agent(agent, ctx):
    """Run agent synchronously for testing."""
    return asyncio.get_event_loop().run_until_complete(collect_events(agent, ctx))


# ============================================================================
# Tests
# ============================================================================

class TestMetadataGenerationAgent:

    def test_generates_config_from_pvmap(self, agent, mock_ctx, tmp_path):
        """Agent reads pvmap_csv from state and writes config with deterministic params."""
        # Disable LLM enrichment by setting attempt > 0
        mock_ctx.session.state["attempt_number"] = 1

        events = run_agent(agent, mock_ctx)

        # Should have generated config
        assert mock_ctx.session.state.get("generated_config_path") is not None
        config_path = Path(mock_ctx.session.state["generated_config_path"])
        assert config_path.exists()

        # Check params
        params = mock_ctx.session.state.get("generated_config_params", {})
        assert "output_columns" in params
        # SIMPLE_PVMAP has no COLUMN:VALUE keys → low confidence →
        # mapped_rows/mapped_columns omitted for safe processor defaults
        assert "mapped_rows" not in params

    def test_merges_with_existing_metadata(self, agent, mock_ctx, mock_dataset, tmp_path):
        """When GT metadata exists, auto params merge under it (user wins)."""
        mock_ctx.session.state["attempt_number"] = 1

        # Create GT metadata
        gt_dir = tmp_path / "gt_metadata"
        gt_dir.mkdir()
        gt_meta = gt_dir / "metadata.csv"
        gt_meta.write_text("header_rows,5\n")
        mock_dataset.ground_truth_metadata = str(gt_dir)

        events = run_agent(agent, mock_ctx)

        params = mock_ctx.session.state.get("generated_config_params", {})
        # GT value should win
        assert params["header_rows"] == "5"
        # Auto-generated value should fill gaps
        assert "output_columns" in params

    def test_generates_config_from_pvmap_output_dict(self, agent, mock_ctx):
        """Agent converts pvmap_output (JSON dict) to CSV when pvmap_csv is absent."""
        mock_ctx.session.state["pvmap_csv"] = None  # Not yet set
        mock_ctx.session.state["pvmap_output"] = SIMPLE_PVMAP_OUTPUT
        mock_ctx.session.state["attempt_number"] = 0

        events = run_agent(agent, mock_ctx)

        assert mock_ctx.session.state.get("generated_config_path") is not None
        params = mock_ctx.session.state.get("generated_config_params", {})
        assert "output_columns" in params
        # SIMPLE_PVMAP_OUTPUT has no COLUMN:VALUE keys → low confidence → omitted
        assert "mapped_rows" not in params

    def test_skips_when_no_pvmap(self, agent, mock_ctx):
        """Gracefully skips when neither pvmap_csv nor pvmap_output in state."""
        mock_ctx.session.state["pvmap_csv"] = None
        mock_ctx.session.state["pvmap_output"] = None  # Also absent

        events = run_agent(agent, mock_ctx)

        assert len(events) == 1
        assert "skipping" in events[0].content.parts[0].text.lower()
        assert mock_ctx.session.state.get("generated_config_path") is None

    def test_skips_when_no_dataset(self, agent, mock_ctx):
        """Gracefully skips when current_dataset not in state."""
        mock_ctx.session.state["current_dataset"] = None

        events = run_agent(agent, mock_ctx)

        assert len(events) == 1
        assert "skipping" in events[0].content.parts[0].text.lower()

    def test_sets_state_keys(self, agent, mock_ctx):
        """Verifies generated_config_path and generated_config_params in state."""
        mock_ctx.session.state["attempt_number"] = 1

        events = run_agent(agent, mock_ctx)

        assert "generated_config_path" in mock_ctx.session.state
        assert "generated_config_params" in mock_ctx.session.state
        assert isinstance(mock_ctx.session.state["generated_config_params"], dict)

    def test_deterministic_params_always_present(self, agent, mock_ctx):
        """output_columns and header_rows always in config regardless of LLM."""
        mock_ctx.session.state["attempt_number"] = 2  # Skip LLM enrichment

        events = run_agent(agent, mock_ctx)

        params = mock_ctx.session.state.get("generated_config_params", {})
        assert "output_columns" in params
        assert "header_rows" in params
        # mapped_rows/mapped_columns only present when confidence is high
        # SIMPLE_PVMAP has no COLUMN:VALUE keys → low confidence → omitted

    def test_output_columns_exclude_statvar_props(self, agent, mock_ctx):
        """StatVar-only props (populationType, measuredProperty) NOT in output_columns."""
        mock_ctx.session.state["attempt_number"] = 1

        events = run_agent(agent, mock_ctx)

        params = mock_ctx.session.state.get("generated_config_params", {})
        cols = params.get("output_columns", "").split(",")
        assert "populationType" not in cols
        assert "measuredProperty" not in cols
        assert "observationAbout" in cols
        assert "value" in cols

    def test_regenerates_on_each_retry(self, agent, mock_ctx):
        """Config regenerated on each attempt (PVMAP changes)."""
        mock_ctx.session.state["attempt_number"] = 2

        events = run_agent(agent, mock_ctx)

        assert mock_ctx.session.state.get("generated_config_path") is not None

    def test_handles_empty_data_context(self, agent, mock_ctx):
        """Works when data_context is empty dict."""
        mock_ctx.session.state["data_context"] = {}
        mock_ctx.session.state["attempt_number"] = 1

        events = run_agent(agent, mock_ctx)

        assert mock_ctx.session.state.get("generated_config_path") is not None

    def test_no_dropped_flags_in_output(self, agent, mock_ctx):
        """Dropped flags should not appear in generated config."""
        mock_ctx.session.state["attempt_number"] = 1

        events = run_agent(agent, mock_ctx)

        params = mock_ctx.session.state.get("generated_config_params", {})
        assert "generate_statvar_name" not in params
        assert "drop_statvars_without_svobs" not in params
        assert "multi_value_properties" not in params


class TestResolveExistingMetadata:

    def test_gt_metadata_takes_priority(self, agent, mock_dataset, tmp_path):
        """Ground truth metadata is tier 1."""
        gt_dir = tmp_path / "gt_meta"
        gt_dir.mkdir()
        (gt_dir / "meta.csv").write_text("key,val\n")
        mock_dataset.ground_truth_metadata = str(gt_dir)
        mock_dataset.use_metadata = True
        mock_dataset.metadata_files = [tmp_path / "user_meta.csv"]
        (tmp_path / "user_meta.csv").write_text("key,val\n")

        result = agent._resolve_existing_metadata(mock_dataset)
        assert "gt_meta" in result

    def test_user_metadata_tier_2(self, agent, mock_dataset, tmp_path):
        """User metadata when no GT."""
        mock_dataset.ground_truth_metadata = None
        mock_dataset.use_metadata = True
        user_meta = tmp_path / "user_meta.csv"
        user_meta.write_text("key,val\n")
        mock_dataset.metadata_files = [user_meta]

        result = agent._resolve_existing_metadata(mock_dataset)
        assert result == str(user_meta)

    def test_returns_none_when_no_metadata(self, agent, mock_dataset):
        """No metadata at all → None."""
        mock_dataset.ground_truth_metadata = None
        mock_dataset.use_metadata = False
        mock_dataset.metadata_files = []

        result = agent._resolve_existing_metadata(mock_dataset)
        assert result is None

    def test_user_metadata_not_used_without_flag(self, agent, mock_dataset, tmp_path):
        """User metadata files ignored when use_metadata=False."""
        mock_dataset.ground_truth_metadata = None
        mock_dataset.use_metadata = False
        user_meta = tmp_path / "user_meta.csv"
        user_meta.write_text("key,val\n")
        mock_dataset.metadata_files = [user_meta]

        result = agent._resolve_existing_metadata(mock_dataset)
        assert result is None

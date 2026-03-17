"""Tests for NotebookLM Enrichment Agent."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.notebooklm_enrichment_agent import (
    NotebookLMEnrichmentAgent,
    _build_statvar_question,
    _build_property_question,
    _build_category_question,
    _format_enrichment,
    DEFAULT_NOTEBOOK_ID,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeSession:
    """Minimal session mock for InvocationContext."""
    def __init__(self, state: dict):
        self.state = state


class FakeContext:
    """Minimal InvocationContext mock."""
    def __init__(self, state: dict):
        self.session = FakeSession(state)


async def _collect_events(agent, ctx):
    """Run agent and collect all yielded events."""
    events = []
    async for event in agent._run_async_impl(ctx):
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Question Construction Tests
# ---------------------------------------------------------------------------

class TestQuestionConstruction:
    def test_statvar_question_with_dimensions(self):
        data_context = {
            "columns": {
                "State": {"role": "place", "sample_values": ["CA", "NY"]},
                "Year": {"role": "time", "sample_values": [2020, 2021]},
                "Age Group": {"role": "dimension", "sample_values": ["0-17", "18-64", "65+"]},
                "Count": {"role": "value", "sample_values": [1000, 2000]},
            },
            "population_type": "Person",
        }
        q = _build_statvar_question(data_context, "Demographics")
        assert "Demographics" in q
        assert "Person" in q
        assert "Age Group" in q
        assert "Count" in q

    def test_statvar_question_empty_context(self):
        q = _build_statvar_question({}, "")
        assert "General" in q
        assert "none identified" in q

    def test_property_question_with_columns(self):
        data_context = {
            "columns": {
                "FIPS": {"role": "place", "semantic_type": "FIPS_STATE", "sample_values": ["01", "02"]},
                "Year": {"role": "time", "sample_values": [2020]},
            }
        }
        q = _build_property_question(data_context)
        assert "FIPS" in q
        assert "FIPS_STATE" in q
        assert "Year" in q

    def test_property_question_empty(self):
        q = _build_property_question({})
        assert q == ""

    def test_category_question(self):
        q = _build_category_question("Health")
        assert "Health" in q
        assert "population types" in q

    def test_category_question_empty(self):
        q = _build_category_question("")
        assert "General" in q


# ---------------------------------------------------------------------------
# Format Tests
# ---------------------------------------------------------------------------

class TestFormatEnrichment:
    def test_format_with_answers(self):
        answers = [
            ("q1", "StatVar answer here"),
            ("q2", "Property answer here"),
            ("q3", "Category answer here"),
        ]
        result = _format_enrichment(answers)
        assert "### StatVar Mapping Guidance" in result
        assert "### Property Mapping Guidance" in result
        assert "### Category-Specific DC Patterns" in result
        assert "StatVar answer here" in result

    def test_format_with_partial_answers(self):
        answers = [
            ("q1", "StatVar answer"),
            ("q2", ""),
            ("q3", "Category answer"),
        ]
        result = _format_enrichment(answers)
        assert "### StatVar Mapping Guidance" in result
        assert "### Property Mapping Guidance" not in result
        assert "### Category-Specific DC Patterns" in result

    def test_format_no_answers(self):
        answers = [("q1", ""), ("q2", ""), ("q3", "")]
        result = _format_enrichment(answers)
        assert result == ""


# ---------------------------------------------------------------------------
# Agent Behavior Tests
# ---------------------------------------------------------------------------

class TestNotebookLMEnrichmentAgent:
    @pytest.mark.asyncio
    async def test_skip_when_disabled(self):
        """When nlm_enabled=False, agent should skip without API calls."""
        agent = NotebookLMEnrichmentAgent(name="TestNLM")
        ctx = FakeContext({"nlm_enabled": False})

        events = await _collect_events(agent, ctx)

        assert len(events) == 1
        assert "skipped" in events[0].content.parts[0].text.lower()
        # No state changes for enrichment
        assert "nlm_enrichment_context" not in ctx.session.state

    @pytest.mark.asyncio
    async def test_enrichment_with_existing_notebook(self):
        """Mock successful enrichment with pre-loaded notebook."""
        agent = NotebookLMEnrichmentAgent(name="TestNLM")
        ctx = FakeContext({
            "nlm_enabled": True,
            "nlm_notebook_id": "test-notebook-123",
            "data_context": {
                "columns": {
                    "State": {"role": "place", "sample_values": ["CA"]},
                    "Value": {"role": "value", "sample_values": [100]},
                },
                "population_type": "Person",
            },
            "schema_category": "Demographics",
        })

        mock_ask = AsyncMock(return_value={
            "success": True,
            "data": {"answer": "Use dcid:Count_Person for population counts.", "citation_count": 2},
            "error": "",
        })

        mock_tools = MagicMock()
        mock_tools.ask_question = mock_ask
        with patch.dict("sys.modules", {"notebooklm.tools": mock_tools, "notebooklm": MagicMock()}):
            events = await _collect_events(agent, ctx)

        assert ctx.session.state["nlm_enrichment_success"] is True
        assert "Count_Person" in ctx.session.state["nlm_enrichment_context"]
        assert ctx.session.state["nlm_notebook_id"] == "test-notebook-123"
        assert ctx.session.state["nlm_notebook_created"] is False

    @pytest.mark.asyncio
    async def test_graceful_failure_on_connection_error(self):
        """Agent should set success=False and continue when connection fails."""
        agent = NotebookLMEnrichmentAgent(name="TestNLM")
        ctx = FakeContext({
            "nlm_enabled": True,
            "nlm_notebook_id": "bad-notebook",
            "data_context": {},
            "schema_category": "",
        })

        mock_ask = AsyncMock(side_effect=Exception("Chrome CDP not available"))

        with patch.dict("sys.modules", {"notebooklm.tools": MagicMock(ask_question=mock_ask)}):
            events = await _collect_events(agent, ctx)

        assert ctx.session.state.get("nlm_enrichment_success") is False
        assert ctx.session.state.get("nlm_enrichment_context") == ""

    @pytest.mark.asyncio
    async def test_creates_notebook_when_default_fails(self):
        """If default notebook is unreachable, auto-create one."""
        agent = NotebookLMEnrichmentAgent(name="TestNLM")
        ctx = FakeContext({
            "nlm_enabled": True,
            "data_context": {"columns": {}},
            "schema_category": "Economy",
        })

        call_count = 0

        async def mock_ask(notebook_id, question):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call = test ping on default notebook → fail
                return {"success": False, "data": {}, "error": "notebook not found"}
            # Subsequent calls = actual questions on new notebook → succeed
            return {
                "success": True,
                "data": {"answer": f"Answer for: {question[:30]}", "citation_count": 1},
                "error": "",
            }

        mock_create = AsyncMock(return_value={
            "success": True,
            "data": {"notebook_id": "new-notebook-456", "name": "DC Context"},
            "error": "",
        })
        mock_add_url = AsyncMock(return_value={"success": True, "data": {}, "error": ""})

        mock_tools = MagicMock()
        mock_tools.ask_question = mock_ask
        mock_tools.create_notebook = mock_create
        mock_tools.add_url_source = mock_add_url

        with patch.dict("sys.modules", {"notebooklm.tools": mock_tools}):
            events = await _collect_events(agent, ctx)

        assert ctx.session.state["nlm_notebook_id"] == "new-notebook-456"
        assert ctx.session.state["nlm_notebook_created"] is True
        assert ctx.session.state["nlm_enrichment_success"] is True

    @pytest.mark.asyncio
    async def test_output_format_markdown(self):
        """Verify enrichment output is well-structured markdown."""
        agent = NotebookLMEnrichmentAgent(name="TestNLM")
        ctx = FakeContext({
            "nlm_enabled": True,
            "nlm_notebook_id": "test-nb",
            "data_context": {
                "columns": {"Col1": {"role": "dimension", "sample_values": ["A", "B"]}},
            },
            "schema_category": "Health",
        })

        async def mock_ask(notebook_id, question):
            return {
                "success": True,
                "data": {"answer": f"Mock answer for question", "citation_count": 1},
                "error": "",
            }

        with patch.dict("sys.modules", {"notebooklm.tools": MagicMock(ask_question=mock_ask)}):
            events = await _collect_events(agent, ctx)

        enrichment = ctx.session.state["nlm_enrichment_context"]
        assert enrichment.startswith("### ")
        assert "### StatVar Mapping Guidance" in enrichment
        assert "### Category-Specific DC Patterns" in enrichment

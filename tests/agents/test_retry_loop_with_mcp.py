"""
Tests for PVMAP retry loop with MCP integration.

Tests:
- Loop agent count (8 with MCP vs 6 without)
- Agent ordering
- Backward compatibility (no MCP)
- State key defaults in StatePreparationAgent
- MCPErrorResolverAgent skip logic
"""

import pytest
from unittest.mock import patch, MagicMock

from src.agents.pvmap_retry_loop import (
    create_pvmap_retry_loop,
    StatePreparationAgent,
    MCPErrorResolverAgent,
    MaxRetriesCheckAgent,
)


# =============================================================================
# create_pvmap_retry_loop() tests
# =============================================================================

class TestCreatePvmapRetryLoop:
    """Tests for create_pvmap_retry_loop with MCP params."""

    def test_without_mcp_7_agents(self):
        """Without MCP, loop has 7 sub-agents (with MetadataGenerator)."""
        loop = create_pvmap_retry_loop(
            model="gemini-2.5-flash",
            max_retries=3,
            enable_mcp=False,
        )

        assert len(loop.sub_agents) == 7
        agent_names = [a.name for a in loop.sub_agents]
        assert agent_names == [
            "StatePrep",
            "Generator",
            "MetadataGenerator",
            "Validator",
            "QualityEvaluator",
            "UnifiedFeedback",
            "MaxRetriesCheck",
        ]

    def test_with_mcp_10_agents(self):
        """With MCP, loop has 10 sub-agents (adds StatVarDiscovery, MCPSpotCheck, MCPErrorResolver)."""
        loop = create_pvmap_retry_loop(
            model="gemini-2.5-flash",
            max_retries=3,
            enable_mcp=True,
            mcp_url="http://localhost:3000/mcp",
        )

        assert len(loop.sub_agents) == 10
        agent_names = [a.name for a in loop.sub_agents]
        assert agent_names == [
            "StatePrep",
            "StatVarDiscovery",
            "Generator",
            "MetadataGenerator",
            "MCPSpotCheck",
            "Validator",
            "MCPErrorResolver",
            "QualityEvaluator",
            "UnifiedFeedback",
            "MaxRetriesCheck",
        ]

    def test_mcp_enabled_without_url_no_mcp_agents(self):
        """MCP enabled but no URL = no MCP agents added."""
        loop = create_pvmap_retry_loop(
            model="gemini-2.5-flash",
            enable_mcp=True,
            mcp_url=None,  # No URL
        )

        assert len(loop.sub_agents) == 7

    def test_backward_compat_no_mcp_params(self):
        """Calling without MCP params works (backward compatible)."""
        loop = create_pvmap_retry_loop(model="gemini-2.5-flash")

        assert len(loop.sub_agents) == 7

    def test_statvar_discovery_before_generator(self):
        """StatVarDiscovery is placed between StatePrep and Generator."""
        loop = create_pvmap_retry_loop(
            enable_mcp=True,
            mcp_url="http://localhost:3000/mcp",
        )

        names = [a.name for a in loop.sub_agents]
        state_idx = names.index("StatePrep")
        disc_idx = names.index("StatVarDiscovery")
        gen_idx = names.index("Generator")

        assert state_idx < disc_idx < gen_idx

    def test_error_resolver_after_validator(self):
        """MCPErrorResolver is placed after Validator and before QualityEvaluator."""
        loop = create_pvmap_retry_loop(
            enable_mcp=True,
            mcp_url="http://localhost:3000/mcp",
        )

        names = [a.name for a in loop.sub_agents]
        val_idx = names.index("Validator")
        res_idx = names.index("MCPErrorResolver")
        qual_idx = names.index("QualityEvaluator")

        assert val_idx < res_idx < qual_idx


# =============================================================================
# StatePreparationAgent MCP state defaults tests
# =============================================================================

class TestStatePrepMCPDefaults:
    """Tests for MCP-related state defaults in StatePreparationAgent."""

    @pytest.mark.asyncio
    async def test_mcp_state_defaults_set(self, mock_invocation_context):
        """StatePrep sets MCP state defaults."""
        ctx = mock_invocation_context
        ctx.session.state["current_dataset"] = MagicMock(
            name="test_ds",
            output_dir="/tmp/test",
            schema_examples=None,
            sampled_data_files=[],
            use_metadata=False,
            metadata_files=[],
        )
        ctx.session.state["attempt_number"] = -1

        agent = StatePreparationAgent(name="TestStatePrep")
        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

        assert ctx.session.state["mcp_enrichment_context"] == {}
        assert ctx.session.state["mcp_resolved_context"] == ""
        assert ctx.session.state["mcp_tools_instruction"] == ""

    @pytest.mark.asyncio
    async def test_mcp_tools_instruction_when_enabled(self, mock_invocation_context):
        """StatePrep sets MCP tools instruction when MCP enabled."""
        ctx = mock_invocation_context
        ctx.session.state["current_dataset"] = MagicMock(
            name="test_ds",
            output_dir="/tmp/test",
            schema_examples=None,
            sampled_data_files=[],
            use_metadata=False,
            metadata_files=[],
        )
        ctx.session.state["attempt_number"] = -1
        ctx.session.state["mcp_enabled"] = True

        agent = StatePreparationAgent(name="TestStatePrep")
        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

        assert "search_indicators" in ctx.session.state["mcp_tools_instruction"]
        assert "get_observations" in ctx.session.state["mcp_tools_instruction"]


# =============================================================================
# MCPErrorResolverAgent tests
# =============================================================================

class TestMCPErrorResolverAgent:
    """Tests for MCPErrorResolverAgent."""

    @pytest.mark.asyncio
    async def test_skips_when_mcp_disabled(self, mock_invocation_context):
        """Skips when MCP is not enabled."""
        ctx = mock_invocation_context
        ctx.session.state["mcp_enabled"] = False
        ctx.session.state["validation_passed"] = False

        agent = MCPErrorResolverAgent(name="TestResolver")
        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

        assert len(events) == 1
        assert "skipped" in events[0].content.parts[0].text.lower()

    @pytest.mark.asyncio
    async def test_skips_when_validation_passed(self, mock_invocation_context):
        """Skips when validation passed (no errors to resolve)."""
        ctx = mock_invocation_context
        ctx.session.state["mcp_enabled"] = True
        ctx.session.state["validation_passed"] = True

        agent = MCPErrorResolverAgent(name="TestResolver")
        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

        assert len(events) == 1
        assert "skipped" in events[0].content.parts[0].text.lower()

    @pytest.mark.asyncio
    async def test_skips_when_no_validation_error(self, mock_invocation_context):
        """Skips when no validation_error in state."""
        ctx = mock_invocation_context
        ctx.session.state["mcp_enabled"] = True
        ctx.session.state["validation_passed"] = False
        ctx.session.state["validation_error"] = ""

        agent = MCPErrorResolverAgent(name="TestResolver")
        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

        assert len(events) == 1
        assert "skipped" in events[0].content.parts[0].text.lower()

    @pytest.mark.asyncio
    async def test_runs_when_needed(self, mock_invocation_context):
        """Runs error resolution when MCP enabled and validation failed."""
        from unittest.mock import AsyncMock
        ctx = mock_invocation_context
        ctx.session.state["mcp_enabled"] = True
        ctx.session.state["validation_passed"] = False
        ctx.session.state["validation_error"] = "Key 'State' not found"
        ctx.session.state["pvmap_csv"] = "key,property,value\nState,observationAbout,dcid:geoId/{Data}"
        ctx.session.state["mcp_url"] = "http://localhost:3000/mcp"

        agent = MCPErrorResolverAgent(name="TestResolver")

        # Patch at the source module where they're imported from inside the method
        with patch("src.agents.dc_query_agent.create_error_resolver_agent") as mock_factory, \
             patch("src.agents.dc_query_agent.run_mcp_query", new_callable=AsyncMock) as mock_query:
            mock_factory.return_value = MagicMock()
            mock_query.return_value = "Resolution: Use dcid:geoId/ prefix"

            events = []
            async for event in agent._run_async_impl(ctx):
                events.append(event)

            assert ctx.session.state["mcp_resolved_context"] != ""
            assert len(events) >= 2  # "Running..." + "complete"

    @pytest.mark.asyncio
    async def test_handles_failure_gracefully(self, mock_invocation_context):
        """Handles MCP query failure gracefully."""
        ctx = mock_invocation_context
        ctx.session.state["mcp_enabled"] = True
        ctx.session.state["validation_passed"] = False
        ctx.session.state["validation_error"] = "Some error"
        ctx.session.state["pvmap_csv"] = "csv content"
        ctx.session.state["mcp_url"] = "http://localhost:3000/mcp"

        agent = MCPErrorResolverAgent(name="TestResolver")

        with patch("src.agents.dc_query_agent.create_error_resolver_agent", side_effect=Exception("MCP down")):
            events = []
            async for event in agent._run_async_impl(ctx):
                events.append(event)

            assert ctx.session.state["mcp_resolved_context"] == ""
            assert any("failed" in e.content.parts[0].text.lower() for e in events)

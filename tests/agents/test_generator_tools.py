import pytest


def test_generator_has_only_validate_tool():
    """Generator should only have validate_pvmap_property, not discovery tools."""
    from src.agents.pvmap_generator_agent import create_pvmap_generator
    agent = create_pvmap_generator(enable_mcp=False)

    tool_names = []
    for tool in agent.tools:
        if hasattr(tool, '__name__'):
            tool_names.append(tool.__name__)
        elif hasattr(tool, 'name'):
            tool_names.append(tool.name)

    assert "validate_pvmap_property" in tool_names
    assert "lookup_schemaorg_type" not in tool_names
    assert "lookup_schemaorg_property" not in tool_names
    assert "search_schemaorg_vocabulary" not in tool_names
    assert "get_schemaorg_type_hierarchy" not in tool_names


def test_generator_no_mcp_toolset_with_flag():
    """Generator should not have MCP toolset even when enable_mcp=True (moved to plan phase)."""
    from src.agents.pvmap_generator_agent import create_pvmap_generator
    # Don't pass mcp_url — just verify the MCP toolset creation block is removed
    agent = create_pvmap_generator(enable_mcp=True)

    tool_names = []
    for tool in agent.tools:
        name = getattr(tool, '__name__', getattr(tool, 'name', str(tool)))
        tool_names.append(name)

    # Should have validate + local DC tools, but NOT MCP toolset
    assert "validate_pvmap_property" in tool_names


def test_generator_no_mcp_tools_without_flag():
    """Generator should not have MCP tools when enable_mcp=False."""
    from src.agents.pvmap_generator_agent import create_pvmap_generator
    agent = create_pvmap_generator(enable_mcp=False)

    tool_names = []
    for tool in agent.tools:
        if hasattr(tool, '__name__'):
            tool_names.append(tool.__name__)

    assert "resolve_place_names" not in tool_names
    assert "validate_statvar_observation" not in tool_names

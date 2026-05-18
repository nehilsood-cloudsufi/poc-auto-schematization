import pytest
from pathlib import Path


def test_schemaorg_enrichment_agent_importable():
    """SchemaOrgEnrichmentAgent can be imported and instantiated."""
    from src.agents.schemaorg_enrichment_agent import SchemaOrgEnrichmentAgent
    agent = SchemaOrgEnrichmentAgent(name="Test")
    assert agent.name == "Test"


def test_generator_only_has_validate():
    """Generator should only have validate_pvmap_property after consolidation."""
    from src.agents.pvmap_generator_agent import create_pvmap_generator
    agent = create_pvmap_generator(enable_mcp=False)
    tool_names = [getattr(t, '__name__', getattr(t, 'name', '')) for t in agent.tools]
    assert "validate_pvmap_property" in tool_names
    assert "lookup_schemaorg_type" not in tool_names
    assert "search_schemaorg_vocabulary" not in tool_names


def test_mapping_plan_prompt_has_candidate_pool_placeholder():
    """Plan prompt template should have the candidate pool placeholder (v2 structured output)."""
    prompt = Path("src/resources/prompts/mapping_plan_prompt.txt").read_text()
    assert "{candidate_pool_json}" in prompt


def test_schemaorg_enrichment_parses_skeleton():
    """SchemaOrgEnrichmentAgent correctly parses column reference table."""
    from src.agents.schemaorg_enrichment_agent import SchemaOrgEnrichmentAgent
    agent = SchemaOrgEnrichmentAgent(name="Test")
    skeleton = """## COLUMN REFERENCE TABLE
| Column | Type | Unique | Semantic Type |
|--------|------|--------|---------------|
| GDP | float | 200 | measure |
| Country | str | 50 | place |"""
    columns = agent._parse_columns(skeleton)
    assert len(columns) == 2
    assert columns[0]["name"] == "GDP"
    assert columns[1]["name"] == "Country"
    assert columns[1]["semantic_type"] == "place"


def test_schemaorg_enrichment_produces_output():
    """SchemaOrgEnrichmentAgent produces non-empty formatted results."""
    from src.agents.schemaorg_enrichment_agent import SchemaOrgEnrichmentAgent
    agent = SchemaOrgEnrichmentAgent(name="Test")
    skeleton = """## COLUMN REFERENCE TABLE
| Column | Type | Unique | Semantic Type |
|--------|------|--------|---------------|
| value | float | 200 | measure |"""
    result = agent._enrich_columns(skeleton, "Economy")
    assert "### value" in result
    assert "Schema.org" in result or "No direct" in result


def test_pipeline_has_schemaorg_enrichment():
    """run_pipeline.py imports and adds SchemaOrgEnrichmentAgent."""
    import ast
    source = Path("src/run_pipeline.py").read_text()
    assert "SchemaOrgEnrichmentAgent" in source
    assert "SchemaOrgEnrichment" in source


def test_statvar_discovery_has_execute_method():
    """StatVarDiscoveryAgent has the _execute_per_column_queries method."""
    from src.agents.statvar_discovery_agent import StatVarDiscoveryAgent
    agent = StatVarDiscoveryAgent(name="Test")
    assert hasattr(agent, '_execute_per_column_queries')
    assert callable(agent._execute_per_column_queries)

import pytest
from unittest.mock import MagicMock, patch
from src.agents.schemaorg_enrichment_agent import SchemaOrgEnrichmentAgent


def test_agent_instantiation():
    agent = SchemaOrgEnrichmentAgent(name="TestEnrich")
    assert agent.name == "TestEnrich"


def test_parse_columns_from_skeleton():
    agent = SchemaOrgEnrichmentAgent(name="TestEnrich")
    skeleton = """## COLUMN REFERENCE TABLE
| Column | Type | Unique | Semantic Type |
|--------|------|--------|---------------|
| REF_AREA | str | 47 | place |
| TIME_PERIOD | str | 120 | date |
| OBS_VALUE | float | 890 | measure |
| FREQ | str | 3 | dimension |"""

    columns = agent._parse_columns(skeleton)
    assert len(columns) == 4
    assert columns[0]["name"] == "REF_AREA"
    assert columns[0]["semantic_type"] == "place"
    assert columns[2]["name"] == "OBS_VALUE"
    assert columns[2]["semantic_type"] == "measure"


def test_parse_empty_skeleton():
    agent = SchemaOrgEnrichmentAgent(name="TestEnrich")
    columns = agent._parse_columns("")
    assert columns == []


def test_lookup_schemaorg_for_column():
    agent = SchemaOrgEnrichmentAgent(name="TestEnrich")
    mock_vocab = MagicMock()
    mock_vocab.search_properties.return_value = [
        {"name": "addressCountry", "description": "The country", "domain": ["Place"]}
    ]
    mock_vocab.get_property.return_value = {
        "name": "addressCountry",
        "rangeIncludes": ["Country", "Text"],
    }

    result = agent._lookup_column("REF_AREA", "place", mock_vocab)
    assert "addressCountry" in result
    assert "Place" in result
    assert "Country" in result


def test_lookup_no_match_unknown_type():
    """Columns with unknown semantic type and no search results get 'No direct match'."""
    agent = SchemaOrgEnrichmentAgent(name="TestEnrich")
    mock_vocab = MagicMock()
    mock_vocab.search_properties.return_value = []

    result = agent._lookup_column("WEIRD_COLUMN_XYZ", "", mock_vocab)
    assert "No direct Schema.org match" in result


def test_lookup_known_semantic_type():
    """Columns with known semantic types (place/date/measure/dimension) get mappings."""
    agent = SchemaOrgEnrichmentAgent(name="TestEnrich")
    mock_vocab = MagicMock()
    mock_vocab.search_properties.return_value = []

    result = agent._lookup_column("COUNTRY", "place", mock_vocab)
    assert "observationAbout" in result
    assert "Schema.org equivalent" in result


def test_format_all_columns():
    agent = SchemaOrgEnrichmentAgent(name="TestEnrich")
    column_results = {
        "REF_AREA": "- Schema.org property: addressCountry (from Place)\n- Expected type: Country or Text",
        "OBS_VALUE": "- No direct Schema.org match",
    }
    formatted = agent._format_results(column_results)
    assert "### REF_AREA" in formatted
    assert "addressCountry" in formatted
    assert "### OBS_VALUE" in formatted


@pytest.mark.asyncio
async def test_agent_writes_state():
    agent = SchemaOrgEnrichmentAgent(name="TestEnrich")
    ctx = MagicMock()
    ctx.session.state = {
        "skeleton_summary": """## COLUMN REFERENCE TABLE
| Column | Type | Unique | Semantic Type |
|--------|------|--------|---------------|
| Year | int | 20 | date |""",
        "schema_category": "Economy",
    }

    with patch.object(agent, '_enrich_columns', return_value="### Year\n- Schema.org: dateCreated"):
        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

    assert "schemaorg_column_mappings" in ctx.session.state
    assert ctx.session.state["schemaorg_column_mappings"] != ""


@pytest.mark.asyncio
async def test_agent_handles_empty_skeleton():
    agent = SchemaOrgEnrichmentAgent(name="TestEnrich")
    ctx = MagicMock()
    ctx.session.state = {"skeleton_summary": "", "schema_category": ""}

    events = []
    async for event in agent._run_async_impl(ctx):
        events.append(event)

    assert ctx.session.state["schemaorg_column_mappings"] == ""

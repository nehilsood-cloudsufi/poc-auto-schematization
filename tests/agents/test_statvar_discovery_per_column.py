import pytest
from unittest.mock import AsyncMock, patch
from src.agents.statvar_discovery_agent import StatVarDiscoveryAgent


def test_build_per_column_queries():
    agent = StatVarDiscoveryAgent(name="TestDiscovery")
    skeleton = """## COLUMN REFERENCE TABLE
| Column | Type | Unique | Semantic Type |
|--------|------|--------|---------------|
| REF_AREA | str | 47 | place |
| TIME_PERIOD | str | 120 | date |
| OBS_VALUE | float | 890 | measure |
| FREQ | str | 3 | dimension |"""

    queries = agent._build_per_column_queries(skeleton)
    assert len(queries) >= 3
    column_names = [q["column"] for q in queries]
    assert "REF_AREA" in column_names
    assert "OBS_VALUE" in column_names
    assert "FREQ" in column_names
    # TIME_PERIOD is "date" type — not in measure/dimension/place
    assert "TIME_PERIOD" not in column_names


def test_build_per_column_queries_empty_skeleton():
    agent = StatVarDiscoveryAgent(name="TestDiscovery")
    queries = agent._build_per_column_queries("")
    assert queries == []


def test_format_per_column_matches_with_results():
    agent = StatVarDiscoveryAgent(name="TestDiscovery")
    matches = {
        "ASTHMA_PREV": [
            {"dcid": "Percent_Person_WithAsthma", "name": "Asthma Prevalence", "relevance": "high"}
        ],
        "REF_AREA": [],
    }
    formatted = agent._format_per_column_matches(matches)
    assert "ASTHMA_PREV" in formatted
    assert "Percent_Person_WithAsthma" in formatted
    assert "REF_AREA" in formatted
    assert "No DC matches found" in formatted


def test_format_per_column_matches_empty():
    agent = StatVarDiscoveryAgent(name="TestDiscovery")
    formatted = agent._format_per_column_matches({})
    assert "No per-column DC matches available" in formatted


def test_query_semantic_types():
    agent = StatVarDiscoveryAgent(name="TestDiscovery")
    skeleton = """## COLUMN REFERENCE TABLE
| Column | Type | Unique | Semantic Type |
|--------|------|--------|---------------|
| Country | str | 50 | place |
| GDP | float | 200 | measure |"""

    queries = agent._build_per_column_queries(skeleton)
    place_q = [q for q in queries if q["column"] == "Country"][0]
    assert place_q["semantic_type"] == "place"
    assert "place types" in place_q["query"]

    measure_q = [q for q in queries if q["column"] == "GDP"][0]
    assert measure_q["semantic_type"] == "measure"
    assert "statistical variables" in measure_q["query"]


@pytest.mark.asyncio
async def test_execute_per_column_queries():
    """Verify per-column queries are actually executed (not just built)."""
    agent = StatVarDiscoveryAgent(name="TestDiscovery")

    queries = [
        {"column": "GDP", "query": "Search for statistical variables related to: GDP", "semantic_type": "measure"},
        {"column": "Population", "query": "Search for statistical variables related to: Population", "semantic_type": "measure"},
    ]

    mock_result = "Found: Count_Person (Population count)"

    with patch('src.agents.dc_query_agent.create_enrichment_agent', return_value=None):
        with patch('src.agents.dc_query_agent.run_mcp_query', new_callable=AsyncMock, return_value=mock_result):
            with patch('src.agents.dc_query_agent.parse_statvars', return_value=[{"dcid": "Count_Person", "name": "Population"}]):
                matches = await agent._execute_per_column_queries(queries, mcp_url="http://localhost:3000/mcp", max_queries=3)

    assert "GDP" in matches
    assert "Population" in matches
    assert len(matches["Population"]) > 0
    assert matches["Population"][0]["dcid"] == "Count_Person"


@pytest.mark.asyncio
async def test_execute_per_column_queries_priority_order():
    """Measure columns should be queried before dimension columns."""
    agent = StatVarDiscoveryAgent(name="TestDiscovery")

    queries = [
        {"column": "Region", "query": "q1", "semantic_type": "place"},
        {"column": "GDP", "query": "q2", "semantic_type": "measure"},
        {"column": "Sector", "query": "q3", "semantic_type": "dimension"},
        {"column": "Revenue", "query": "q4", "semantic_type": "measure"},
    ]

    queried_columns = []

    async def mock_query(url, agent, query):
        # Track which queries were actually executed
        for q in queries:
            if q["query"] == query:
                queried_columns.append(q["column"])
        return "No results"

    with patch('src.agents.dc_query_agent.create_enrichment_agent', return_value=None):
        with patch('src.agents.dc_query_agent.run_mcp_query', side_effect=mock_query):
            with patch('src.agents.dc_query_agent.parse_statvars', return_value=[]):
                await agent._execute_per_column_queries(queries, mcp_url="http://localhost:3000/mcp", max_queries=2)

    # With max_queries=2, should query the 2 measure columns (highest priority)
    assert len(queried_columns) == 2
    assert "GDP" in queried_columns
    assert "Revenue" in queried_columns

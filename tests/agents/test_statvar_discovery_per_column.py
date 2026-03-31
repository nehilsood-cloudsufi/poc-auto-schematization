import pytest
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

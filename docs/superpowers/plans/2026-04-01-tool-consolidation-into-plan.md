# Tool Consolidation into Plan Phase — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Schema.org discovery + DC MCP discovery into the plan phase so the mapping plan contains real property data, and downstream agents only do validation.

**Architecture:** New `SchemaOrgEnrichmentAgent` (BaseAgent, programmatic) runs before plan. StatVarDiscovery enhanced with real per-column queries. Generator stripped of discovery tools, keeps validate only.

**Tech Stack:** Google ADK (BaseAgent), SchemaOrgVocab singleton (local cache), existing MCP query infrastructure

**Spec:** `docs/superpowers/specs/2026-04-01-tool-consolidation-into-plan-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `src/agents/schemaorg_enrichment_agent.py` | Programmatic Schema.org per-column lookups |
| `tests/agents/test_schemaorg_enrichment.py` | Tests for enrichment agent |

### Modified Files

| File | Changes |
|------|---------|
| `src/agents/statvar_discovery_agent.py` | Execute real per-column MCP queries (not placeholders) |
| `src/agents/pvmap_generator_agent.py` | Remove discovery tools, keep validate_pvmap_property only |
| `src/agents/mapping_plan_agent.py` | Read schemaorg_column_mappings from state |
| `src/resources/prompts/mapping_plan_prompt.txt` | Add {schemaorg_column_mappings} section |
| `src/run_pipeline.py` | Insert SchemaOrgEnrichmentAgent before MappingPlanAgent |

---

### Task 1: SchemaOrgEnrichmentAgent

**Files:**
- Create: `src/agents/schemaorg_enrichment_agent.py`
- Test: `tests/agents/test_schemaorg_enrichment.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_schemaorg_enrichment.py
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


def test_lookup_schemaorg_for_column():
    agent = SchemaOrgEnrichmentAgent(name="TestEnrich")

    # Mock SchemaOrgVocab
    mock_vocab = MagicMock()
    mock_vocab.search_properties.return_value = [
        {"name": "addressCountry", "description": "The country", "domain": ["Place"]}
    ]
    mock_vocab.get_property.return_value = {
        "name": "addressCountry",
        "rangeIncludes": ["Country", "Text"],
    }

    result = agent._lookup_column(
        column_name="REF_AREA",
        semantic_type="place",
        vocab=mock_vocab,
    )
    assert "addressCountry" in result


def test_lookup_no_match():
    agent = SchemaOrgEnrichmentAgent(name="TestEnrich")
    mock_vocab = MagicMock()
    mock_vocab.search_properties.return_value = []

    result = agent._lookup_column(
        column_name="WEIRD_COLUMN_XYZ",
        semantic_type="dimension",
        vocab=mock_vocab,
    )
    assert "No direct Schema.org match" in result


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_schemaorg_enrichment.py -x -q`
Expected: FAIL — module not found

- [ ] **Step 3: Implement SchemaOrgEnrichmentAgent**

```python
# src/agents/schemaorg_enrichment_agent.py
"""
SchemaOrgEnrichmentAgent — programmatic Schema.org per-column lookups.

Runs before MappingPlanAgent to enrich state with real Schema.org property
matches for each column. Uses the local SchemaOrgVocab cache (instant, no network).

ADK State Inputs:
    - skeleton_summary: str (column profiles from profiler)
    - schema_category: str (selected schema category)

ADK State Outputs:
    - schemaorg_column_mappings: str (formatted markdown — per-column findings)
"""

import logging
from typing import AsyncGenerator, Dict, List, Optional

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab

logger = logging.getLogger(__name__)


class SchemaOrgEnrichmentAgent(BaseAgent):
    """Programmatic Schema.org per-column lookups using local cache."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        skeleton = ctx.session.state.get("skeleton_summary", "")
        schema_category = ctx.session.state.get("schema_category", "")

        if not skeleton:
            ctx.session.state["schemaorg_column_mappings"] = ""
            yield Event(author=self.name, content=types.Content(
                parts=[types.Part(text="Schema.org enrichment skipped (no skeleton)")]
            ))
            return

        result = self._enrich_columns(skeleton, schema_category)
        ctx.session.state["schemaorg_column_mappings"] = result

        yield Event(author=self.name, content=types.Content(
            parts=[types.Part(text=f"Schema.org enrichment complete ({len(result)} chars)")]
        ))

    def _enrich_columns(self, skeleton: str, schema_category: str) -> str:
        """Run Schema.org lookups for all columns in skeleton."""
        columns = self._parse_columns(skeleton)
        if not columns:
            return ""

        vocab = SchemaOrgVocab.instance()
        column_results = {}

        for col in columns:
            result = self._lookup_column(col["name"], col["semantic_type"], vocab)
            column_results[col["name"]] = result

        return self._format_results(column_results)

    def _parse_columns(self, skeleton: str) -> List[Dict[str, str]]:
        """Parse column names and semantic types from COLUMN REFERENCE TABLE."""
        columns = []
        in_table = False

        for line in skeleton.split('\n'):
            line = line.strip()
            if 'Column' in line and 'Type' in line and '|' in line:
                in_table = True
                continue
            if in_table and line.startswith('|') and set(line.replace('|', '').strip()) <= {'-'}:
                continue
            if in_table and line.startswith('|'):
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 1:
                    col_name = parts[0]
                    semantic_type = parts[3] if len(parts) > 3 else ""
                    columns.append({"name": col_name, "semantic_type": semantic_type})
            elif in_table and not line.startswith('|'):
                in_table = False

        return columns

    def _lookup_column(self, column_name: str, semantic_type: str, vocab: SchemaOrgVocab) -> str:
        """Look up Schema.org property for a single column."""
        search_term = column_name.replace('_', ' ').lower()
        results = vocab.search_properties(search_term, limit=3)

        if not results:
            # Try semantic type as fallback
            if semantic_type == "place":
                results = vocab.search_properties("address country location", limit=3)
            elif semantic_type == "date":
                results = vocab.search_properties("date observation", limit=3)
            elif semantic_type == "measure":
                results = vocab.search_properties("value number amount", limit=3)

        if not results:
            return "- No direct Schema.org match"

        best = results[0]
        prop_name = best.get("name", "")
        domain = best.get("domain", [])
        domain_str = f" (from {', '.join(domain[:2])})" if domain else ""

        # Get range info
        prop_detail = vocab.get_property(prop_name)
        range_types = []
        if prop_detail:
            range_types = prop_detail.get("rangeIncludes", [])

        lines = [f"- Schema.org property: {prop_name}{domain_str}"]
        if range_types:
            lines.append(f"- Expected type: {' or '.join(range_types[:3])}")

        return '\n'.join(lines)

    def _format_results(self, column_results: Dict[str, str]) -> str:
        """Format all column results as markdown."""
        lines = []
        for col_name, result in column_results.items():
            lines.append(f"### {col_name}")
            lines.append(result)
            lines.append("")
        return '\n'.join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_schemaorg_enrichment.py -x -q`
Expected: All 6 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All existing tests pass

- [ ] **Step 6: Commit**

```bash
git add src/agents/schemaorg_enrichment_agent.py tests/agents/test_schemaorg_enrichment.py
git commit -m "feat: add SchemaOrgEnrichmentAgent for pre-plan Schema.org lookups"
```

---

### Task 2: Update Mapping Plan Prompt + Agent to Use Schema.org Data

**Files:**
- Modify: `src/resources/prompts/mapping_plan_prompt.txt`
- Modify: `src/agents/mapping_plan_agent.py`

- [ ] **Step 1: Add `{schemaorg_column_mappings}` section to mapping plan prompt**

In `src/resources/prompts/mapping_plan_prompt.txt`, insert after the `{sampled_data}` section and before the DC discovery section:

```text
## Schema.org Property Mappings (from automated lookup)

{schemaorg_column_mappings}

Use these Schema.org mappings in your plan. For each column, if a Schema.org match
was found above, include it in the **Schema.org** field. If no match, write "N/A".
These lookups are authoritative — do not guess Schema.org properties.
```

- [ ] **Step 2: Update MappingPlanAgent to read schemaorg_column_mappings from state**

In `src/agents/mapping_plan_agent.py`, in `_run_async_impl`, add after reading `per_column_dc`:

```python
schemaorg_mappings = ctx.session.state.get("schemaorg_column_mappings", "")
```

And add the template replacement:

```python
populated = populated.replace("{schemaorg_column_mappings}", schemaorg_mappings)
```

- [ ] **Step 3: Verify prompt has the placeholder**

Run: `grep "schemaorg_column_mappings" src/resources/prompts/mapping_plan_prompt.txt`
Expected: Shows the new section

- [ ] **Step 4: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/resources/prompts/mapping_plan_prompt.txt src/agents/mapping_plan_agent.py
git commit -m "feat: wire Schema.org enrichment data into mapping plan prompt"
```

---

### Task 3: Enhanced StatVarDiscovery — Real Per-Column MCP Queries

**Files:**
- Modify: `src/agents/statvar_discovery_agent.py`
- Test: `tests/agents/test_statvar_discovery_per_column.py` (add tests)

- [ ] **Step 1: Write the failing test**

Add to `tests/agents/test_statvar_discovery_per_column.py`:

```python
@pytest.mark.asyncio
async def test_execute_per_column_queries():
    """Verify per-column queries are actually executed (not just built)."""
    from unittest.mock import AsyncMock, patch
    agent = StatVarDiscoveryAgent(name="TestDiscovery")

    queries = [
        {"column": "GDP", "query": "Search for statistical variables related to: GDP", "semantic_type": "measure"},
        {"column": "Population", "query": "Search for statistical variables related to: Population", "semantic_type": "measure"},
    ]

    mock_result = "Found: Count_Person (Population count)"

    with patch('src.agents.statvar_discovery_agent.run_mcp_query', new_callable=AsyncMock, return_value=mock_result):
        with patch('src.agents.statvar_discovery_agent.parse_statvars', return_value=[{"dcid": "Count_Person", "name": "Population"}]):
            matches = await agent._execute_per_column_queries(queries, mcp_url="http://localhost:3000/mcp", max_queries=3)

    assert "GDP" in matches
    assert "Population" in matches
    assert len(matches["Population"]) > 0
    assert matches["Population"][0]["dcid"] == "Count_Person"
```

- [ ] **Step 2: Implement `_execute_per_column_queries` method**

Add to `StatVarDiscoveryAgent`:

```python
async def _execute_per_column_queries(
    self, queries: list, mcp_url: str, max_queries: int = 3
) -> dict:
    """
    Execute actual MCP queries for top N columns.

    Prioritizes: measure > dimension > place columns.
    Returns dict mapping column names to lists of DC match dicts.
    """
    from src.agents.dc_query_agent import (
        create_enrichment_agent, run_mcp_query, parse_statvars,
    )

    # Priority sort: measure first, then dimension, then place
    priority = {"measure": 0, "dimension": 1, "place": 2}
    sorted_queries = sorted(queries, key=lambda q: priority.get(q["semantic_type"], 9))
    top_queries = sorted_queries[:max_queries]

    matches = {q["column"]: [] for q in queries}

    for pq in top_queries:
        try:
            enrichment_agent = create_enrichment_agent(
                mcp_url=mcp_url, model=self._model, data_context={},
                attempt=0, error_feedback="", validation_error="",
            )
            result_text = await run_mcp_query(mcp_url, enrichment_agent, pq["query"])
            discovered = parse_statvars(result_text)
            matches[pq["column"]] = discovered
            logger.info("Per-column DC query for %s: found %d matches", pq["column"], len(discovered))
        except Exception as e:
            logger.warning("Per-column DC query failed for %s: %s", pq["column"], e)
            matches[pq["column"]] = []

    return matches
```

- [ ] **Step 3: Wire into `_run_async_impl`**

Replace the placeholder per-column block (around the line `per_column_matches[pq["column"]] = []`) with:

```python
# Per-column DC matches — execute real queries
skeleton = ctx.session.state.get("skeleton_summary", "")
per_column_queries = self._build_per_column_queries(skeleton)
if per_column_queries and mcp_url:
    per_column_matches = await self._execute_per_column_queries(
        per_column_queries, mcp_url=mcp_url, max_queries=3
    )
else:
    per_column_matches = {pq["column"]: [] for pq in per_column_queries}

ctx.session.state["per_column_dc_matches"] = self._format_per_column_matches(per_column_matches)
```

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_statvar_discovery_per_column.py -x -q`
Expected: All tests pass

- [ ] **Step 5: Run full suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/agents/statvar_discovery_agent.py tests/agents/test_statvar_discovery_per_column.py
git commit -m "feat: execute real per-column MCP queries in StatVarDiscoveryAgent"
```

---

### Task 4: Remove Discovery Tools from Generator

**Files:**
- Modify: `src/agents/pvmap_generator_agent.py`
- Test: `tests/agents/test_generator_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_generator_tools.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_generator_tools.py -x -q`
Expected: FAIL — generator still has all 5 Schema.org tools

- [ ] **Step 3: Modify pvmap_generator_agent.py**

Replace the imports:

```python
# BEFORE:
from src.tools.schemaorg_tools import (
    lookup_schemaorg_type,
    lookup_schemaorg_property,
    search_schemaorg_vocabulary,
    validate_pvmap_property,
    get_schemaorg_type_hierarchy,
)

# AFTER:
from src.tools.schemaorg_tools import validate_pvmap_property
```

Replace the tools block:

```python
# BEFORE:
    tools.extend([
        lookup_schemaorg_type,
        lookup_schemaorg_property,
        search_schemaorg_vocabulary,
        validate_pvmap_property,
        get_schemaorg_type_hierarchy,
    ])

# AFTER:
    tools.append(validate_pvmap_property)
```

Also remove the DC MCP toolset block:

```python
# REMOVE this entire block:
    if enable_mcp and mcp_url:
        from src.data_commons.api.mcp_toolset_factory import create_dc_mcp_toolset
        mcp_toolset = create_dc_mcp_toolset(mcp_url=mcp_url)
        tools.append(mcp_toolset)
```

Keep the local DC tools block (resolve_place_names etc.) — those are lightweight and useful.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_generator_tools.py -x -q`
Expected: Both tests PASS

- [ ] **Step 5: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/agents/pvmap_generator_agent.py tests/agents/test_generator_tools.py
git commit -m "refactor: remove Schema.org discovery + DC MCP tools from generator, keep validate only"
```

---

### Task 5: Wire SchemaOrgEnrichmentAgent into Pipeline

**Files:**
- Modify: `src/run_pipeline.py`

- [ ] **Step 1: Add SchemaOrgEnrichmentAgent to sub_agents**

In `run_pipeline.py`, after the SchemaSelectionAgent block and before the MappingPlanAgent block, add:

```python
    # Add SchemaOrgEnrichmentAgent (programmatic Schema.org lookups per column)
    from src.agents.schemaorg_enrichment_agent import SchemaOrgEnrichmentAgent
    schemaorg_agent = SchemaOrgEnrichmentAgent(name="SchemaOrgEnrichment")
    sub_agents.append(schemaorg_agent)
    logger.info("SchemaOrgEnrichmentAgent added to pipeline")
```

This should go before the `if not from_plan:` block that adds MappingPlanAgent.

- [ ] **Step 2: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add src/run_pipeline.py
git commit -m "feat: wire SchemaOrgEnrichmentAgent into pipeline before MappingPlanAgent"
```

---

### Task 6: Integration Test + Smoke Test

**Files:**
- Create: `tests/integration/test_tool_consolidation.py`

- [ ] **Step 1: Write integration tests**

```python
# tests/integration/test_tool_consolidation.py
import pytest
from pathlib import Path


def test_schemaorg_enrichment_agent_importable():
    from src.agents.schemaorg_enrichment_agent import SchemaOrgEnrichmentAgent
    agent = SchemaOrgEnrichmentAgent(name="Test")
    assert agent.name == "Test"


def test_generator_only_has_validate():
    from src.agents.pvmap_generator_agent import create_pvmap_generator
    agent = create_pvmap_generator(enable_mcp=False)
    tool_names = [getattr(t, '__name__', getattr(t, 'name', '')) for t in agent.tools]
    assert "validate_pvmap_property" in tool_names
    assert "lookup_schemaorg_type" not in tool_names


def test_mapping_plan_prompt_has_schemaorg_placeholder():
    prompt = Path("src/resources/prompts/mapping_plan_prompt.txt").read_text()
    assert "{schemaorg_column_mappings}" in prompt


def test_schemaorg_enrichment_parses_skeleton():
    from src.agents.schemaorg_enrichment_agent import SchemaOrgEnrichmentAgent
    agent = SchemaOrgEnrichmentAgent(name="Test")
    skeleton = """## COLUMN REFERENCE TABLE
| Column | Type | Unique | Semantic Type |
|--------|------|--------|---------------|
| GDP | float | 200 | measure |"""
    columns = agent._parse_columns(skeleton)
    assert len(columns) == 1
    assert columns[0]["name"] == "GDP"
```

- [ ] **Step 2: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/integration/test_tool_consolidation.py -x -q`
Expected: All PASS

- [ ] **Step 3: Smoke test on real dataset**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py \
  --dataset=bis_bis_central_bank_policy_rate \
  --plan-only --auto-approve
```

Then verify the plan contains real Schema.org data:
```bash
grep -A2 "Schema.org" output/bis_bis_central_bank_policy_rate/mapping_plan.md | head -20
```

Expected: Schema.org fields now contain actual property names instead of "N/A"

- [ ] **Step 4: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_tool_consolidation.py
git commit -m "test: add integration tests for tool consolidation"
```

---

### Task 7: A/B Test — Validate Quality with 5 Datasets

Run the consolidated pipeline (with Schema.org enrichment + generator tool removal) against the same 5 datasets used in the previous A/B test. Compare against the existing "With Plan" baseline results.

**Previous "With Plan" results (our baseline for comparison):**

| Dataset | Validation | Data Rows | PVMAP Rows | PV Acc | Time |
|---------|-----------|-----------|-----------|--------|------|
| BIS | Passed | 31 | 19 | - | 5:00 |
| FAO | Passed | 67 | 6 | 0.0% | 2:44 |
| CRDC | Passed | 3106 | 4 | 0.0% | 3:04 |
| BRFSS | Failed | 0 | 17 | 19.6% | 5:28 |
| Census SAHIE | Failed | 0 | 32 | 29.5% | 10:14 |

- [ ] **Step 1: Run all 5 datasets with consolidated pipeline**

```bash
# Create output directory
mkdir -p output/ab_test_consolidated

# Run all 5 in parallel
for ds in bis_bis_central_bank_policy_rate brfss_nchs_asthma_prevalence census_v2_sahie fao_currency_and_exchange_rate crdc_import_crdc_harassment_or_bullying india_nfhs; do
  PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py \
    --dataset=$ds \
    --output-dir=output/ab_test_consolidated \
    --auto-approve &
done
wait
```

- [ ] **Step 2: Collect results**

For each dataset, extract from the pipeline log:
- Validation passed (True/False)
- Data rows (line count of processed.csv minus 1)
- PVMAP rows (line count of generated_pvmap.csv)
- PV accuracy (from log)
- Node accuracy (from log)
- Total runtime (start timestamp → end timestamp)

```bash
for ds in bis_bis_central_bank_policy_rate brfss_nchs_asthma_prevalence census_v2_sahie fao_currency_and_exchange_rate crdc_import_crdc_harassment_or_bullying india_nfhs; do
  log=$(ls -t output/ab_test_consolidated/logs/pipeline_${ds}_*.log | head -1)
  echo "=== $ds ==="
  grep -E "Validation passed|PV accuracy|Node accuracy|Starting PVMAP|Received" "$log"
  wc -l output/ab_test_consolidated/$ds/generated_pvmap.csv output/ab_test_consolidated/$ds/processed.csv 2>/dev/null
done
```

- [ ] **Step 3: Verify Schema.org fields in plans**

For each dataset, check that the mapping plan now has real Schema.org data:

```bash
for ds in bis_bis_central_bank_policy_rate brfss_nchs_asthma_prevalence census_v2_sahie fao_currency_and_exchange_rate crdc_import_crdc_harassment_or_bullying india_nfhs; do
  echo "=== $ds ==="
  grep -c "Schema.org.*N/A" output/ab_test_consolidated/$ds/mapping_plan.md
  grep -c "Schema.org property:" output/ab_test_consolidated/$ds/mapping_plan.md
done
```

Expected: Significantly fewer "N/A" entries and more "Schema.org property:" entries compared to previous runs.

- [ ] **Step 4: Compare against previous "With Plan" results**

Build comparison table:

| Dataset | Metric | Previous (Plan) | Consolidated | Delta |
|---------|--------|-----------------|-------------|-------|
| BIS | Validation | Passed | ? | |
| BIS | Data rows | 31 | ? | |
| BIS | PV accuracy | - | ? | |
| FAO | Validation | Passed | ? | |
| FAO | Data rows | 67 | ? | |
| CRDC | Validation | Passed | ? | |
| CRDC | Data rows | 3106 | ? | |
| BRFSS | Validation | Failed | ? | |
| BRFSS | PV accuracy | 19.6% | ? | |
| Census | Validation | Failed | ? | |
| Census | PV accuracy | 29.5% | ? | |

**Pass criteria:**
- No dataset that previously passed validation should now fail
- PV accuracy should not decrease by more than 5% on any dataset
- Runtime should not increase by more than 3 min on any dataset
- Plans should have fewer "N/A" Schema.org fields

**If quality drops:** Revert to keeping discovery tools in generator (approach B from brainstorming). Add the tools back to `pvmap_generator_agent.py` alongside the plan enrichment.

- [ ] **Step 5: Document results and commit**

Save comparison results to `docs/ab_test_results/2026-04-01-tool-consolidation.md` and commit:

```bash
git add docs/ab_test_results/2026-04-01-tool-consolidation.md
git commit -m "docs: A/B test results for tool consolidation into plan phase"
```

"""
Hybrid MCP enrichment for column discovery.

Architecture: Gemini writes queries → Direct HTTP executes → Gemini interprets.
Three sources unified: Schema.org (local) + DC API (remote) + MCP (remote).

Usage:
    enrichment = await enrich_via_mcp_hybrid(data_context, verification, mcp_url)
    skeleton = enrich_skeleton_with_results(skeleton_csv, enrichment)
    reference = format_dimension_reference(enrichment)
"""

import asyncio
import csv
import io
import json
import logging
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Models for query generation and interpretation
QUERY_GEN_MODEL = "gemini-flash-latest"
INTERPRET_MODEL = "gemini-pro-latest"

# MCP search_indicators defaults
DEFAULT_SEARCH_LIMIT = 100
MAX_QUERIES = 5


# ---------------------------------------------------------------------------
# Step 1: Gemini Flash generates MCP queries
# ---------------------------------------------------------------------------

QUERY_GEN_PROMPT = """You are a Data Commons MCP query expert. Given dataset context,
generate 1-5 search_indicators queries that will discover StatVars covering ALL
dimension columns.

Dataset context:
- Population type: {population_type}
- Measurement type: {measurement_type}
- StatVar pattern: {statvar_pattern}
- Dimension columns with DC properties:
{dimension_details}
- Sample place names: {place_names}
- Already verified properties (Schema.org): {verified_properties}
- Unverified dimensions needing MCP discovery: {unverified_dims}

Rules for search_indicators queries:
- Search ONE concept per query (not "health AND education")
- Always include the population type (e.g., "Person", "Household")
- Use English place names with country (e.g., "California, USA" not "geoId/06")
- Target specific dimension properties that need DC entity discovery
- Cover ALL unverified dimensions across your queries

Output a JSON array of query objects:
[
  {{"query": "health insurance Person race", "places": ["California, USA"], "target_dimensions": ["race", "gender"]}},
  {{"query": "income poverty Person", "places": ["California, USA"], "target_dimensions": ["income"]}}
]"""


def _build_query_gen_context(
    data_context: dict,
    verification: dict,
) -> str:
    """Build compact context for Gemini Flash query generation."""
    pop_type = data_context.get("population_type", "Unknown")
    meas_type = data_context.get("measurement_type", "Unknown")
    pattern = data_context.get("statvar_pattern", "")
    dim_cols = data_context.get("dimension_columns", [])
    dim_domains = data_context.get("dimension_domains", {})
    geo = data_context.get("geography", {})

    # Build dimension details
    # Extract dc_property from skeleton_summary
    from src.pipeline.pvmap_skeleton.skeleton_generator import _extract_dc_properties
    dc_props = _extract_dc_properties(data_context.get("skeleton_summary", ""))

    dim_lines = []
    for col in dim_cols:
        dc_prop = dc_props.get(col, "unknown")
        domain = dim_domains.get(col, [])
        samples = domain[:5]
        dim_lines.append(f"  - {col} → dc_property: {dc_prop}, values: {samples}")

    # Resolve place names from geography
    place_names = _resolve_place_names(geo)

    # Get verified/unverified from Phase 2
    verified = []
    unverified = []
    for col_name, info in verification.get("columns", {}).items():
        if info.get("property_verified"):
            verified.append(f"{col_name}({info.get('verification_source', '?')})")
        elif info.get("role") == "dimension":
            unverified.append(col_name)

    return QUERY_GEN_PROMPT.format(
        population_type=pop_type,
        measurement_type=meas_type,
        statvar_pattern=pattern,
        dimension_details="\n".join(dim_lines) if dim_lines else "  (none)",
        place_names=place_names,
        verified_properties=", ".join(verified) if verified else "none",
        unverified_dims=", ".join(unverified) if unverified else "none",
    )


def _resolve_place_names(geo: dict) -> list:
    """Convert geography info to English place names for MCP queries."""
    geo_format = geo.get("format", "NAME")
    samples = geo.get("sample_values", [])[:3]

    # For US FIPS codes, use state names
    if geo_format in ("FIPS_STATE", "FIPS_COUNTY", "FIPS"):
        return ["California, USA", "New York, USA", "Texas, USA"]
    elif geo_format in ("ISO_2", "ISO_3"):
        return ["United States", "United Kingdom", "Germany"]
    elif geo_format == "NAME":
        # Use actual place names from samples
        return [f"{s}, USA" if len(s) < 20 else s for s in samples[:3]] or ["United States"]
    return ["United States"]


async def generate_mcp_queries(
    data_context: dict,
    verification: dict,
) -> List[Dict]:
    """Use Gemini Flash to generate targeted MCP queries.

    Returns list of query dicts: [{"query": str, "places": [str], "target_dimensions": [str]}]
    """
    try:
        from google import genai

        client = genai.Client()
        prompt = _build_query_gen_context(data_context, verification)

        response = client.models.generate_content(
            model=QUERY_GEN_MODEL,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        )

        queries = json.loads(response.text)
        if isinstance(queries, list):
            logger.info("Gemini Flash generated %d MCP queries", len(queries))
            return queries[:MAX_QUERIES]
        return []

    except Exception as e:
        logger.warning("Failed to generate MCP queries via Gemini: %s", e)
        # Fallback: build a basic query from P+M+C
        return _fallback_queries(data_context)


def _fallback_queries(data_context: dict) -> List[Dict]:
    """Build basic MCP queries without Gemini (fallback)."""
    pop_type = data_context.get("population_type", "Person")
    meas_type = data_context.get("measurement_type", "count")
    geo = data_context.get("geography", {})
    places = _resolve_place_names(geo)

    return [{"query": f"{meas_type} {pop_type}", "places": places, "target_dimensions": []}]


# ---------------------------------------------------------------------------
# Step 2: Direct HTTP executes queries in parallel
# ---------------------------------------------------------------------------

async def execute_mcp_queries(
    queries: List[Dict],
    mcp_url: str = "http://localhost:3000/mcp",
    search_limit: int = DEFAULT_SEARCH_LIMIT,
) -> List[Dict]:
    """Execute all MCP search_indicators queries via direct HTTP in parallel.

    Returns list of MCP response dicts (one per query).
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [
            _call_search_indicators(client, mcp_url, q, search_limit)
            for q in queries
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out errors
    valid_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning("MCP query %d failed: %s", i, result)
        elif result:
            valid_results.append(result)

    logger.info("MCP queries: %d sent, %d succeeded", len(queries), len(valid_results))
    return valid_results


async def _call_search_indicators(
    client: httpx.AsyncClient,
    mcp_url: str,
    query_spec: Dict,
    search_limit: int,
) -> Optional[Dict]:
    """Execute a single search_indicators call via HTTP."""
    try:
        resp = await client.post(
            mcp_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "search_indicators",
                    "arguments": {
                        "query": query_spec.get("query", ""),
                        "places": query_spec.get("places", ["United States"]),
                        "per_search_limit": search_limit,
                        "include_topics": False,
                    },
                },
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )

        # Parse SSE or JSON response
        content_type = resp.headers.get("content-type", "")
        if "event-stream" in content_type:
            for line in resp.text.split("\n"):
                if line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    if "result" in data:
                        for c in data["result"].get("content", []):
                            if c.get("type") == "text":
                                return json.loads(c["text"])
        else:
            data = resp.json()
            if "result" in data:
                for c in data["result"].get("content", []):
                    if c.get("type") == "text":
                        return json.loads(c["text"])

        return None

    except Exception as e:
        logger.warning("MCP HTTP call failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Step 3: Gemini Pro interprets combined results
# ---------------------------------------------------------------------------

INTERPRET_PROMPT = """You are a Data Commons schema expert. Given MCP search results
and dataset context, produce a complete dimension enrichment mapping.

MCP discovered these StatVars (DCIDs with names):
{statvar_list}

Dataset dimensions needing mapping:
{dimension_details}

Schema.org verification results:
{schema_org_results}

DC API verification results:
{dc_api_results}

For EACH dimension column, produce:
1. dc_property: The correct Data Commons property name
2. value_map: Map each raw value in the dataset to its DC entity name
3. confidence: "high" (MCP confirmed + verified), "medium" (MCP or Schema.org only), "low" (your suggestion)
4. source: "mcp", "schema_org", "dc_api", "mcp+schema_org", "llm_suggestion"

Also identify cross-column StatVar patterns from the discovered DCIDs.

For dimensions MCP couldn't resolve (age ranges, income brackets),
use your knowledge of Data Commons conventions to SUGGEST mappings.
Include format hints (e.g., "[MIN MAX Years]" for age ranges).

Output as JSON with this exact structure:
{{
  "column_mappings": {{
    "column_name": {{
      "dc_property": "property_name",
      "value_map": {{"raw_value": "dc_entity"}},
      "confidence": "high|medium|low",
      "source": "source_name"
    }}
  }},
  "cross_column_patterns": [
    {{"pattern": "Count_Person_[gender]_[race]", "confirmed": true}}
  ],
  "llm_suggestions": {{
    "column_name": {{
      "format": "format_hint",
      "examples": ["example1", "example2"],
      "note": "optional_note"
    }}
  }}
}}"""


async def interpret_mcp_results(
    mcp_results: List[Dict],
    data_context: dict,
    verification: dict,
) -> Dict:
    """Use Gemini Pro to interpret MCP results into enrichment context.

    Returns full enrichment dict with column_mappings, cross_column_patterns,
    llm_suggestions.
    """
    # Merge all MCP results
    all_variables = []
    all_mappings = {}
    for result in mcp_results:
        all_variables.extend(result.get("variables", []))
        all_mappings.update(result.get("dcid_name_mappings", {}))

    if not all_variables and not all_mappings:
        logger.info("No MCP results to interpret")
        return {"column_mappings": {}, "cross_column_patterns": [], "llm_suggestions": {}}

    # Build StatVar list for prompt
    statvar_lines = []
    for v in all_variables[:50]:  # Cap at 50 to manage tokens
        dcid = v.get("dcid", "")
        name = all_mappings.get(dcid, "")
        statvar_lines.append(f"- {dcid}: {name}")

    # Build dimension details
    dim_cols = data_context.get("dimension_columns", [])
    dim_domains = data_context.get("dimension_domains", {})
    from src.pipeline.pvmap_skeleton.skeleton_generator import _extract_dc_properties
    dc_props = _extract_dc_properties(data_context.get("skeleton_summary", ""))

    dim_lines = []
    for col in dim_cols:
        dc_prop = dc_props.get(col, "unknown")
        domain = dim_domains.get(col, [])
        dim_lines.append(f"- {col} (dc_property: {dc_prop}): raw values = {domain[:10]}")

    # Build verification summaries
    schema_org_lines = []
    dc_api_lines = []
    for col_name, info in verification.get("columns", {}).items():
        src = info.get("verification_source", "")
        verified = info.get("property_verified", False)
        if "schema_org" in src:
            schema_org_lines.append(f"- {col_name}: {info.get('property', '?')} (verified={verified})")
        if "dc_api" in src:
            dc_api_lines.append(f"- {col_name}: {info.get('property', '?')} (verified={verified})")

    prompt = INTERPRET_PROMPT.format(
        statvar_list="\n".join(statvar_lines) if statvar_lines else "(no StatVars found)",
        dimension_details="\n".join(dim_lines) if dim_lines else "(no dimensions)",
        schema_org_results="\n".join(schema_org_lines) if schema_org_lines else "(none)",
        dc_api_results="\n".join(dc_api_lines) if dc_api_lines else "(none)",
    )

    try:
        from google import genai

        client = genai.Client()
        response = client.models.generate_content(
            model=INTERPRET_MODEL,
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        )

        enrichment = json.loads(response.text)
        logger.info(
            "Gemini Pro enrichment: %d column mappings, %d patterns, %d suggestions",
            len(enrichment.get("column_mappings", {})),
            len(enrichment.get("cross_column_patterns", [])),
            len(enrichment.get("llm_suggestions", {})),
        )
        return enrichment

    except Exception as e:
        logger.warning("Gemini Pro interpretation failed: %s", e)
        return {"column_mappings": {}, "cross_column_patterns": [], "llm_suggestions": {}}


# ---------------------------------------------------------------------------
# Step 4: Modify skeleton with enrichment
# ---------------------------------------------------------------------------

def enrich_skeleton_with_results(
    skeleton_csv: str,
    enrichment: dict,
    verification: Optional[dict] = None,
) -> str:
    """Modify skeleton CSV rows using enrichment results.

    IMPORTANT: Only modifies columns that are NOT already verified by Phase 2
    (Schema.org + DC API). This prevents Gemini hallucinations from overriding
    correct property names.

    Rules:
    - NEVER overwrite a property already verified by Schema.org or DC API
    - Only overwrite empty properties or unverified ones
    - Validate suggested properties against Schema.org before applying
    - Value mappings applied only when property is correct
    """
    if not skeleton_csv or not enrichment:
        return skeleton_csv

    column_mappings = enrichment.get("column_mappings", {})
    if not column_mappings:
        return skeleton_csv

    # Build set of already-verified columns (from Phase 2)
    verified_columns = set()
    if verification:
        for col_name, info in verification.get("columns", {}).items():
            if info.get("property_verified"):
                verified_columns.add(col_name)

    # Load Schema.org vocab for validation
    schema_vocab = None
    try:
        from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab
        schema_vocab = SchemaOrgVocab.instance()
    except Exception:
        pass

    reader = csv.reader(io.StringIO(skeleton_csv))
    rows = list(reader)
    modified_rows = [rows[0]]  # Keep header
    modified_count = 0

    for row in rows[1:]:
        if not row or not row[0].strip():
            modified_rows.append(row)
            continue

        key = row[0].strip()
        # Parse COLUMN:VALUE format
        if ":" in key:
            col_name = key.split(":")[0]
            raw_value = key.split(":", 1)[1] if ":" in key else ""
        else:
            col_name = key
            raw_value = ""

        # SKIP columns already verified by Phase 2 — don't let Gemini override
        if col_name in verified_columns:
            modified_rows.append(row)
            continue

        # Check if we have enrichment for this column
        if col_name in column_mappings:
            mapping = column_mappings[col_name]
            dc_prop = mapping.get("dc_property", "")
            value_map = mapping.get("value_map", {})
            existing_prop = row[1].strip() if len(row) > 1 else ""

            row = list(row)  # Make mutable
            applied = False

            # Only set dc_property if current is empty AND suggestion is valid
            if dc_prop and not existing_prop and len(row) > 1:
                # Validate against Schema.org before applying
                if _validate_property(dc_prop, schema_vocab):
                    row[1] = dc_prop
                    applied = True
                else:
                    logger.debug(
                        "Rejected MCP suggestion '%s' for column '%s' — not in Schema.org/DC",
                        dc_prop, col_name,
                    )

            # Map raw value to DC entity (only if property is set correctly)
            if raw_value and raw_value in value_map and len(row) > 2:
                if row[1].strip():  # Only if property is set
                    row[2] = value_map[raw_value]
                    applied = True

            if applied:
                modified_count += 1

        modified_rows.append(row)

    # Write back to CSV
    output = io.StringIO()
    writer = csv.writer(output)
    for row in modified_rows:
        writer.writerow(row)

    result = output.getvalue()
    logger.info(
        "Enriched skeleton: %d rows modified (skipped %d verified columns)",
        modified_count, len(verified_columns),
    )
    return result


def _validate_property(prop_name: str, schema_vocab) -> bool:
    """Validate a property name against Schema.org + DC built-ins."""
    from src.pipeline.pvmap_skeleton.skeleton_verifier import ALWAYS_VALID_PROPERTIES

    # Check DC built-ins
    if prop_name.lower() in ALWAYS_VALID_PROPERTIES:
        return True

    # Check Schema.org
    if schema_vocab:
        if schema_vocab.get_property(prop_name) is not None:
            return True
        if hasattr(schema_vocab, 'is_known_dc_property') and schema_vocab.is_known_dc_property(prop_name):
            return True

    return False


# ---------------------------------------------------------------------------
# Step 5: Format reference section for prompt
# ---------------------------------------------------------------------------

def format_dimension_reference(enrichment: dict) -> str:
    """Build the Dimension Value Reference prompt section.

    Includes all sources with confidence levels + cross-column patterns.
    """
    if not enrichment:
        return ""

    column_mappings = enrichment.get("column_mappings", {})
    patterns = enrichment.get("cross_column_patterns", [])
    suggestions = enrichment.get("llm_suggestions", {})

    if not column_mappings and not patterns and not suggestions:
        return ""

    lines = ["## Dimension Value Reference (from Schema.org + DC API + MCP)", ""]

    # Column mappings table
    if column_mappings:
        lines.append("| Column | DC Property | Raw → DC Value | Confidence | Source |")
        lines.append("|--------|------------|----------------|------------|--------|")

        for col_name, mapping in sorted(column_mappings.items()):
            dc_prop = mapping.get("dc_property", "?")
            confidence = mapping.get("confidence", "low").upper()
            source = mapping.get("source", "?")
            value_map = mapping.get("value_map", {})

            for raw, dc_val in sorted(value_map.items()):
                lines.append(
                    f"| {col_name}:{raw} | {dc_prop} | {raw} → {dc_val} | {confidence} | {source} |"
                )

    # Cross-column patterns
    if patterns:
        lines.append("")
        lines.append("### Cross-Column StatVar Patterns")
        for p in patterns:
            confirmed = "confirmed in DC" if p.get("confirmed") else "suggested"
            lines.append(f"- `{p.get('pattern', '?')}` ({confirmed})")

    # LLM suggestions for gaps
    if suggestions:
        lines.append("")
        lines.append("### LLM Suggestions (for dimensions MCP couldn't resolve)")
        for col, info in sorted(suggestions.items()):
            fmt = info.get("format", "?")
            examples = info.get("examples", [])
            note = info.get("note", "")
            lines.append(f"- **{col}**: format=`{fmt}`, examples: {examples}")
            if note:
                lines.append(f"  Note: {note}")

    lines.append("")
    lines.append("Use HIGH confidence values exactly as shown. LOW confidence values are suggestions.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def enrich_via_mcp_hybrid(
    data_context: dict,
    verification: dict,
    mcp_url: str = "http://localhost:3000/mcp",
) -> dict:
    """One-shot hybrid MCP enrichment for skeleton column discovery.

    Orchestrates: Gemini Flash (queries) → HTTP (execute) → Gemini Pro (interpret)

    Returns:
        {
            "enrichment_success": bool,
            "column_mappings": {col: {dc_property, value_map, confidence, source}},
            "cross_column_patterns": [{pattern, confirmed}],
            "llm_suggestions": {col: {format, examples, note}},
            "mcp_call_count": int,
            "statvars_discovered": int,
        }
    """
    result = {
        "enrichment_success": False,
        "column_mappings": {},
        "cross_column_patterns": [],
        "llm_suggestions": {},
        "mcp_call_count": 0,
        "statvars_discovered": 0,
    }

    try:
        # Step 1: Generate queries
        logger.info("MCP enrichment: generating queries via Gemini Flash")
        queries = await generate_mcp_queries(data_context, verification)
        if not queries:
            logger.warning("No MCP queries generated")
            return result

        # Step 2: Execute queries
        logger.info("MCP enrichment: executing %d queries via HTTP", len(queries))
        mcp_results = await execute_mcp_queries(queries, mcp_url)
        result["mcp_call_count"] = len(queries)

        total_vars = sum(len(r.get("variables", [])) for r in mcp_results)
        result["statvars_discovered"] = total_vars
        logger.info("MCP enrichment: %d StatVars discovered", total_vars)

        # Step 3: Interpret results
        logger.info("MCP enrichment: interpreting results via Gemini Pro")
        enrichment = await interpret_mcp_results(mcp_results, data_context, verification)

        result["column_mappings"] = enrichment.get("column_mappings", {})
        result["cross_column_patterns"] = enrichment.get("cross_column_patterns", [])
        result["llm_suggestions"] = enrichment.get("llm_suggestions", {})
        result["enrichment_success"] = bool(result["column_mappings"] or result["llm_suggestions"])

        logger.info(
            "MCP enrichment complete: %d mappings, %d patterns, %d suggestions, success=%s",
            len(result["column_mappings"]),
            len(result["cross_column_patterns"]),
            len(result["llm_suggestions"]),
            result["enrichment_success"],
        )

    except Exception as e:
        logger.error("MCP enrichment failed: %s", e)

    return result

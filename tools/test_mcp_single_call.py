"""
Quick test: Can ONE MCP search_indicators call provide enough info
to map all dimension columns for a dataset?

Usage:
    # Start MCP server first:
    uv tool run datacommons-mcp serve http --port 3000

    # Then run:
    PYTHONPATH="$(pwd):$(pwd)/src" python tools/test_mcp_single_call.py
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Load .env for API keys
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


async def test_single_call():
    """Test one search_indicators call for Census SAHIE."""

    MCP_URL = os.environ.get("MCP_URL", "http://localhost:3000/mcp")

    # Load Census data context
    ctx_path = PROJECT_ROOT / "output" / "diversity_test" / "census_v2_sahie" / "data_context.json"
    if not ctx_path.exists():
        print(f"ERROR: {ctx_path} not found. Run the pipeline on census_v2_sahie first.")
        return

    with open(ctx_path) as f:
        data_context = json.load(f)

    population_type = data_context.get("population_type", "Person")
    measurement_type = data_context.get("measurement_type", "Count")
    dimension_columns = data_context.get("dimension_columns", [])
    dimension_domains = data_context.get("dimension_domains", {})
    geography = data_context.get("geography", {})

    print("=" * 60)
    print("Dataset: Census SAHIE (Health Insurance)")
    print(f"Population: {population_type}, Measurement: {measurement_type}")
    print(f"Dimensions: {dimension_columns}")
    for dim, vals in dimension_domains.items():
        print(f"  {dim}: {vals[:5]}{'...' if len(vals) > 5 else ''}")
    print(f"Geography: {geography.get('format', '?')} — {geography.get('sample_values', [])[:3]}")
    print("=" * 60)

    # Build the search query from P+M+C
    # For Census SAHIE, the topic is health insurance
    query = "health insurance Person"
    places = ["California, USA"]

    print(f"\n--- MCP Call: search_indicators ---")
    print(f"Query: {query}")
    print(f"Places: {places}")
    print(f"per_search_limit: 50")

    # Use the existing dc_query_agent pattern
    from src.agents.dc_query_agent import (
        create_enrichment_agent, run_mcp_query, parse_statvars,
        build_structured_summary,
    )

    agent = create_enrichment_agent(
        mcp_url=MCP_URL,
        model="gemini-3-flash-preview",
        data_context=data_context,
        attempt=0,
        error_feedback="",
    )

    # Run the query
    print("\nCalling MCP...")
    response = await run_mcp_query(MCP_URL, agent, query)

    if not response:
        print("ERROR: Empty response from MCP")
        return

    print(f"\nResponse length: {len(response)} chars")
    print(f"First 500 chars:\n{response[:500]}")

    # Parse StatVars
    statvars = parse_statvars(response)
    print(f"\n--- Parsed {len(statvars)} StatVars ---")

    # Extract dimension enum map from StatVar DCIDs
    dimension_enum_map = {}
    all_dcids = []

    for sv in statvars:
        dcid = sv.get("dcid", "")
        all_dcids.append(dcid)
        props = sv.get("properties", {})

        # Extract property-value pairs from the parsed properties
        for prop, val in props.items():
            prop_lower = prop.lower()
            if prop_lower in ("populationtype", "measuredproperty", "stattype"):
                continue  # Skip base properties
            if prop_lower not in dimension_enum_map:
                dimension_enum_map[prop_lower] = set()
            dimension_enum_map[prop_lower].add(val)

    print(f"\n--- Dimension Enum Map (from {len(statvars)} StatVars) ---")
    for prop, values in sorted(dimension_enum_map.items()):
        print(f"  {prop}: {sorted(values)}")

    # Also try decomposing DCIDs directly
    print(f"\n--- All Discovered DCIDs ({len(all_dcids)}) ---")
    for dcid in all_dcids[:20]:
        print(f"  {dcid}")
    if len(all_dcids) > 20:
        print(f"  ... and {len(all_dcids) - 20} more")

    # Compare with what the dataset needs
    print(f"\n--- Coverage Analysis ---")
    print(f"Dataset dimensions: {dimension_columns}")
    print(f"Skeleton dc_properties: geocat→geo, agecat→age, racecat→race, sexcat→gender, iprcat→income")
    print()

    # Check which dimension values MCP found
    needed_props = {"age", "race", "gender", "income"}
    found_props = set(dimension_enum_map.keys())
    covered = needed_props & found_props
    missing = needed_props - found_props

    print(f"Properties found by MCP: {found_props}")
    print(f"Properties needed: {needed_props}")
    print(f"Covered: {covered}")
    print(f"Missing: {missing}")

    if missing:
        print(f"\n⚠️  MCP did NOT return values for: {missing}")
        print("May need additional targeted queries for missing properties")
    else:
        print(f"\n✅ ONE CALL covered all needed dimension properties!")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"SUMMARY:")
    print(f"  MCP calls made: 1")
    print(f"  StatVars discovered: {len(statvars)}")
    print(f"  Unique dimension properties: {len(dimension_enum_map)}")
    print(f"  Total enum values: {sum(len(v) for v in dimension_enum_map.values())}")
    print(f"  Coverage: {len(covered)}/{len(needed_props)} needed properties")
    print(f"{'=' * 60}")

    # Save results for inspection
    results = {
        "query": query,
        "places": places,
        "statvars_count": len(statvars),
        "dimension_enum_map": {k: sorted(v) for k, v in dimension_enum_map.items()},
        "all_dcids": all_dcids,
        "coverage": {
            "needed": sorted(needed_props),
            "found": sorted(found_props),
            "covered": sorted(covered),
            "missing": sorted(missing),
        },
    }
    out_path = PROJECT_ROOT / "output" / "mcp_single_call_test.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    asyncio.run(test_single_call())

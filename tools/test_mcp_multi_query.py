"""
Test: How many MCP calls do we ACTUALLY need to cover all dimensions?
Try multiple query strategies.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))


async def test_queries():
    MCP_URL = os.environ.get("MCP_URL", "http://localhost:3000/mcp")

    from src.agents.dc_query_agent import (
        create_enrichment_agent, run_mcp_query, parse_statvars,
    )

    # Load Census data context
    with open(PROJECT_ROOT / "output" / "diversity_test" / "census_v2_sahie" / "data_context.json") as f:
        data_context = json.load(f)

    # Strategy: One query per dimension property
    queries = [
        ("health insurance race Person", "race"),
        ("health insurance age Person", "age"),
        ("health insurance income poverty Person", "income"),
        ("health insurance gender Person", "gender"),
    ]

    all_enum_map = {}
    all_dcids = []
    call_count = 0

    for query, target_prop in queries:
        print(f"\n--- Query: '{query}' (targeting: {target_prop}) ---")
        call_count += 1

        agent = create_enrichment_agent(
            mcp_url=MCP_URL,
            model="gemini-3-flash-preview",
            data_context=data_context,
            attempt=0,
            error_feedback="",
        )

        response = await run_mcp_query(MCP_URL, agent, query)
        if not response:
            print("  Empty response")
            continue

        statvars = parse_statvars(response)
        print(f"  Found {len(statvars)} StatVars")

        for sv in statvars:
            dcid = sv.get("dcid", "")
            all_dcids.append(dcid)
            props = sv.get("properties", {})
            for prop, val in props.items():
                prop_lower = prop.lower()
                if prop_lower in ("populationtype", "measuredproperty", "stattype"):
                    continue
                if prop_lower not in all_enum_map:
                    all_enum_map[prop_lower] = set()
                all_enum_map[prop_lower].add(val)

        # Show what this query found
        for prop, values in sorted(all_enum_map.items()):
            if any(v not in getattr(test_queries, '_seen', set()) for v in values):
                print(f"  {prop}: {sorted(values)}")

    print(f"\n{'=' * 60}")
    print(f"TOTAL: {call_count} MCP calls")
    print(f"Unique DCIDs: {len(set(all_dcids))}")
    print(f"\nFull dimension enum map:")
    for prop, values in sorted(all_enum_map.items()):
        print(f"  {prop}: {sorted(values)}")

    needed = {"age", "race", "gender", "income"}
    found = set(all_enum_map.keys())
    print(f"\nCoverage: {len(needed & found)}/{len(needed)} ({needed & found})")
    print(f"Missing: {needed - found}")

    # Save
    out = {
        "calls": call_count,
        "unique_dcids": len(set(all_dcids)),
        "dimension_enum_map": {k: sorted(v) for k, v in all_enum_map.items()},
        "coverage": {"needed": sorted(needed), "found": sorted(found & needed), "missing": sorted(needed - found)},
    }
    with open(PROJECT_ROOT / "output" / "mcp_multi_query_test.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved to output/mcp_multi_query_test.json")


if __name__ == "__main__":
    asyncio.run(test_queries())

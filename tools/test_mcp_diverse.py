"""
Test MCP single-call enrichment across diverse datasets.
Checks how many dimension properties one search_indicators call can cover.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Load .env for API keys
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


# Dataset configs: (name, query, expected_dimensions)
DATASETS = [
    ("bis_bis_central_bank_policy_rate", "central bank policy interest rate", {"frequency"}),
    ("brfss_nchs_asthma_prevalence", "asthma prevalence income", {"income", "age"}),
    ("census_v2_sahie", "health insurance Person race age", {"race", "gender", "age", "income"}),
    ("world_bank_commodity_market", "commodity price", set()),
    ("india_nfhs", "health nutrition India", {"gender", "age"}),
    ("oecd_regional_education", "education regional", set()),
    ("zurich_bev_4031_wiki", "birth population Zurich", set()),
]


async def test_dataset(name, query, expected_dims):
    MCP_URL = os.environ.get("MCP_URL", "http://localhost:3000/mcp")

    from src.agents.dc_query_agent import (
        create_enrichment_agent, run_mcp_query, parse_statvars,
    )

    # Load data context if available
    ctx_path = PROJECT_ROOT / "output" / "diversity_test" / name / "data_context.json"
    data_context = {}
    if ctx_path.exists():
        with open(ctx_path) as f:
            data_context = json.load(f)

    agent = create_enrichment_agent(
        mcp_url=MCP_URL,
        model="gemini-3-flash-preview",
        data_context=data_context,
        attempt=0,
        error_feedback="",
    )

    response = await run_mcp_query(MCP_URL, agent, query)
    if not response:
        return {"name": name, "query": query, "error": "empty response", "statvars": 0, "enum_map": {}}

    statvars = parse_statvars(response)

    enum_map = {}
    for sv in statvars:
        props = sv.get("properties", {})
        for prop, val in props.items():
            prop_lower = prop.lower()
            if prop_lower in ("populationtype", "measuredproperty", "stattype", "unit"):
                continue
            if prop_lower not in enum_map:
                enum_map[prop_lower] = set()
            enum_map[prop_lower].add(val)

    covered = expected_dims & set(enum_map.keys())
    missing = expected_dims - set(enum_map.keys())

    return {
        "name": name,
        "query": query,
        "statvars": len(statvars),
        "enum_map": {k: sorted(v) for k, v in enum_map.items()},
        "expected": sorted(expected_dims),
        "covered": sorted(covered),
        "missing": sorted(missing),
        "coverage_pct": len(covered) / len(expected_dims) * 100 if expected_dims else 100,
    }


async def main():
    print("=" * 80)
    print("MCP Single-Call Enrichment Test — Diverse Datasets")
    print("=" * 80)

    results = []
    for name, query, expected in DATASETS:
        print(f"\n--- {name} ---")
        print(f"  Query: '{query}'")
        try:
            r = await test_dataset(name, query, expected)
            results.append(r)
            print(f"  StatVars found: {r['statvars']}")
            print(f"  Properties discovered: {list(r['enum_map'].keys())}")
            for prop, vals in r['enum_map'].items():
                print(f"    {prop}: {vals[:5]}{'...' if len(vals) > 5 else ''}")
            if expected:
                print(f"  Coverage: {len(r['covered'])}/{len(expected)} ({r['coverage_pct']:.0f}%)")
                if r['missing']:
                    print(f"  Missing: {r['missing']}")
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"name": name, "error": str(e)})

    # Summary table
    print(f"\n{'=' * 80}")
    print(f"{'Dataset':<40} {'SVars':>5} {'Props':>5} {'Cover':>7} {'Missing'}")
    print("-" * 80)
    total_covered = 0
    total_expected = 0
    for r in results:
        if "error" in r and r.get("statvars", 0) == 0:
            print(f"{r['name']:<40} {'ERR':>5}")
            continue
        svars = r.get("statvars", 0)
        props = len(r.get("enum_map", {}))
        covered = len(r.get("covered", []))
        expected = len(r.get("expected", []))
        missing = r.get("missing", [])
        total_covered += covered
        total_expected += expected
        cov_str = f"{covered}/{expected}" if expected else "N/A"
        print(f"{r['name']:<40} {svars:>5} {props:>5} {cov_str:>7} {missing if missing else ''}")

    print("-" * 80)
    print(f"Total dimension coverage: {total_covered}/{total_expected} ({total_covered/total_expected*100:.0f}%)" if total_expected else "No dimensions to cover")

    # Save
    with open(PROJECT_ROOT / "output" / "mcp_diverse_test.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved to output/mcp_diverse_test.json")


if __name__ == "__main__":
    asyncio.run(main())

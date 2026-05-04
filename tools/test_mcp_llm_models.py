"""
Test MCP enrichment with different Gemini models.
Compare gemini-3.0-flash vs gemini-2.5-pro for dimension discovery.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

MCP_URL = os.environ.get("MCP_URL", "http://localhost:3000/mcp")

DATASETS = [
    ("census_v2_sahie",
     "Search for statistical variables about health insurance coverage by race, age, gender, and income for Person in California, USA. Return ALL StatVars with their property decomposition.",
     {"race", "gender", "age", "income"}),
    ("brfss_nchs_asthma_prevalence",
     "Search for statistical variables about asthma prevalence by income and age for Person in United States. Return ALL StatVars with property decomposition.",
     {"income", "age"}),
    ("india_nfhs",
     "Search for statistical variables about health nutrition demographics gender age in India. Return ALL StatVars.",
     {"gender", "age"}),
    ("bis_bis_central_bank_policy_rate",
     "Search for statistical variables about central bank policy interest rate frequency. Return ALL StatVars.",
     {"frequency"}),
]


async def test_model(model_name, query, data_context):
    """Test a single model with enrichment agent."""
    from src.agents.dc_query_agent import create_enrichment_agent, run_mcp_query, parse_statvars

    agent = create_enrichment_agent(
        mcp_url=MCP_URL,
        model=model_name,
        data_context=data_context,
        attempt=0,
        error_feedback="",
    )

    response = await run_mcp_query(MCP_URL, agent, query)
    if not response:
        return {"statvars": 0, "dim_map": {}, "response_len": 0, "error": "empty"}

    statvars = parse_statvars(response)
    dim_map = {}
    for sv in statvars:
        for prop, val in sv.get("properties", {}).items():
            pl = prop.lower()
            if pl in ("populationtype", "measuredproperty", "stattype", "unit"):
                continue
            if pl not in dim_map:
                dim_map[pl] = set()
            dim_map[pl].add(val)

    return {
        "statvars": len(statvars),
        "dim_map": {k: sorted(v) for k, v in dim_map.items()},
        "response_len": len(response),
    }


async def main():
    models = ["gemini-3.0-flash", "gemini-2.5-pro-preview-06-05"]

    print("=" * 90)
    print("MCP LLM Agent: gemini-3.0-flash vs gemini-2.5-pro")
    print("=" * 90)

    for ds_name, query, expected in DATASETS:
        # Load data context
        ctx_path = PROJECT_ROOT / "output" / "diversity_test" / ds_name / "data_context.json"
        data_context = {}
        if ctx_path.exists():
            with open(ctx_path) as f:
                data_context = json.load(f)

        print(f"\n{'─' * 90}")
        print(f"Dataset: {ds_name} | Expected dims: {sorted(expected)}")

        for model in models:
            print(f"\n  [{model}]")
            try:
                result = await test_model(model, query, data_context)
                svars = result["statvars"]
                dims = result["dim_map"]
                found = set(dims.keys())
                covered = expected & found
                missing = expected - found

                print(f"    StatVars: {svars}, Response: {result['response_len']} chars")
                for prop, vals in sorted(dims.items()):
                    shown = vals[:4]
                    extra = f" +{len(vals)-4}" if len(vals) > 4 else ""
                    print(f"    {prop}: {shown}{extra}")
                print(f"    Coverage: {len(covered)}/{len(expected)} | Missing: {sorted(missing) if missing else 'none'}")
            except Exception as e:
                print(f"    ERROR: {str(e)[:120]}")

    print(f"\n{'=' * 90}")


if __name__ == "__main__":
    asyncio.run(main())

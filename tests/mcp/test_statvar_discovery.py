#!/usr/bin/env python3
"""Test StatVarDiscoveryAgent.

This tests the new StatVarDiscoveryAgent that queries MCP for existing
Data Commons StatVars before PVMAP generation.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env", override=True)

# Ensure GOOGLE_API_KEY is set from GEMINI_API_KEY
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")


def test_statvar_discovery():
    """Test StatVarDiscoveryAgent with MCP."""
    from src.data_commons.api.mcp_server_manager import MCPServerManager
    from src.agents.statvar_discovery_agent import StatVarDiscoveryAgent
    from src.agents.discovery_agent import DiscoveryAgent
    from google.adk import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    import uuid
    import asyncio

    port = int(os.getenv("MCP_PORT", "3000"))

    print(f"Starting MCP server on port {port}...")
    with MCPServerManager(port=port) as mcp:
        print(f"MCP server running at {mcp.mcp_url}")

        # Discover a test dataset
        input_dir = PROJECT_ROOT / "input"
        discovery = DiscoveryAgent(name="Discovery")

        # Find first available dataset
        dataset_dirs = [d for d in input_dir.iterdir() if d.is_dir()]
        if not dataset_dirs:
            print("No datasets found in input/")
            return False

        dataset_name = dataset_dirs[0].name
        print(f"\nUsing dataset: {dataset_name}")

        dataset = discovery._discover_single_dataset(
            input_dir / dataset_name,
            dataset_name
        )

        # Read sampled data content
        sampled_data_content = ""
        if dataset.combined_sampled_data and Path(dataset.combined_sampled_data).exists():
            with open(dataset.combined_sampled_data, 'r') as f:
                sampled_data_content = f.read()

        # Read metadata content
        metadata_content = ""
        if dataset.combined_metadata and Path(dataset.combined_metadata).exists():
            with open(dataset.combined_metadata, 'r') as f:
                metadata_content = f.read()

        print(f"Sampled data preview:\n{sampled_data_content[:200]}...")
        print(f"Metadata preview:\n{metadata_content[:200]}...")

        # Create agent
        agent = StatVarDiscoveryAgent(name="TestDiscovery")

        # Create runner - use 'agents' app_name for consistency
        runner = Runner(
            app_name="agents",
            agent=agent,
            session_service=InMemorySessionService(),
            auto_create_session=True
        )

        # Set up initial state
        session_id = f"test_{uuid.uuid4().hex[:8]}"

        async def setup_state():
            session = await runner.session_service.create_session(
                app_name="agents",
                user_id="test",
                state={
                    "current_dataset": dataset,
                    "mcp_enabled": True,
                    "mcp_url": mcp.mcp_url,
                    "sampled_data_content": sampled_data_content,
                    "metadata_content": metadata_content
                },
                session_id=session_id
            )
            return session

        asyncio.run(setup_state())

        # Run discovery
        print("\nRunning StatVar discovery...")
        msg = types.Content(parts=[types.Part(text="Discover StatVars")])
        events = list(runner.run(user_id="test", session_id=session_id, new_message=msg))

        print(f"\nEvents received: {len(events)}")
        discovered_something = False
        for e in events:
            if e.content:
                for part in e.content.parts:
                    if hasattr(part, 'text'):
                        print(f"  {part.text}")
                        if "Discovered" in part.text and "StatVars" in part.text:
                            discovered_something = True

        # Check state via internal storage
        stored_session = runner.session_service.sessions.get("agents", {}).get("test", {}).get(session_id)
        state = dict(stored_session.state) if stored_session else {}

        print(f"\nDiscovered StatVars: {state.get('discovered_statvars', [])}")
        print(f"Discovery success: {state.get('discovery_success')}")
        print(f"StatVar summary length: {len(state.get('statvar_summary', ''))}")

        if state.get('statvar_summary'):
            print(f"\nStatVar summary preview:\n{state.get('statvar_summary', '')[:500]}...")

        # Return True if we got through without exceptions (MCP working)
        # The actual discovery may or may not find StatVars depending on the dataset
        return discovered_something or state.get('discovery_success', False)


def test_without_mcp():
    """Test that StatVarDiscoveryAgent gracefully handles MCP disabled."""
    from src.agents.statvar_discovery_agent import StatVarDiscoveryAgent
    from src.agents.discovery_agent import DiscoveryAgent
    from google.adk import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    import uuid
    import asyncio

    print("\n" + "=" * 60)
    print("Testing StatVarDiscoveryAgent with MCP DISABLED")
    print("=" * 60)

    input_dir = PROJECT_ROOT / "input"
    discovery = DiscoveryAgent(name="Discovery")

    # Find first available dataset
    dataset_dirs = [d for d in input_dir.iterdir() if d.is_dir()]
    if not dataset_dirs:
        print("No datasets found in input/")
        return False

    dataset_name = dataset_dirs[0].name
    dataset = discovery._discover_single_dataset(
        input_dir / dataset_name,
        dataset_name
    )

    # Create agent
    agent = StatVarDiscoveryAgent(name="TestDiscovery")

    # Create runner - use 'agents' app_name for consistency
    runner = Runner(
        app_name="agents",
        agent=agent,
        session_service=InMemorySessionService(),
        auto_create_session=True
    )

    session_id = f"test_{uuid.uuid4().hex[:8]}"

    async def setup_state():
        session = await runner.session_service.create_session(
            app_name="agents",
            user_id="test",
            state={
                "current_dataset": dataset,
                "mcp_enabled": False,  # MCP disabled
            },
            session_id=session_id
        )
        return session

    asyncio.run(setup_state())

    # Run discovery
    print("Running StatVar discovery (MCP disabled)...")
    msg = types.Content(parts=[types.Part(text="Discover StatVars")])
    events = list(runner.run(user_id="test", session_id=session_id, new_message=msg))

    # Validate via event output (more reliable than session state in ADK)
    found_skip_message = False
    for e in events:
        if e.content:
            for part in e.content.parts:
                if hasattr(part, 'text'):
                    print(f"  {part.text}")
                    if "skipped" in part.text.lower() and "MCP not enabled" in part.text:
                        found_skip_message = True

    # Check state via internal storage (ADK's get_session returns stale state)
    stored_session = runner.session_service.sessions.get("agents", {}).get("test", {}).get(session_id)
    state = dict(stored_session.state) if stored_session else {}
    print(f"Discovery success: {state.get('discovery_success')}")
    print(f"Discovered StatVars: {state.get('discovered_statvars', [])}")

    # Validate behavior via event output
    assert found_skip_message, "Expected skip message not found in events"
    print("PASSED: MCP disabled handled correctly")

    return True


def test_prompt_injection():
    """Test that discovered StatVars are injected into the prompt."""
    from src.agents.pvmap_generation.helpers import build_prompt_with_feedback
    from pathlib import Path

    print("\n" + "=" * 60)
    print("Testing prompt injection with discovered StatVars")
    print("=" * 60)

    template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "improved_pvmap_prompt.txt"
    if not template_path.exists():
        print(f"Template not found: {template_path}")
        return False

    # Test with EXACT match discovered StatVars (should be injected)
    discovered_statvars = """- DCID: Count_Person
  Description: Total population count
  Match confidence: HIGH
- DCID: UnemploymentRate_Person
  Description: Unemployment rate for persons
  Match confidence: HIGH"""

    prompt = build_prompt_with_feedback(
        template_path=template_path,
        schema_content="Test schema content",
        sampled_data_content="col1,col2\nval1,val2",
        metadata_content="param,value\nname,test",
        error_feedback=None,
        discovered_statvars=discovered_statvars
    )

    # Check that StatVars section was injected
    assert "EXISTING DATA COMMONS VARIABLES" in prompt, "Missing StatVars section"
    assert "Count_Person" in prompt, "Missing Count_Person DCID"
    assert "IGNORE them" in prompt, "Missing warning to ignore non-matching variables"

    print("PASSED: Exact match StatVars injected into prompt correctly")

    # Test without discovered StatVars
    prompt_no_statvars = build_prompt_with_feedback(
        template_path=template_path,
        schema_content="Test schema content",
        sampled_data_content="col1,col2\nval1,val2",
        metadata_content="param,value\nname,test",
        error_feedback=None,
        discovered_statvars=None
    )

    assert "EXISTING DATA COMMONS VARIABLES" not in prompt_no_statvars
    print("PASSED: No StatVars section when none discovered")

    # Test with "not found" StatVars (should NOT be injected)
    not_found_statvars = """The specific BIS Central Bank Policy Rate variables were not found in Data Commons.
However, related interest rate variables are available:
- DCID: worldBank/FR_INR_LEND
  Description: Lending interest rate"""

    prompt_not_found = build_prompt_with_feedback(
        template_path=template_path,
        schema_content="Test schema content",
        sampled_data_content="col1,col2\nval1,val2",
        metadata_content="param,value\nname,test",
        error_feedback=None,
        discovered_statvars=not_found_statvars
    )

    assert "EXISTING DATA COMMONS VARIABLES" not in prompt_not_found, \
        "StatVars section should NOT be injected when variables 'not found'"
    print("PASSED: 'Not found' StatVars correctly filtered out")

    # Test with "no exact matches" (should NOT be injected)
    no_matches_statvars = """No exact matches found for this dataset.
Related variables that may be of interest:
- DCID: someVariable
  Description: Some description"""

    prompt_no_matches = build_prompt_with_feedback(
        template_path=template_path,
        schema_content="Test schema content",
        sampled_data_content="col1,col2\nval1,val2",
        metadata_content="param,value\nname,test",
        error_feedback=None,
        discovered_statvars=no_matches_statvars
    )

    assert "EXISTING DATA COMMONS VARIABLES" not in prompt_no_matches, \
        "StatVars section should NOT be injected when 'no exact matches'"
    print("PASSED: 'No exact matches' StatVars correctly filtered out")

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("StatVar Discovery Agent Tests")
    print("=" * 60)

    # Test 1: Prompt injection (no MCP needed)
    test1_passed = test_prompt_injection()

    # Test 2: MCP disabled handling
    test2_passed = test_without_mcp()

    # Test 3: Full MCP test (requires MCP server)
    print("\n" + "=" * 60)
    print("Testing StatVarDiscoveryAgent with MCP ENABLED")
    print("=" * 60)

    try:
        test3_passed = test_statvar_discovery()
    except Exception as e:
        print(f"MCP test failed: {e}")
        test3_passed = False

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Prompt injection test: {'PASSED' if test1_passed else 'FAILED'}")
    print(f"MCP disabled test: {'PASSED' if test2_passed else 'FAILED'}")
    print(f"Full MCP test: {'PASSED' if test3_passed else 'FAILED'}")

    sys.exit(0 if all([test1_passed, test2_passed, test3_passed]) else 1)

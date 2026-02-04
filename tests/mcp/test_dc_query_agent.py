#!/usr/bin/env python3
"""
DC Query Agent Test

Tests the full DC Query Agent pattern that will be used in the pipeline.
This demonstrates:
1. Creating an agent with MCP tools for Data Commons queries
2. Running queries to discover StatVars
3. Fetching observations for known variables

Based on:
https://github.com/datacommonsorg/agent-toolkit/blob/main/notebooks/datacommons_mcp_tools_with_custom_agent.ipynb

Usage:
    python mcp-testing/test_dc_query_agent.py
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env and set GOOGLE_API_KEY for ADK
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env", override=True)

# ADK uses GOOGLE_API_KEY, map from GEMINI_API_KEY if needed
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

import requests


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print test result with formatting."""
    status = "[PASS]" if passed else "[FAIL]"
    msg = f"{status} {test_name}"
    if details:
        msg += f" - {details}"
    print(msg)
    return passed


class MCPServerContext:
    """Context manager to start/stop MCP server for tests."""

    def __init__(self, port: int = 3000):
        self.port = port
        self.base_url = f"http://localhost:{port}"
        self.process = None

    def __enter__(self):
        env = os.environ.copy()

        # Find datacommons-mcp executable
        venv_executable = PROJECT_ROOT / "venv" / "bin" / "datacommons-mcp"
        if venv_executable.exists():
            dc_mcp_cmd = str(venv_executable)
        else:
            dc_mcp_cmd = "datacommons-mcp"

        cmd = [dc_mcp_cmd, "serve", "http", "--port", str(self.port)]

        # Use DEVNULL instead of PIPE to avoid buffer deadlock
        # The MCP server outputs lots of content (ASCII banner, info messages)
        # which can fill the pipe buffer and cause the process to block
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env
        )

        start_time = time.time()
        while time.time() - start_time < 30:
            if self.process.poll() is not None:
                raise RuntimeError(f"MCP server died with exit code: {self.process.returncode}")

            try:
                resp = requests.get(f"{self.base_url}/health", timeout=2)
                if resp.status_code == 200:
                    return self
            except requests.RequestException:
                pass

            time.sleep(1)

        raise RuntimeError("MCP server failed to start")

    def __exit__(self, *args):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    @property
    def mcp_url(self) -> str:
        return f"{self.base_url}/mcp"


def create_dc_query_agent(mcp_url: str, model: str = "gemini-2.5-pro"):
    """
    Create a Data Commons Query Agent with MCP tools.

    This is the pattern we'll use in src/agents/dc_query_agent.py

    Args:
        mcp_url: URL of the MCP server endpoint
        model: Gemini model to use (default: gemini-2.0-flash for speed)

    Returns:
        Configured LlmAgent with MCP tools
    """
    from google.adk.agents import LlmAgent
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

    mcp_toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=mcp_url)
    )

    agent = LlmAgent(
        name="DCQueryAgent",
        model=model,
        instruction="""You are a Data Commons expert assistant. Your role is to help users
discover and query statistical data from the Data Commons knowledge graph.

You have access to two MCP tools:

1. **search_indicators**: Search for statistical variables (StatVars) and topics
   - Use this to find what variables are available for a given topic or place
   - Parameters: query (required), places (optional), parent_place (optional)
   - Example: Search for "population" indicators for "California"

2. **get_observations**: Fetch actual statistical data
   - Use this AFTER finding valid DCIDs from search_indicators
   - Parameters: variable_dcid (required), place_dcid (required), date (optional)
   - Example: Get observations for Count_Person in geoId/06 (California)

**IMPORTANT WORKFLOW**:
1. Always call search_indicators FIRST to discover valid variable DCIDs
2. Then use those DCIDs with get_observations to fetch data
3. Never guess DCIDs - always discover them through search first

When responding:
- Report the exact DCIDs and values you found
- Be concise but include key data points
- If a query returns no results, suggest alternative searches
""",
        tools=[mcp_toolset]
    )

    return agent


async def test_statvar_discovery(mcp_url: str) -> bool:
    """Test discovering StatVars for a dataset topic."""
    all_passed = True

    try:
        from google.adk import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
        import uuid

        agent = create_dc_query_agent(mcp_url)
        runner = Runner(
            app_name="dc_test",
            agent=agent,
            session_service=InMemorySessionService(),
            auto_create_session=True
        )

        # Test: Search for population variables
        print("\n  Query: Find population-related indicators for California")

        session_id = f"discovery_{uuid.uuid4().hex[:8]}"
        user_message = types.Content(
            parts=[types.Part(text="""
Search for population indicators available for California, USA.
Use the search_indicators tool with query "population" and places "California, USA".
Report the variable DCIDs you find.
""")]
        )

        result_text = ""
        for event in runner.run(
            user_id="test_user",
            session_id=session_id,
            new_message=user_message
        ):
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        result_text += part.text

        if "Count_Person" in result_text or "population" in result_text.lower():
            all_passed &= print_result("StatVar discovery found population variables", True)
        else:
            all_passed &= print_result("StatVar discovery found population variables", False,
                                      f"Response didn't contain expected variables: {result_text[:200]}")

        # Save result for inspection
        output_dir = PROJECT_ROOT / "mcp-testing" / "sample_output"
        output_dir.mkdir(exist_ok=True)
        with open(output_dir / "statvar_discovery_result.txt", "w") as f:
            f.write(result_text)
        print(f"  Result saved to: {output_dir / 'statvar_discovery_result.txt'}")

        return all_passed

    except Exception as e:
        import traceback
        traceback.print_exc()
        return print_result("StatVar discovery test", False, str(e))


async def test_observation_fetch(mcp_url: str) -> bool:
    """Test fetching observations for known StatVars."""
    all_passed = True

    try:
        from google.adk import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
        import uuid

        agent = create_dc_query_agent(mcp_url)
        runner = Runner(
            app_name="dc_test",
            agent=agent,
            session_service=InMemorySessionService(),
            auto_create_session=True
        )

        # Test: Get population data for California
        print("\n  Query: Get population observations for California")

        session_id = f"obs_{uuid.uuid4().hex[:8]}"
        user_message = types.Content(
            parts=[types.Part(text="""
Get the population count for California (geoId/06).
First search for the population count variable, then get observations for the most recent year available.
Report the value and date.
""")]
        )

        result_text = ""
        for event in runner.run(
            user_id="test_user",
            session_id=session_id,
            new_message=user_message
        ):
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        result_text += part.text

        # Check if we got actual data
        if any(char.isdigit() for char in result_text):
            all_passed &= print_result("Observation fetch returned data", True)
        else:
            all_passed &= print_result("Observation fetch returned data", False,
                                      "No numeric data in response")

        # Save result
        output_dir = PROJECT_ROOT / "mcp-testing" / "sample_output"
        with open(output_dir / "observation_fetch_result.txt", "w") as f:
            f.write(result_text)
        print(f"  Result saved to: {output_dir / 'observation_fetch_result.txt'}")

        return all_passed

    except Exception as e:
        import traceback
        traceback.print_exc()
        return print_result("Observation fetch test", False, str(e))


async def test_pipeline_relevant_query(mcp_url: str) -> bool:
    """Test a query relevant to the PVMAP pipeline use case."""
    all_passed = True

    try:
        from google.adk import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
        import uuid

        agent = create_dc_query_agent(mcp_url)
        runner = Runner(
            app_name="dc_test",
            agent=agent,
            session_service=InMemorySessionService(),
            auto_create_session=True
        )

        # Test: Search for GDP/economic indicators (common in PVMAP datasets)
        print("\n  Query: Find economic indicators (GDP) for countries")

        session_id = f"pipeline_{uuid.uuid4().hex[:8]}"
        user_message = types.Content(
            parts=[types.Part(text="""
Search for GDP (Gross Domestic Product) indicators available in Data Commons.
What variables are available for measuring economic output at the country level?
List the variable DCIDs and their descriptions.
""")]
        )

        result_text = ""
        for event in runner.run(
            user_id="test_user",
            session_id=session_id,
            new_message=user_message
        ):
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        result_text += part.text

        # Check if we found economic indicators
        if "GDP" in result_text or "Amount_Economic" in result_text or "economic" in result_text.lower():
            all_passed &= print_result("Economic indicator discovery", True)
        else:
            all_passed &= print_result("Economic indicator discovery", False,
                                      "No economic indicators found")

        # Save result
        output_dir = PROJECT_ROOT / "mcp-testing" / "sample_output"
        with open(output_dir / "economic_indicators_result.txt", "w") as f:
            f.write(result_text)
        print(f"  Result saved to: {output_dir / 'economic_indicators_result.txt'}")

        return all_passed

    except Exception as e:
        import traceback
        traceback.print_exc()
        return print_result("Pipeline-relevant query test", False, str(e))


async def run_tests():
    """Run all DC Query Agent tests."""
    print("=" * 60)
    print("DC Query Agent Test")
    print("=" * 60)
    print()

    all_passed = True
    port = int(os.getenv("MCP_PORT", "3000"))

    # Verify prerequisites
    try:
        import datacommons_mcp
        from google.adk.agents import LlmAgent
        from google.adk.tools.mcp_tool import McpToolset
        print_result("All imports successful", True)
    except ImportError as e:
        print_result("Import check", False, str(e))
        return False

    # Check API keys
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
        print_result("GEMINI_API_KEY required", False)
        return False

    if not os.getenv("DC_API_KEY"):
        print_result("DC_API_KEY required", False, "Get from https://apikeys.datacommons.org/")
        return False

    print_result("API keys configured", True)
    print()

    print(f"Starting MCP server on port {port}...")
    print("-" * 40)

    try:
        with MCPServerContext(port=port) as mcp:
            print_result("MCP server running", True)

            # Test 1: StatVar Discovery
            print("\nTest 1: StatVar Discovery")
            print("-" * 40)
            all_passed &= await test_statvar_discovery(mcp.mcp_url)

            # Test 2: Observation Fetch
            print("\nTest 2: Observation Fetch")
            print("-" * 40)
            all_passed &= await test_observation_fetch(mcp.mcp_url)

            # Test 3: Pipeline-relevant Query
            print("\nTest 3: Pipeline-relevant Query")
            print("-" * 40)
            all_passed &= await test_pipeline_relevant_query(mcp.mcp_url)

    except Exception as e:
        print_result("MCP server startup", False, str(e))
        all_passed = False

    # Summary
    print()
    print("=" * 60)
    if all_passed:
        print("All tests passed!")
        print("\nThe DC Query Agent is ready for pipeline integration.")
        print("\nSample outputs saved to: mcp-testing/sample_output/")
    else:
        print("Some tests failed. See above for details.")
    print("=" * 60)

    return all_passed


def main():
    """Entry point."""
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

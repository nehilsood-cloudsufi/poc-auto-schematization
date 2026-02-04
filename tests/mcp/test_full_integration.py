#!/usr/bin/env python3
"""
Full Integration Test

Tests that all MCP integration components work together:
1. Imports work correctly
2. MCPServerManager can be used from the API module
3. DC Query Agent can be created from the agents module
4. Pipeline coordinator accepts MCP parameters

Usage:
    python mcp-testing/test_full_integration.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env and set GOOGLE_API_KEY for ADK
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env", override=True)

# ADK uses GOOGLE_API_KEY, map from GEMINI_API_KEY if needed
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print test result with formatting."""
    status = "[PASS]" if passed else "[FAIL]"
    msg = f"{status} {test_name}"
    if details:
        msg += f" - {details}"
    print(msg)
    return passed


def test_api_imports():
    """Test that API module imports work."""
    print("\nTest 1: API Module Imports")
    print("-" * 40)
    all_passed = True

    try:
        from src.data_commons.api import (
            GeminiClient,
            MCPServerManager,
            create_dc_mcp_toolset,
            MCP_AVAILABLE
        )

        all_passed &= print_result("GeminiClient import", GeminiClient is not None)
        all_passed &= print_result("MCPServerManager import", MCPServerManager is not None)
        all_passed &= print_result("create_dc_mcp_toolset import", create_dc_mcp_toolset is not None)
        all_passed &= print_result("MCP_AVAILABLE flag", MCP_AVAILABLE == True)

    except ImportError as e:
        all_passed &= print_result("API imports", False, str(e))

    return all_passed


def test_agent_imports():
    """Test that agent module imports work."""
    print("\nTest 2: Agent Module Imports")
    print("-" * 40)
    all_passed = True

    try:
        from src.agents import (
            DiscoveryAgent,
            SamplingAgent,
            PVMAPGenerationAgent,
            EvaluationAgent,
            create_pipeline_coordinator,
            create_dc_query_agent,
            DC_QUERY_AVAILABLE
        )

        all_passed &= print_result("DiscoveryAgent import", DiscoveryAgent is not None)
        all_passed &= print_result("PVMAPGenerationAgent import", PVMAPGenerationAgent is not None)
        all_passed &= print_result("create_pipeline_coordinator import", create_pipeline_coordinator is not None)
        all_passed &= print_result("create_dc_query_agent import", create_dc_query_agent is not None)
        all_passed &= print_result("DC_QUERY_AVAILABLE flag", DC_QUERY_AVAILABLE == True)

    except ImportError as e:
        all_passed &= print_result("Agent imports", False, str(e))

    return all_passed


def test_coordinator_with_mcp():
    """Test that coordinator accepts MCP parameters."""
    print("\nTest 3: Coordinator with MCP Parameters")
    print("-" * 40)
    all_passed = True

    try:
        from src.agents import create_pipeline_coordinator

        # Create coordinator without MCP
        coordinator_no_mcp = create_pipeline_coordinator(
            enable_mcp=False
        )
        all_passed &= print_result("Coordinator without MCP", coordinator_no_mcp is not None)

        # Check agent count (should be 5 without MCP)
        no_mcp_agents = len(coordinator_no_mcp.sub_agents)
        all_passed &= print_result(f"Agent count without MCP", no_mcp_agents == 5, f"{no_mcp_agents} agents")

        # Create coordinator with MCP
        coordinator_with_mcp = create_pipeline_coordinator(
            enable_mcp=True,
            mcp_url="http://localhost:3000/mcp"
        )
        all_passed &= print_result("Coordinator with MCP", coordinator_with_mcp is not None)

        # Check agent count (should be 6 with MCP - includes DCQueryAgent)
        with_mcp_agents = len(coordinator_with_mcp.sub_agents)
        all_passed &= print_result(f"Agent count with MCP", with_mcp_agents == 6, f"{with_mcp_agents} agents")

        # Check that DCQueryAgent is included
        agent_names = [a.name for a in coordinator_with_mcp.sub_agents]
        has_dc_query = "DCQueryAgent" in agent_names
        all_passed &= print_result("DCQueryAgent included", has_dc_query, str(agent_names))

    except Exception as e:
        import traceback
        traceback.print_exc()
        all_passed &= print_result("Coordinator test", False, str(e))

    return all_passed


def test_mcp_server_lifecycle():
    """Test MCP server can start and stop via the API module."""
    print("\nTest 4: MCP Server Lifecycle via API")
    print("-" * 40)
    all_passed = True

    try:
        from src.data_commons.api import MCPServerManager

        port = int(os.getenv("MCP_PORT", "3000"))
        manager = MCPServerManager(port=port)

        # Test start
        started = manager.start(timeout=30)
        all_passed &= print_result("Server start via API", started)

        if started:
            # Test is_running
            running = manager.is_running()
            all_passed &= print_result("is_running()", running)

            # Test stop
            manager.stop()
            all_passed &= print_result("Server stop via API", True)

    except Exception as e:
        all_passed &= print_result("MCP lifecycle test", False, str(e))

    return all_passed


def test_run_pipeline_args():
    """Test that run_pipeline.py accepts MCP arguments."""
    print("\nTest 5: run_pipeline.py CLI Arguments")
    print("-" * 40)
    all_passed = True

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "src/run_pipeline.py", "--help"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT)
        )

        help_text = result.stdout

        # Check for MCP-related arguments
        has_enable_mcp = "--enable-mcp" in help_text
        has_mcp_port = "--mcp-port" in help_text
        has_no_mcp = "--no-mcp" in help_text

        all_passed &= print_result("--enable-mcp flag exists", has_enable_mcp)
        all_passed &= print_result("--mcp-port flag exists", has_mcp_port)
        all_passed &= print_result("--no-mcp flag exists", has_no_mcp)

    except Exception as e:
        all_passed &= print_result("CLI args test", False, str(e))

    return all_passed


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("Full MCP Integration Test")
    print("=" * 60)

    all_passed = True

    # Test 1: API imports
    all_passed &= test_api_imports()

    # Test 2: Agent imports
    all_passed &= test_agent_imports()

    # Test 3: Coordinator with MCP
    all_passed &= test_coordinator_with_mcp()

    # Test 4: MCP server lifecycle
    all_passed &= test_mcp_server_lifecycle()

    # Test 5: CLI arguments
    all_passed &= test_run_pipeline_args()

    # Summary
    print()
    print("=" * 60)
    if all_passed:
        print("All integration tests passed!")
        print("\nMCP integration is complete and ready for use.")
        print("\nUsage:")
        print("  # Without MCP")
        print("  python src/run_pipeline.py --dataset=my_dataset")
        print()
        print("  # With MCP")
        print("  python src/run_pipeline.py --dataset=my_dataset --enable-mcp")
    else:
        print("Some tests failed. See above for details.")
    print("=" * 60)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

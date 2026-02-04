#!/usr/bin/env python3
"""
Basic MCP Server Connection Test

Tests that the Data Commons MCP server can:
1. Start as a subprocess
2. Respond to health checks
3. Stop cleanly

This is the first test to run - it validates basic connectivity
without requiring Google ADK.

Usage:
    python mcp-testing/test_mcp_connection.py
"""

import os
import subprocess
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import requests


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print test result with formatting."""
    status = "[PASS]" if passed else "[FAIL]"
    msg = f"{status} {test_name}"
    if details:
        msg += f" - {details}"
    print(msg)
    return passed


def check_dependencies() -> bool:
    """Check if required packages are installed."""
    all_passed = True

    # Check datacommons-mcp
    try:
        import datacommons_mcp
        all_passed &= print_result("datacommons-mcp package installed", True)
    except ImportError:
        all_passed &= print_result(
            "datacommons-mcp package installed", False,
            "Run: pip install datacommons-mcp"
        )

    # Check DC_API_KEY
    dc_api_key = os.getenv("DC_API_KEY")
    if dc_api_key:
        # Mask the key for display
        masked = dc_api_key[:4] + "..." + dc_api_key[-4:] if len(dc_api_key) > 8 else "***"
        all_passed &= print_result("DC_API_KEY environment variable set", True, f"({masked})")
    else:
        all_passed &= print_result(
            "DC_API_KEY environment variable set", False,
            "Get key from https://apikeys.datacommons.org/"
        )

    return all_passed


def test_mcp_server_lifecycle() -> bool:
    """Test MCP server start, health check, and stop."""
    port = int(os.getenv("MCP_PORT", "3000"))
    base_url = f"http://localhost:{port}"
    process = None
    all_passed = True

    try:
        # Prepare environment
        env = os.environ.copy()

        # Try to start MCP server
        print(f"\nStarting MCP server on port {port}...")

        # Find datacommons-mcp executable in venv or PATH
        venv_executable = PROJECT_ROOT / "venv" / "bin" / "datacommons-mcp"
        if venv_executable.exists():
            dc_mcp_cmd = str(venv_executable)
        else:
            # Fall back to PATH
            dc_mcp_cmd = "datacommons-mcp"

        cmd = [dc_mcp_cmd, "serve", "http", "--port", str(port)]
        print(f"  Command: {' '.join(cmd)}")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True
            )
        except FileNotFoundError as e:
            all_passed &= print_result(
                "MCP server started successfully", False,
                f"datacommons-mcp not found: {e}. Run: pip install datacommons-mcp"
            )
            return all_passed

        # Wait for server to start (up to 30 seconds)
        start_time = time.time()
        server_ready = False
        while time.time() - start_time < 30:
            # Check if process died
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                all_passed &= print_result(
                    "MCP server started successfully", False,
                    f"Process died. stderr: {stderr[:200]}"
                )
                return all_passed

            # Try health check
            try:
                resp = requests.get(f"{base_url}/health", timeout=2)
                if resp.status_code == 200:
                    server_ready = True
                    break
            except requests.RequestException:
                pass

            time.sleep(1)
            print(".", end="", flush=True)

        print()  # New line after dots

        if server_ready:
            all_passed &= print_result("MCP server started successfully", True)
        else:
            all_passed &= print_result(
                "MCP server started successfully", False,
                "Timeout waiting for health check"
            )
            return all_passed

        # Test health endpoint
        try:
            resp = requests.get(f"{base_url}/health", timeout=5)
            if resp.status_code == 200:
                all_passed &= print_result("Health check passed", True, f"Response: {resp.text[:50]}")
            else:
                all_passed &= print_result("Health check passed", False, f"Status: {resp.status_code}")
        except requests.RequestException as e:
            all_passed &= print_result("Health check passed", False, str(e))

        # Test MCP endpoint exists
        try:
            resp = requests.get(f"{base_url}/mcp", timeout=5)
            # MCP endpoint might return various codes, but should respond
            all_passed &= print_result("MCP endpoint responds", True, f"Status: {resp.status_code}")
        except requests.RequestException as e:
            all_passed &= print_result("MCP endpoint responds", False, str(e))

    except Exception as e:
        all_passed &= print_result("MCP server test", False, str(e))

    finally:
        # Clean up - stop the server
        if process is not None:
            print("\nStopping MCP server...")
            try:
                process.terminate()
                process.wait(timeout=5)
                all_passed &= print_result("MCP server stopped cleanly", True)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                all_passed &= print_result("MCP server stopped cleanly", False, "Had to kill process")

    return all_passed


def main():
    """Run all connection tests."""
    print("=" * 60)
    print("MCP Server Connection Test")
    print("=" * 60)
    print()

    all_passed = True

    # Phase 1: Check dependencies
    print("Phase 1: Checking dependencies...")
    print("-" * 40)
    deps_ok = check_dependencies()
    all_passed &= deps_ok

    if not deps_ok:
        print("\n[STOP] Fix dependency issues before continuing.")
        sys.exit(1)

    # Phase 2: Test server lifecycle
    print("\nPhase 2: Testing MCP server lifecycle...")
    print("-" * 40)
    all_passed &= test_mcp_server_lifecycle()

    # Summary
    print()
    print("=" * 60)
    if all_passed:
        print("All tests passed!")
        print("\nNext step: Run test_mcp_tools.py to test ADK integration")
    else:
        print("Some tests failed. See above for details.")
    print("=" * 60)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

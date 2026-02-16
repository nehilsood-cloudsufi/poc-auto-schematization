"""
MCP Server Manager for Data Commons.

Manages the lifecycle of the Data Commons MCP server, including:
- Starting the server as a subprocess
- Health checking to ensure server is ready
- Graceful shutdown

Usage:
    from src.data_commons.api.mcp_server_manager import MCPServerManager

    manager = MCPServerManager(port=3000)
    try:
        if manager.start(timeout=30):
            # Use MCP tools via manager.mcp_url
            pass
    finally:
        manager.stop()
"""

import logging
import os
import subprocess
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class MCPServerManager:
    """
    Manages the Data Commons MCP server lifecycle.

    The MCP server provides tools for querying Data Commons:
    - search_indicators: Search for statistical variables and topics
    - get_observations: Fetch statistical data for variables and places

    The server is started as a subprocess using the datacommons-mcp package
    and communicates via HTTP on the specified port.

    Attributes:
        port: The HTTP port for the MCP server (default: 3000)
        process: The subprocess running the MCP server (None if not running)
        base_url: The base URL for the MCP server
    """

    def __init__(
        self,
        port: int = 3000,
        dc_api_key: Optional[str] = None,
        dc_instance_url: Optional[str] = None
    ):
        """
        Initialize the MCP server manager.

        Args:
            port: HTTP port for the MCP server (default: 3000)
            dc_api_key: Data Commons API key (falls back to DC_API_KEY env var)
            dc_instance_url: Custom DC instance URL (falls back to DC_INSTANCE_URL env var)
        """
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.base_url = f"http://localhost:{port}"

        # Store API credentials (will be passed to subprocess via env)
        self._dc_api_key = dc_api_key or os.getenv("DC_API_KEY")
        self._dc_instance_url = dc_instance_url or os.getenv("DC_INSTANCE_URL")

    def start(self, timeout: int = 30) -> bool:
        """
        Start the MCP server and wait for it to be ready.

        Launches the Data Commons MCP server using 'uv tool run datacommons-mcp'
        and polls the health endpoint until the server is ready or timeout.

        Args:
            timeout: Maximum seconds to wait for server startup (default: 30)

        Returns:
            True if server started successfully and is healthy, False otherwise

        Raises:
            RuntimeError: If datacommons-mcp is not installed
        """
        # Check if already running
        if self.is_running():
            logger.info(f"MCP server already running on port {self.port}")
            return True

        # Prepare environment with DC API key
        env = os.environ.copy()
        if self._dc_api_key:
            env["DC_API_KEY"] = self._dc_api_key
        if self._dc_instance_url:
            env["DC_INSTANCE_URL"] = self._dc_instance_url

        # Find datacommons-mcp executable
        # First check .venv, then fall back to PATH
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent.parent.resolve()
        venv_executable = project_root / ".venv" / "bin" / "datacommons-mcp"

        if venv_executable.exists():
            dc_mcp_cmd = str(venv_executable)
        else:
            # Fall back to PATH
            dc_mcp_cmd = "datacommons-mcp"

        cmd = [dc_mcp_cmd, "serve", "http", "--port", str(self.port)]
        logger.info(f"Starting MCP server: {' '.join(cmd)}")

        try:
            # Use DEVNULL instead of PIPE to avoid pipe buffer deadlock.
            # The MCP server outputs significant content on startup (ASCII art,
            # initialization logs, etc.) which can fill the OS pipe buffer (~64KB).
            # Since we don't actively read from pipes, this would cause the server
            # to block waiting for the buffer to drain. We only need to know if
            # the server started (via health check) or failed (via exit code).
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
        except FileNotFoundError:
            logger.error("datacommons-mcp not installed. Run: pip install datacommons-mcp")
            return False

        # Wait for health check to pass
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Check if process died
            if self.process.poll() is not None:
                exit_code = self.process.returncode
                logger.error(f"MCP server process died with exit code: {exit_code}")
                self.process = None
                return False

            # Try health check
            try:
                resp = requests.get(f"{self.base_url}/health", timeout=2)
                if resp.status_code == 200:
                    logger.info(f"MCP server started successfully on port {self.port}")
                    return True
            except requests.RequestException:
                pass

            time.sleep(1)

        # Timeout reached
        logger.error(f"MCP server failed to start within {timeout} seconds")
        self.stop()
        return False

    def stop(self) -> None:
        """
        Stop the MCP server gracefully.

        Terminates the subprocess and waits for it to exit.
        If the process doesn't exit within 5 seconds, it will be killed.
        """
        if self.process is None:
            return

        logger.info("Stopping MCP server...")

        try:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("MCP server didn't terminate, killing...")
                self.process.kill()
                self.process.wait(timeout=2)
        except Exception as e:
            logger.error(f"Error stopping MCP server: {e}")
        finally:
            self.process = None
            logger.info("MCP server stopped")

    def is_running(self) -> bool:
        """
        Check if the MCP server is healthy and responding.

        Returns:
            True if server is running and healthy, False otherwise
        """
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=2)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    @property
    def mcp_url(self) -> str:
        """
        Get the MCP endpoint URL.

        Returns:
            The URL for the MCP endpoint (e.g., "http://localhost:3000/mcp")
        """
        return f"{self.base_url}/mcp"

    def __enter__(self) -> "MCPServerManager":
        """Context manager entry - starts the server."""
        if not self.start():
            raise RuntimeError("Failed to start MCP server")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - stops the server."""
        self.stop()

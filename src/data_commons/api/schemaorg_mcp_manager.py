"""
MCP Server Manager for Schema.org vocabulary.

Manages the lifecycle of the Schema.org MCP server (start/stop/health).
Follows the same pattern as MCPServerManager for Data Commons.

Usage:
    from src.data_commons.api.schemaorg_mcp_manager import SchemaOrgMCPManager

    manager = SchemaOrgMCPManager(port=3001)
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
import sys
import time
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()


class SchemaOrgMCPManager:
    """
    Manages the Schema.org MCP server lifecycle.

    The server provides tools for looking up schema.org types, properties,
    and validating PVMAP property-type compatibility.

    Attributes:
        port: The HTTP port for the MCP server (default: 3001)
        process: The subprocess running the MCP server (None if not running)
        base_url: The base URL for the MCP server
    """

    def __init__(self, port: int = 3001):
        """
        Initialize the Schema.org MCP server manager.

        Args:
            port: HTTP port for the MCP server (default: 3001)
        """
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.base_url = f"http://localhost:{port}"

    def start(self, timeout: int = 30) -> bool:
        """
        Start the MCP server and wait for it to be ready.

        Args:
            timeout: Maximum seconds to wait for server startup (default: 30)

        Returns:
            True if server started successfully and is healthy, False otherwise
        """
        if self.is_running():
            logger.info(f"Schema.org MCP server already running on port {self.port}")
            return True

        # Find Python executable
        venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
        python_cmd = str(venv_python) if venv_python.exists() else sys.executable

        server_module = "src.data_commons.api.schemaorg_mcp_server"
        cmd = [
            python_cmd, "-m", server_module,
            "--port", str(self.port),
        ]

        logger.info(f"Starting Schema.org MCP server: {' '.join(cmd)}")

        try:
            env = os.environ.copy()
            # Ensure PYTHONPATH includes project root
            pythonpath = env.get("PYTHONPATH", "")
            paths = [str(PROJECT_ROOT), str(PROJECT_ROOT / "src")]
            for p in paths:
                if p not in pythonpath:
                    pythonpath = f"{p}:{pythonpath}" if pythonpath else p
            env["PYTHONPATH"] = pythonpath

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                cwd=str(PROJECT_ROOT),
            )
        except FileNotFoundError:
            logger.error(f"Python not found at {python_cmd}")
            return False

        # Wait for health check
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.process.poll() is not None:
                exit_code = self.process.returncode
                logger.error(f"Schema.org MCP server died with exit code: {exit_code}")
                self.process = None
                return False

            try:
                resp = requests.get(f"{self.base_url}/health", timeout=2)
                if resp.status_code == 200:
                    logger.info(f"Schema.org MCP server started on port {self.port}")
                    return True
            except requests.RequestException:
                pass

            time.sleep(1)

        logger.error(f"Schema.org MCP server failed to start within {timeout}s")
        self.stop()
        return False

    def stop(self) -> None:
        """Stop the MCP server gracefully."""
        if self.process is None:
            return

        logger.info("Stopping Schema.org MCP server...")

        try:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Schema.org MCP server didn't terminate, killing...")
                self.process.kill()
                self.process.wait(timeout=2)
        except Exception as e:
            logger.error(f"Error stopping Schema.org MCP server: {e}")
        finally:
            self.process = None
            logger.info("Schema.org MCP server stopped")

    def is_running(self) -> bool:
        """Check if the MCP server is healthy."""
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=2)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    @property
    def mcp_url(self) -> str:
        """Get the MCP endpoint URL."""
        return f"{self.base_url}/mcp"

    def __enter__(self) -> "SchemaOrgMCPManager":
        """Context manager entry."""
        if not self.start():
            raise RuntimeError("Failed to start Schema.org MCP server")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()

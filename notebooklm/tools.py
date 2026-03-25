"""
ADK tool functions wrapping the official Google NotebookLM MCP server.

Each tool function is async and returns a dict with
{"success": bool, "data": ..., "error": str} pattern, matching the
convention in src/tools/.

The MCP server is accessed via corp-mcp-proxy (stdio transport).
Configure via environment variables:
    NLM_MCP_COMMAND  — path to MCP proxy binary
                       (default: /google/bin/releases/corp-mcp-proxy/server.par)
    NLM_MCP_ARGS     — JSON-encoded args list (optional override)
"""

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MCP server configuration
# ---------------------------------------------------------------------------

_DEFAULT_COMMAND = "/google/bin/releases/corp-mcp-proxy/server.par"
_DEFAULT_ARGS = [
    "--mcp_server=blade:google.internal.labs.tailwind.mcp.partner.mcpservice-prod",
    "--use_gaia_mint=True",
    "--alsologtostderr",
]

MCP_COMMAND = os.getenv("NLM_MCP_COMMAND", _DEFAULT_COMMAND)
MCP_ARGS = json.loads(os.getenv("NLM_MCP_ARGS", "null")) or _DEFAULT_ARGS
MCP_TIMEOUT = int(os.getenv("NLM_MCP_TIMEOUT", "60"))


# ---------------------------------------------------------------------------
# MCP client — one-shot per call (stateless stdio transport)
# ---------------------------------------------------------------------------

async def _call_mcp_tool(tool_name: str, arguments: dict | None = None) -> dict:
    """Spawn the MCP server, call one tool, return parsed result."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server = StdioServerParameters(command=MCP_COMMAND, args=MCP_ARGS)

    try:
        async with stdio_client(server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments or {})

                # Extract text from content blocks
                parts = []
                for block in result.content:
                    parts.append(block.text if hasattr(block, "text") else str(block))
                raw = "\n".join(parts)

                # Try to parse as JSON for structured data
                try:
                    parsed = json.loads(raw)
                    return {"success": True, "data": parsed, "error": ""}
                except (json.JSONDecodeError, TypeError):
                    return {"success": True, "data": {"text": raw}, "error": ""}

    except Exception as e:
        logger.error("MCP tool %s failed: %s", tool_name, e)
        return {"success": False, "data": {}, "error": str(e)}


# ---------------------------------------------------------------------------
# Notebook management
# ---------------------------------------------------------------------------

async def create_notebook(name: str) -> dict:
    """Create a new NotebookLM notebook.

    Args:
        name: Display name for the notebook.
    """
    return await _call_mcp_tool("create_notebook", {"name": name})


async def list_notebooks() -> dict:
    """List all notebooks for the authenticated user."""
    return await _call_mcp_tool("list_notebooks")


# ---------------------------------------------------------------------------
# Source management
# ---------------------------------------------------------------------------

async def create_source(
    notebook_id: str,
    source_type: str,
    content: str,
) -> dict:
    """Add a source to a notebook.

    Args:
        notebook_id: Target notebook ID.
        source_type: One of "url", "google_drive", "text".
        content: URL, Drive link, or raw text depending on source_type.
    """
    return await _call_mcp_tool("create_source", {
        "notebook_id": notebook_id,
        "source_type": source_type,
        "content": content,
    })


async def add_url_source(notebook_id: str, url: str) -> dict:
    """Add a URL source to a notebook (convenience wrapper)."""
    return await create_source(notebook_id, "url", url)


async def add_text_source(notebook_id: str, text: str) -> dict:
    """Add raw text as a source (convenience wrapper)."""
    return await create_source(notebook_id, "text", text)


async def list_sources(notebook_id: str) -> dict:
    """List all sources in a notebook.

    Args:
        notebook_id: Target notebook ID.
    """
    return await _call_mcp_tool("list_sources", {"notebook_id": notebook_id})


async def delete_source(notebook_id: str, source_id: str) -> dict:
    """Remove a source from a notebook.

    Args:
        notebook_id: Target notebook ID.
        source_id: Source to remove.
    """
    return await _call_mcp_tool("delete_source", {
        "notebook_id": notebook_id,
        "source_id": source_id,
    })


# ---------------------------------------------------------------------------
# Query / Answer
# ---------------------------------------------------------------------------

async def generate_answer(notebook_id: str, question: str) -> dict:
    """Query a notebook and generate an answer grounded in sources.

    Args:
        notebook_id: Target notebook ID.
        question: The question to ask.
    """
    return await _call_mcp_tool("generate_answer", {
        "notebook_id": notebook_id,
        "question": question,
    })


# Backward-compatible alias used by enrichment agent and viewer
ask_question = generate_answer


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------

async def create_artifact(
    notebook_id: str,
    artifact_type: str,
    **kwargs: Any,
) -> dict:
    """Create an artifact (slide deck, audio overview, etc.).

    Args:
        notebook_id: Target notebook ID.
        artifact_type: Type of artifact to create.
        **kwargs: Additional parameters for the artifact.
    """
    args = {"notebook_id": notebook_id, "artifact_type": artifact_type}
    args.update(kwargs)
    return await _call_mcp_tool("create_artifact", args)


async def get_artifact(notebook_id: str, artifact_id: str) -> dict:
    """Retrieve an artifact or check its status.

    Args:
        notebook_id: Target notebook ID.
        artifact_id: The artifact to retrieve.
    """
    return await _call_mcp_tool("get_artifact", {
        "notebook_id": notebook_id,
        "artifact_id": artifact_id,
    })


# ---------------------------------------------------------------------------
# Convenience wrappers (keep agents.py imports working)
# ---------------------------------------------------------------------------

async def delete_notebook(notebook_id: str) -> dict:
    """Delete a notebook (not in official MCP — returns no-op)."""
    logger.info("delete_notebook called for %s (no-op in official MCP)", notebook_id)
    return {"success": True, "data": {"notebook_id": notebook_id}, "error": ""}


async def shutdown_client() -> None:
    """No-op — stdio transport is stateless, no persistent client to close."""
    pass

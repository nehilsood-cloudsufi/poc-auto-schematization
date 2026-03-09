"""
ADK tool functions wrapping notebooklm-py async methods.

Each tool function is async (ADK supports async tools natively) and returns
a dict with {"success": bool, "data": ..., "error": str} pattern, matching
the convention in src/tools/.

Client lifecycle: A module-level singleton is lazy-initialized via _get_client().
The client requires prior authentication via `notebooklm login`.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

from notebooklm import NotebookLMClient

# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

_client: Optional[NotebookLMClient] = None
_client_lock = asyncio.Lock()


async def _get_client() -> NotebookLMClient:
    """Return (and lazily create) the shared NotebookLMClient."""
    global _client
    if _client is None:
        async with _client_lock:
            if _client is None:
                _client = await NotebookLMClient.from_storage()
                # Enter the async context manager so the browser session is live
                await _client.__aenter__()
    return _client


async def shutdown_client() -> None:
    """Gracefully close the shared client (call at program exit)."""
    global _client
    if _client is not None:
        await _client.__aexit__(None, None, None)
        _client = None


# ---------------------------------------------------------------------------
# Notebook management
# ---------------------------------------------------------------------------


async def create_notebook(name: str) -> dict:
    """Create a new NotebookLM notebook.

    Args:
        name: Display name for the notebook.

    Returns:
        dict with notebook_id and name on success.
    """
    try:
        client = await _get_client()
        notebook = await client.notebooks.create(name)
        return {
            "success": True,
            "data": {"notebook_id": notebook.id, "name": notebook.name},
            "error": "",
        }
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


async def delete_notebook(notebook_id: str) -> dict:
    """Delete a notebook by ID.

    Args:
        notebook_id: The notebook to delete.
    """
    try:
        client = await _get_client()
        await client.notebooks.delete(notebook_id)
        return {"success": True, "data": {"notebook_id": notebook_id}, "error": ""}
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


async def list_notebooks() -> dict:
    """List all notebooks for the authenticated user."""
    try:
        client = await _get_client()
        notebooks = await client.notebooks.list()
        items = [{"notebook_id": nb.id, "name": nb.name} for nb in notebooks]
        return {"success": True, "data": {"notebooks": items}, "error": ""}
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


# ---------------------------------------------------------------------------
# Source management
# ---------------------------------------------------------------------------


async def add_url_source(notebook_id: str, url: str) -> dict:
    """Add a URL as a source to a notebook.

    Args:
        notebook_id: Target notebook.
        url: Web page URL to import.
    """
    try:
        client = await _get_client()
        source = await client.sources.add_url(notebook_id, url, wait=True)
        return {
            "success": True,
            "data": {"source_id": source.id, "url": url},
            "error": "",
        }
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


async def add_youtube_source(notebook_id: str, video_url: str) -> dict:
    """Add a YouTube video as a source.

    Args:
        notebook_id: Target notebook.
        video_url: YouTube video URL.
    """
    try:
        client = await _get_client()
        source = await client.sources.add_youtube(notebook_id, video_url)
        return {
            "success": True,
            "data": {"source_id": source.id, "video_url": video_url},
            "error": "",
        }
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


async def add_text_source(notebook_id: str, text: str) -> dict:
    """Add inline text as a source.

    Args:
        notebook_id: Target notebook.
        text: The text content to add.
    """
    try:
        client = await _get_client()
        source = await client.sources.add_text(notebook_id, text)
        return {
            "success": True,
            "data": {"source_id": source.id},
            "error": "",
        }
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


async def add_file_source(notebook_id: str, file_path: str) -> dict:
    """Upload a local file as a source.

    Args:
        notebook_id: Target notebook.
        file_path: Absolute or relative path to the file.
    """
    try:
        client = await _get_client()
        path = Path(file_path).resolve()
        if not path.exists():
            return {"success": False, "data": {}, "error": f"File not found: {path}"}
        await client.sources.add_file(notebook_id, str(path))
        return {
            "success": True,
            "data": {"file_path": str(path)},
            "error": "",
        }
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


async def ask_question(notebook_id: str, question: str) -> dict:
    """Ask a question against the notebook's sources.

    Args:
        notebook_id: Target notebook.
        question: The question to ask.

    Returns:
        dict with answer text and citation count.
    """
    try:
        client = await _get_client()
        response = await client.chat.ask(notebook_id, question)
        citation_count = len(response.citations) if response.citations else 0
        return {
            "success": True,
            "data": {
                "answer": response.answer,
                "citation_count": citation_count,
            },
            "error": "",
        }
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


# ---------------------------------------------------------------------------
# Artifact generation
# ---------------------------------------------------------------------------


async def generate_audio(
    notebook_id: str,
    instructions: str = "",
    audio_format: str = "deep-dive",
    audio_length: str = "medium",
) -> dict:
    """Generate an audio overview (podcast-style) and wait for completion.

    Args:
        notebook_id: Target notebook.
        instructions: Optional focus instructions for the audio.
        audio_format: One of "brief", "deep-dive". Default "deep-dive".
        audio_length: One of "short", "medium", "long". Default "medium".

    Returns:
        dict indicating the audio is ready for download.
    """
    try:
        client = await _get_client()
        kwargs = {"format": audio_format, "length": audio_length, "language": "en"}
        if instructions:
            kwargs["instructions"] = instructions
        task = await client.artifacts.generate_audio(notebook_id, **kwargs)
        await client.artifacts.wait_for_completion(notebook_id, task.id)
        return {
            "success": True,
            "data": {"task_id": task.id, "status": "completed"},
            "error": "",
        }
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


async def download_audio(notebook_id: str, output_path: str) -> dict:
    """Download generated audio to a local file.

    Args:
        notebook_id: Target notebook.
        output_path: Local path to save the audio file.
    """
    try:
        client = await _get_client()
        await client.artifacts.download_audio(notebook_id, output_path)
        return {"success": True, "data": {"output_path": output_path}, "error": ""}
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


async def generate_video(
    notebook_id: str,
    instructions: str = "",
    video_style: str = "whiteboard",
) -> dict:
    """Generate a video overview and wait for completion.

    Args:
        notebook_id: Target notebook.
        instructions: Optional instructions.
        video_style: Style of the video (e.g. "whiteboard"). Default "whiteboard".
    """
    try:
        client = await _get_client()
        task = await client.artifacts.generate_video(
            notebook_id, format="standard", style=video_style
        )
        await client.artifacts.wait_for_completion(notebook_id, task.id)
        return {
            "success": True,
            "data": {"task_id": task.id, "status": "completed"},
            "error": "",
        }
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


async def download_video(notebook_id: str, output_path: str) -> dict:
    """Download generated video to a local file.

    Args:
        notebook_id: Target notebook.
        output_path: Local path to save the video file.
    """
    try:
        client = await _get_client()
        await client.artifacts.download_video(notebook_id, output_path)
        return {"success": True, "data": {"output_path": output_path}, "error": ""}
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


async def generate_report(
    notebook_id: str,
    title: str = "",
    report_format: str = "briefing",
) -> dict:
    """Generate a report/briefing document and wait for completion.

    Args:
        notebook_id: Target notebook.
        title: Optional custom prompt / title for the report.
        report_format: Template name (e.g. "briefing"). Default "briefing".
    """
    try:
        client = await _get_client()
        kwargs = {"template": report_format}
        if title:
            kwargs["custom_prompt"] = title
        task = await client.artifacts.generate_report(notebook_id, **kwargs)
        await client.artifacts.wait_for_completion(notebook_id, task.id)
        return {
            "success": True,
            "data": {"task_id": task.id, "status": "completed"},
            "error": "",
        }
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


async def download_report(notebook_id: str, output_path: str) -> dict:
    """Download a generated report to a local file.

    Args:
        notebook_id: Target notebook.
        output_path: Local path to save the report.
    """
    try:
        client = await _get_client()
        await client.artifacts.download_report(notebook_id, output_path)
        return {"success": True, "data": {"output_path": output_path}, "error": ""}
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


async def generate_quiz(
    notebook_id: str,
    difficulty: str = "medium",
    quantity: str = "standard",
) -> dict:
    """Generate a quiz and wait for completion.

    Args:
        notebook_id: Target notebook.
        difficulty: "easy", "medium", or "hard". Default "medium".
        quantity: "few", "standard", or "many". Default "standard".
    """
    try:
        client = await _get_client()
        task = await client.artifacts.generate_quiz(
            notebook_id, quantity=quantity, difficulty=difficulty
        )
        await client.artifacts.wait_for_completion(notebook_id, task.id)
        return {
            "success": True,
            "data": {"task_id": task.id, "status": "completed"},
            "error": "",
        }
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


async def download_quiz(notebook_id: str, output_path: str) -> dict:
    """Download a generated quiz to a local JSON file.

    Args:
        notebook_id: Target notebook.
        output_path: Local path to save the quiz JSON.
    """
    try:
        client = await _get_client()
        await client.artifacts.download_quiz(
            notebook_id, output_path, output_format="json"
        )
        return {"success": True, "data": {"output_path": output_path}, "error": ""}
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}


# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------


async def start_research(
    notebook_id: str,
    query: str,
    mode: str = "deep",
) -> dict:
    """Start a web research task and wait for results.

    Args:
        notebook_id: Target notebook.
        query: Research query / topic.
        mode: "quick" or "deep". Default "deep".

    Returns:
        dict with list of discovered source titles.
    """
    try:
        client = await _get_client()
        research = await client.research.web_research(
            notebook_id, query=query, mode=mode
        )
        sources = [
            {"title": src.title[:120]} for src in (research.sources or [])
        ]
        return {
            "success": True,
            "data": {"source_count": len(sources), "sources": sources},
            "error": "",
        }
    except Exception as e:
        return {"success": False, "data": {}, "error": str(e)}

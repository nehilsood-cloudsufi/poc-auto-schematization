"""
ADK agents for NotebookLM integration via the official Google MCP server.

Defines four agents:
1. ResearchAgent (LlmAgent) — interactive research via NotebookLM
2. DataAnalysisAgent (LlmAgent) — analyze project CSV datasets
3. PodcastPipelineAgent (BaseAgent) — deterministic notebook-to-artifact pipeline
4. BulkImportAgent (BaseAgent) — concurrent multi-source import

All agents use the MCP-backed tool functions from tools.py.
"""

import logging
import os
from typing import AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from typing_extensions import override

from notebooklm.tools import (
    create_notebook,
    delete_notebook,
    list_notebooks,
    create_source,
    add_url_source,
    add_text_source,
    list_sources,
    delete_source,
    generate_answer,
    create_artifact,
    get_artifact,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. ResearchAgent — LlmAgent with all tools
# ---------------------------------------------------------------------------

_RESEARCH_INSTRUCTION = """\
You are a research assistant with access to Google NotebookLM via its official MCP API.

You can create notebooks, add sources (URLs, Google Drive links, or text),
query notebooks for grounded answers, and create artifacts (audio, slides, etc.).

Workflow:
1. Create a notebook for the topic using create_notebook.
2. Add relevant sources using add_url_source or add_text_source.
3. Use generate_answer to query the sources and gather grounded insights.
4. Create artifacts as requested using create_artifact.
5. Report findings back to the user.

Use [NUMBER] for numeric placeholders and [DATA] for data placeholders.
"""


def create_research_agent(
    name: str = "ResearchAgent",
    model: str = "gemini-2.5-flash",
) -> LlmAgent:
    """Create a ResearchAgent that interactively uses NotebookLM tools."""
    return LlmAgent(
        name=name,
        model=model,
        instruction=_RESEARCH_INSTRUCTION,
        description="Interactive research assistant using Google NotebookLM",
        tools=[
            create_notebook,
            delete_notebook,
            list_notebooks,
            add_url_source,
            add_text_source,
            list_sources,
            generate_answer,
            create_artifact,
            get_artifact,
        ],
    )


# ---------------------------------------------------------------------------
# 2. DataAnalysisAgent — LlmAgent for project CSV analysis
# ---------------------------------------------------------------------------

_DATA_ANALYSIS_INSTRUCTION = """\
You analyze datasets using Google NotebookLM. You receive a CSV file path
and an optional dataset name in the session state.

Workflow:
1. Create a notebook named after the dataset using create_notebook.
2. Add the CSV data as text source using add_text_source.
3. If metadata text is provided in state key "metadata_text", add it too.
4. Ask questions about the dataset using generate_answer:
   - What does it contain? Describe columns, types, measurements.
   - What geographic regions and time periods does it cover?
   - How would you map this into a Schema.org knowledge graph?
5. Create a briefing artifact using create_artifact.
6. Report your findings clearly to the user.
"""


def create_data_analysis_agent(
    name: str = "DataAnalysisAgent",
    model: str = "gemini-2.5-flash",
) -> LlmAgent:
    """Create a DataAnalysisAgent that analyzes CSV datasets via NotebookLM."""
    return LlmAgent(
        name=name,
        model=model,
        instruction=_DATA_ANALYSIS_INSTRUCTION,
        description="Dataset analysis agent using Google NotebookLM",
        tools=[
            create_notebook,
            delete_notebook,
            add_text_source,
            add_url_source,
            generate_answer,
            create_artifact,
            get_artifact,
        ],
    )


# ---------------------------------------------------------------------------
# 3. PodcastPipelineAgent — BaseAgent (deterministic pipeline)
# ---------------------------------------------------------------------------


class PodcastPipelineAgent(BaseAgent):
    """Deterministic pipeline: create notebook -> add sources -> artifact.

    Reads from session state:
        - topic: str — research topic (required)
        - source_urls: list[str] — URLs to add as sources (optional)
        - output_dir: str — directory for output files (default: ".")

    Writes to session state:
        - notebook_id: str
        - artifact_id: str
        - pipeline_status: str ("completed" or "failed")
    """

    model_config = {"arbitrary_types_allowed": True}

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        topic = state.get("topic", "advances in artificial intelligence")
        source_urls = state.get("source_urls", [])

        try:
            # Step 1: Create notebook
            result = await create_notebook(f"Research: {topic[:50]}")
            if not result["success"]:
                state["pipeline_status"] = f"failed: {result['error']}"
                yield Event(
                    author=self.name,
                    content=types.Content(
                        parts=[types.Part(text=f"Failed to create notebook: {result['error']}")]
                    ),
                )
                return
            notebook_id = result["data"].get("notebook_id", result["data"].get("id", ""))
            state["notebook_id"] = notebook_id
            yield Event(
                author=self.name,
                content=types.Content(
                    parts=[types.Part(text=f"Created notebook {notebook_id}")]
                ),
            )

            # Step 2: Add sources
            for url in source_urls:
                r = await add_url_source(notebook_id, url)
                status = "added" if r["success"] else f"failed: {r['error']}"
                yield Event(
                    author=self.name,
                    content=types.Content(
                        parts=[types.Part(text=f"Source {url[:60]}: {status}")]
                    ),
                )

            # Step 3: Query for summary
            result = await generate_answer(
                notebook_id,
                f"What are the 3 most important points about {topic}?",
            )
            if result["success"]:
                answer = result["data"].get("answer", result["data"].get("text", ""))
                yield Event(
                    author=self.name,
                    content=types.Content(
                        parts=[types.Part(text=f"Key points:\n{str(answer)[:500]}")]
                    ),
                )

            # Step 4: Create audio artifact
            yield Event(
                author=self.name,
                content=types.Content(
                    parts=[types.Part(text="Creating audio artifact...")]
                ),
            )
            result = await create_artifact(notebook_id, "audio_overview")
            if result["success"]:
                artifact_id = result["data"].get("artifact_id", result["data"].get("id", ""))
                state["artifact_id"] = artifact_id

            state["pipeline_status"] = "completed"
            yield Event(
                author=self.name,
                content=types.Content(
                    parts=[types.Part(text="Pipeline completed successfully.")]
                ),
            )

        except Exception as e:
            state["pipeline_status"] = f"failed: {e}"
            yield Event(
                author=self.name,
                content=types.Content(
                    parts=[types.Part(text=f"Pipeline failed: {e}")]
                ),
            )


# ---------------------------------------------------------------------------
# 4. BulkImportAgent — BaseAgent (concurrent import)
# ---------------------------------------------------------------------------


class BulkImportAgent(BaseAgent):
    """Import multiple sources into a notebook concurrently.

    Reads from session state:
        - notebook_name: str — name for the new notebook (default: "Bulk Import")
        - sources: list[dict] — each dict has "type" (url/text/google_drive), "content", "label"

    Writes to session state:
        - notebook_id: str
        - import_results: list[dict]
        - import_summary: str
    """

    model_config = {"arbitrary_types_allowed": True}

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        import asyncio

        state = ctx.session.state
        notebook_name = state.get("notebook_name", "Bulk Import")
        sources = state.get("sources", [])

        if not sources:
            yield Event(
                author=self.name,
                content=types.Content(
                    parts=[types.Part(text="No sources provided in state['sources'].")]
                ),
            )
            return

        # Create notebook
        result = await create_notebook(notebook_name)
        if not result["success"]:
            yield Event(
                author=self.name,
                content=types.Content(
                    parts=[types.Part(text=f"Failed to create notebook: {result['error']}")]
                ),
            )
            return
        notebook_id = result["data"].get("notebook_id", result["data"].get("id", ""))
        state["notebook_id"] = notebook_id

        yield Event(
            author=self.name,
            content=types.Content(
                parts=[types.Part(text=f"Created notebook {notebook_id}. Importing {len(sources)} sources...")]
            ),
        )

        # Import concurrently
        async def _import_one(spec: dict) -> dict:
            src_type = spec.get("type", "text")
            content = spec.get("content", "")
            label = spec.get("label", content[:40])
            try:
                r = await create_source(notebook_id, src_type, content)
                return {"label": label, "success": r["success"], "error": r.get("error", "")}
            except Exception as e:
                return {"label": label, "success": False, "error": str(e)}

        results = await asyncio.gather(*[_import_one(s) for s in sources])
        state["import_results"] = list(results)

        succeeded = sum(1 for r in results if r["success"])
        summary = f"{succeeded}/{len(results)} sources imported"
        state["import_summary"] = summary

        lines = [summary, ""]
        for r in results:
            icon = "+" if r["success"] else "x"
            line = f"  [{icon}] {r['label']}"
            if not r["success"]:
                line += f": {r['error']}"
            lines.append(line)

        yield Event(
            author=self.name,
            content=types.Content(
                parts=[types.Part(text="\n".join(lines))]
            ),
        )

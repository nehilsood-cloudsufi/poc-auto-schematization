"""
ADK agents for NotebookLM integration.

Defines four agents:
1. ResearchAgent (LlmAgent) — interactive research via NotebookLM
2. DataAnalysisAgent (LlmAgent) — analyze project CSV datasets
3. PodcastPipelineAgent (BaseAgent) — deterministic research-to-podcast pipeline
4. BulkImportAgent (BaseAgent) — concurrent multi-source import

All agents use the tool functions from tools.py.
"""

import logging
import os
from typing import AsyncGenerator, List, Optional

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from typing_extensions import override

from notebooklm.tools import (
    create_notebook,
    delete_notebook,
    list_notebooks,
    add_url_source,
    add_youtube_source,
    add_text_source,
    add_file_source,
    ask_question,
    generate_audio,
    download_audio,
    generate_video,
    download_video,
    generate_report,
    download_report,
    generate_quiz,
    download_quiz,
    start_research,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. ResearchAgent — LlmAgent with all tools
# ---------------------------------------------------------------------------

_RESEARCH_INSTRUCTION = """\
You are a research assistant with access to Google NotebookLM.

You can create notebooks, add sources (URLs, YouTube videos, text), ask
questions against those sources, generate artifacts (audio podcasts, video
overviews, reports, quizzes), and run web research.

Workflow:
1. Create a notebook for the topic using create_notebook.
2. Add relevant sources using add_url_source, add_youtube_source, or add_text_source.
3. Use ask_question to explore the sources and gather insights.
4. Generate artifacts as requested (audio, video, report, quiz).
5. When done, clean up with delete_notebook unless the user wants to keep it.

Always report what you did and key findings back to the user.
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
            add_youtube_source,
            add_text_source,
            add_file_source,
            ask_question,
            generate_audio,
            download_audio,
            generate_video,
            download_video,
            generate_report,
            download_report,
            generate_quiz,
            download_quiz,
            start_research,
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
2. Upload the CSV file using add_file_source.
3. If metadata text is provided in state key "metadata_text", add it using add_text_source.
4. Ask questions about the dataset:
   - What does it contain? Describe columns, types, measurements.
   - What geographic regions and time periods does it cover?
   - How would you map this into a Schema.org knowledge graph?
5. Generate a briefing report using generate_report, then download it.
6. Clean up the notebook with delete_notebook.

Report your findings clearly to the user.
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
            add_file_source,
            add_text_source,
            ask_question,
            generate_report,
            download_report,
        ],
    )


# ---------------------------------------------------------------------------
# 3. PodcastPipelineAgent — BaseAgent (deterministic pipeline)
# ---------------------------------------------------------------------------


class PodcastPipelineAgent(BaseAgent):
    """Deterministic pipeline: create notebook -> research -> podcast -> download.

    Reads from session state:
        - topic: str — research topic (required)
        - output_dir: str — directory for output files (default: ".")

    Writes to session state:
        - notebook_id: str
        - research_source_count: int
        - podcast_path: str
        - briefing_path: str
        - pipeline_status: str ("completed" or "failed")
    """

    model_config = {"arbitrary_types_allowed": True}

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        topic = state.get("topic", "advances in artificial intelligence")
        output_dir = state.get("output_dir", ".")
        os.makedirs(output_dir, exist_ok=True)

        try:
            # Step 1: Create notebook
            result = await create_notebook(f"Podcast: {topic[:50]}")
            if not result["success"]:
                state["pipeline_status"] = f"failed: {result['error']}"
                yield Event(
                    author=self.name,
                    content=types.Content(
                        parts=[types.Part(text=f"Failed to create notebook: {result['error']}")]
                    ),
                )
                return
            notebook_id = result["data"]["notebook_id"]
            state["notebook_id"] = notebook_id
            yield Event(
                author=self.name,
                content=types.Content(
                    parts=[types.Part(text=f"Created notebook {notebook_id}")]
                ),
            )

            # Step 2: Run web research
            result = await start_research(notebook_id, topic, mode="deep")
            if result["success"]:
                count = result["data"]["source_count"]
                state["research_source_count"] = count
                titles = [s["title"] for s in result["data"].get("sources", [])]
                yield Event(
                    author=self.name,
                    content=types.Content(
                        parts=[types.Part(text=f"Research found {count} sources: {', '.join(titles[:5])}")]
                    ),
                )
            else:
                yield Event(
                    author=self.name,
                    content=types.Content(
                        parts=[types.Part(text=f"Research failed: {result['error']}. Continuing with available sources.")]
                    ),
                )

            # Step 3: Ask summary question
            result = await ask_question(
                notebook_id,
                f"What are the 3 most important recent developments in {topic}?",
            )
            if result["success"]:
                yield Event(
                    author=self.name,
                    content=types.Content(
                        parts=[types.Part(text=f"Key developments:\n{result['data']['answer'][:500]}")]
                    ),
                )

            # Step 4: Generate podcast audio
            yield Event(
                author=self.name,
                content=types.Content(
                    parts=[types.Part(text="Generating podcast audio (this may take a few minutes)...")]
                ),
            )
            result = await generate_audio(
                notebook_id,
                instructions=f"Create an engaging podcast about {topic}. Cover latest developments, challenges, and outlook.",
                audio_format="deep-dive",
                audio_length="medium",
            )
            if result["success"]:
                safe_topic = topic[:30].replace(" ", "_").replace("/", "_")
                podcast_path = os.path.join(output_dir, f"podcast_{safe_topic}.mp3")
                dl = await download_audio(notebook_id, podcast_path)
                if dl["success"]:
                    state["podcast_path"] = podcast_path
                    yield Event(
                        author=self.name,
                        content=types.Content(
                            parts=[types.Part(text=f"Podcast saved: {podcast_path}")]
                        ),
                    )

            # Step 5: Generate briefing
            result = await generate_report(notebook_id, title=f"Briefing on {topic}")
            if result["success"]:
                briefing_path = os.path.join(output_dir, f"briefing_{safe_topic}.md")
                dl = await download_report(notebook_id, briefing_path)
                if dl["success"]:
                    state["briefing_path"] = briefing_path
                    yield Event(
                        author=self.name,
                        content=types.Content(
                            parts=[types.Part(text=f"Briefing saved: {briefing_path}")]
                        ),
                    )

            # Step 6: Cleanup
            await delete_notebook(notebook_id)
            state["pipeline_status"] = "completed"
            yield Event(
                author=self.name,
                content=types.Content(
                    parts=[types.Part(text="Pipeline completed successfully. Notebook cleaned up.")]
                ),
            )

        except Exception as e:
            state["pipeline_status"] = f"failed: {e}"
            # Attempt cleanup
            if "notebook_id" in state:
                await delete_notebook(state["notebook_id"])
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
        - sources: list[dict] — each dict has "type" (url/youtube/text), "content", "label"

    Writes to session state:
        - notebook_id: str
        - import_results: list[dict] — per-source success/failure
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
        notebook_id = result["data"]["notebook_id"]
        state["notebook_id"] = notebook_id

        yield Event(
            author=self.name,
            content=types.Content(
                parts=[types.Part(text=f"Created notebook {notebook_id}. Importing {len(sources)} sources...")]
            ),
        )

        # Import all sources concurrently
        async def _import_one(spec: dict) -> dict:
            src_type = spec.get("type", "text")
            content = spec.get("content", "")
            label = spec.get("label", content[:40])
            try:
                if src_type == "url":
                    r = await add_url_source(notebook_id, content)
                elif src_type == "youtube":
                    r = await add_youtube_source(notebook_id, content)
                elif src_type == "text":
                    r = await add_text_source(notebook_id, content)
                elif src_type == "file":
                    r = await add_file_source(notebook_id, content)
                else:
                    return {"label": label, "success": False, "error": f"Unknown type: {src_type}"}
                return {"label": label, "success": r["success"], "error": r.get("error", "")}
            except Exception as e:
                return {"label": label, "success": False, "error": str(e)}

        results = await asyncio.gather(*[_import_one(s) for s in sources])
        state["import_results"] = list(results)

        succeeded = sum(1 for r in results if r["success"])
        failed = len(results) - succeeded
        summary = f"{succeeded}/{len(results)} sources imported successfully"
        if failed:
            summary += f" ({failed} failed)"
        state["import_summary"] = summary

        # Build status report
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

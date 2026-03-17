"""
NotebookLM Enrichment Agent for the PVMAP pipeline.

Queries a pre-loaded NotebookLM notebook (with Data Commons documentation)
to enrich the context available to the PVMAP generator. Runs once between
SchemaSelection and PVMAPRetryLoop.

State Inputs:
    nlm_enabled (bool): Whether NotebookLM enrichment is enabled
    nlm_notebook_id (str): Pre-existing notebook ID (optional)
    skeleton_summary (str): From sampling phase
    data_context (dict): Structural analysis from sampling
    schema_category (str): From schema selection phase

State Outputs:
    nlm_enrichment_context (str): Markdown enrichment for PVMAP prompt
    nlm_enrichment_success (bool): Whether enrichment succeeded
    nlm_notebook_id (str): Notebook ID used (may be auto-created)
    nlm_notebook_created (bool): Whether a new notebook was created (for cleanup)
"""

import asyncio
import logging
from typing import AsyncGenerator, Optional

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

logger = logging.getLogger(__name__)

# Default notebook pre-loaded with DC documentation
DEFAULT_NOTEBOOK_ID = "3d07c6fa-9e36-43e8-91cd-bbc690f32e58"

# DC documentation URLs for auto-created notebooks
DC_DOC_URLS = [
    "https://docs.datacommons.org/datasets.html",
    "https://docs.datacommons.org/data_model.html",
    "https://datacommons.org/tools/statvar",
]


def _build_statvar_question(data_context: dict, schema_category: str) -> str:
    """Build Q1: StatVar mapping guidance from data_context."""
    columns = data_context.get("columns", {})
    dimension_cols = []
    measurement_info = ""

    for col_name, col_info in columns.items():
        role = col_info.get("role", "")
        if role == "dimension":
            samples = col_info.get("sample_values", [])[:5]
            dimension_cols.append(f"{col_name} (values: {', '.join(str(s) for s in samples)})")
        elif role == "value":
            measurement_info = col_name

    population_type = data_context.get("population_type", "Thing")
    category = schema_category or "General"

    dims_text = "; ".join(dimension_cols) if dimension_cols else "none identified"
    measurement_text = measurement_info or "unspecified"

    return (
        f"I have a {category} dataset measuring {population_type} "
        f"with measurement column: {measurement_text}. "
        f"Dimensions: {dims_text}. "
        f"What existing Data Commons StatVars match this data? "
        f"Provide DCIDs and property decompositions for the best matches."
    )


def _build_property_question(data_context: dict) -> str:
    """Build Q2: Property mapping guidance from column info."""
    columns = data_context.get("columns", {})
    col_lines = []

    for col_name, col_info in columns.items():
        role = col_info.get("role", "unknown")
        semantic = col_info.get("semantic_type", "")
        samples = col_info.get("sample_values", [])[:3]
        samples_text = ", ".join(str(s) for s in samples)
        line = f"- {col_name} (role: {role}"
        if semantic:
            line += f", semantic: {semantic}"
        line += f", samples: {samples_text})"
        col_lines.append(line)

    if not col_lines:
        return ""

    return (
        "Map these CSV columns to Data Commons properties for a PVMAP:\n"
        + "\n".join(col_lines)
        + "\nFor each, what DC property should it map to? "
        "Include the property name and expected value format."
    )


def _build_category_question(schema_category: str) -> str:
    """Build Q3: Category-specific DC patterns."""
    category = schema_category or "General"
    return (
        f"What are the standard Data Commons property patterns, population types, "
        f"and measurement methods for {category} datasets? "
        f"Include common StatVar naming conventions and required properties."
    )


def _format_enrichment(answers: list[tuple[str, str]]) -> str:
    """Format Q&A pairs into markdown enrichment context."""
    sections = []
    titles = [
        "### StatVar Mapping Guidance",
        "### Property Mapping Guidance",
        "### Category-Specific DC Patterns",
    ]
    for (question, answer), title in zip(answers, titles):
        if answer:
            sections.append(f"{title}\n\n{answer}")

    if not sections:
        return ""

    return "\n\n".join(sections)


async def _ask_with_fallback(notebook_id: str, question: str) -> tuple[str, str]:
    """Ask a question, returning (question, answer) or (question, '') on failure."""
    if not question:
        return (question, "")
    try:
        from notebooklm.tools import ask_question
        result = await ask_question(notebook_id, question)
        if result.get("success"):
            return (question, result["data"].get("answer", ""))
        else:
            logger.warning("NotebookLM question failed: %s", result.get("error", "unknown"))
            return (question, "")
    except Exception as e:
        logger.warning("NotebookLM ask_question error: %s", e)
        return (question, "")


async def _create_notebook_with_sources() -> Optional[str]:
    """Create a new notebook and add DC documentation sources. Returns notebook_id or None."""
    try:
        from notebooklm.tools import create_notebook, add_url_source

        result = await create_notebook("DC Auto-Schematization Context")
        if not result.get("success"):
            logger.warning("Failed to create notebook: %s", result.get("error"))
            return None

        notebook_id = result["data"]["notebook_id"]
        logger.info("Created NotebookLM notebook: %s", notebook_id)

        # Add DC documentation URLs concurrently
        tasks = [add_url_source(notebook_id, url) for url in DC_DOC_URLS]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        added = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        logger.info("Added %d/%d DC documentation sources to notebook", added, len(DC_DOC_URLS))

        return notebook_id

    except Exception as e:
        logger.warning("Failed to create notebook with sources: %s", e)
        return None


class NotebookLMEnrichmentAgent(BaseAgent):
    """Agent that queries NotebookLM for Data Commons enrichment context.

    Runs between SchemaSelection and PVMAPRetryLoop. Asks 3 concurrent
    questions about the dataset's columns and domain, then stores the
    combined answers as enrichment context for the PVMAP prompt.
    """

    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # Check if enrichment is enabled
        nlm_enabled = ctx.session.state.get("nlm_enabled", False)
        if not nlm_enabled:
            logger.info("NotebookLM enrichment disabled, skipping")
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="NotebookLM enrichment: skipped (disabled)")]),
            )
            return

        logger.info("Starting NotebookLM enrichment")
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text="NotebookLM enrichment: starting...")]),
        )

        # Get notebook ID — try provided, then default, then auto-create
        notebook_id = ctx.session.state.get("nlm_notebook_id", "") or DEFAULT_NOTEBOOK_ID
        notebook_created = False

        # Test the notebook with a simple ping
        try:
            from notebooklm.tools import ask_question
            test_result = await ask_question(notebook_id, "What is Data Commons?")
            if not test_result.get("success"):
                logger.warning(
                    "Default notebook %s unreachable: %s. Attempting auto-create.",
                    notebook_id, test_result.get("error"),
                )
                new_id = await _create_notebook_with_sources()
                if new_id:
                    notebook_id = new_id
                    notebook_created = True
                else:
                    logger.warning("NotebookLM enrichment: unable to connect. Skipping.")
                    ctx.session.state["nlm_enrichment_context"] = ""
                    ctx.session.state["nlm_enrichment_success"] = False
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[types.Part(text="NotebookLM enrichment: skipped (connection failed)")]),
                    )
                    return
        except Exception as e:
            logger.warning("NotebookLM connection test failed: %s. Skipping enrichment.", e)
            ctx.session.state["nlm_enrichment_context"] = ""
            ctx.session.state["nlm_enrichment_success"] = False
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"NotebookLM enrichment: skipped ({e})")]),
            )
            return

        # Build questions from state
        data_context = ctx.session.state.get("data_context", {})
        schema_category = ctx.session.state.get("schema_category", "")

        q1 = _build_statvar_question(data_context, schema_category)
        q2 = _build_property_question(data_context)
        q3 = _build_category_question(schema_category)

        # Ask all 3 questions concurrently
        logger.info("Asking 3 enrichment questions to NotebookLM notebook %s", notebook_id)
        answers = await asyncio.gather(
            _ask_with_fallback(notebook_id, q1),
            _ask_with_fallback(notebook_id, q2),
            _ask_with_fallback(notebook_id, q3),
        )

        # Format enrichment
        enrichment = _format_enrichment(list(answers))
        success = bool(enrichment.strip())

        # Store in state
        ctx.session.state["nlm_enrichment_context"] = enrichment
        ctx.session.state["nlm_enrichment_success"] = success
        ctx.session.state["nlm_notebook_id"] = notebook_id
        ctx.session.state["nlm_notebook_created"] = notebook_created

        if success:
            logger.info(
                "NotebookLM enrichment complete: %d chars from %d answers",
                len(enrichment),
                sum(1 for _, a in answers if a),
            )
        else:
            logger.warning("NotebookLM enrichment: no useful answers received")

        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(
                text=f"NotebookLM enrichment: {'success' if success else 'no answers'} "
                     f"({len(enrichment)} chars)"
            )]),
        )

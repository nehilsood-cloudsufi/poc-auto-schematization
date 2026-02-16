"""
Schema Selection Agent for ADK pipeline.

Selects appropriate schema category based on data analysis.
Uses Pattern 2: LlmAgent with Tools (no custom class needed!).

This is a factory function that returns a configured LlmAgent.

Simplified: Uses skeleton_summary from SamplingAgent exclusively for
category decision (no redundant CSV re-reading). Also reads compressed
schema vocab and stores it in state for downstream PVMAP generation.
"""

import logging
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

from google.adk.agents import LlmAgent
from src.agents.prompt_loader import load_prompt
from src.agents.retry_config import create_resilient_model
from src.tools.schema_tools import (
    get_schema_categories,
    copy_schema_files,
    read_schema_vocab
)
from src.tools.schemaorg_tools import search_schemaorg_vocabulary, lookup_schemaorg_type

_SCHEMA_SELECTION_INSTRUCTION = load_prompt("schema_selection_agent.txt")


def create_schema_selection_agent(
    name: str = "SchemaSelectionAgent",
    model: str = "gemini-2.5-pro"
) -> LlmAgent:
    """
    Create a SchemaSelectionAgent using LlmAgent with schema tools.

    No custom class needed - LlmAgent handles _run_async_impl automatically!

    Simplified from previous version:
    - Removed generate_data_preview tool (skeleton_summary has all needed info)
    - Added read_schema_vocab tool (stores compressed vocab in state)
    - Instruction updated to use skeleton_summary exclusively

    ADK State Inputs:
        - current_dataset: DatasetInfo - Current dataset being processed
        - skip_schema_selection: bool - Whether to skip schema selection
        - force_schema_selection: bool - Whether to force new selection
        - skeleton_summary: str - Enriched summary from SamplingAgent
        - data_context: Dict - Data context from SamplingAgent (column_roles, dimensions)

    ADK State Outputs:
        - schema_category: str - Selected schema category name
        - schema_vocab_content: str - Formatted vocab for PVMAP prompt (from copy_schema_files)

    Args:
        name: Agent name (default: "SchemaSelectionAgent")
        model: Gemini model to use (default: "gemini-3-pro-preview")

    Returns:
        Configured LlmAgent ready to use
    """

    logger.info("Creating SchemaSelectionAgent: model=%s, tools=%d", model, 5)

    return LlmAgent(
        name=name,
        model=create_resilient_model(model),
        instruction=_SCHEMA_SELECTION_INSTRUCTION,
        tools=[
            get_schema_categories,
            copy_schema_files,
            read_schema_vocab,
            search_schemaorg_vocabulary,
            lookup_schemaorg_type,  # Verify primary type for selected category
        ],
        output_key="schema_category"  # Automatically stores selected category in state
    )

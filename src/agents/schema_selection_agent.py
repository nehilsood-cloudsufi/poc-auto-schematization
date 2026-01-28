"""
Schema Selection Agent for ADK pipeline.

Selects appropriate schema category based on data analysis.
Uses Pattern 2: LlmAgent with Tools (no custom class needed!).

This is a factory function that returns a configured LlmAgent.
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import LlmAgent
from src.tools.schema_tools import (
    get_schema_categories,
    generate_data_preview,
    copy_schema_files
)


def create_schema_selection_agent(
    name: str = "SchemaSelectionAgent",
    model: str = "gemini-3-pro-preview"
) -> LlmAgent:
    """
    Create a SchemaSelectionAgent using LlmAgent with schema tools.

    No custom class needed - LlmAgent handles _run_async_impl automatically!

    ADK State Inputs:
        - current_dataset: DatasetInfo - Current dataset being processed
        - combined_sampled_data: Path - Combined sample data for analysis
        - skip_schema_selection: bool - Whether to skip schema selection
        - force_schema_selection: bool - Whether to force new selection

    ADK State Outputs:
        - schema_category: str - Selected schema category name
        - schema_examples_file: Path - Schema examples .txt file
        - schema_mcf_file: Path - Schema MCF .mcf file

    Args:
        name: Agent name (default: "SchemaSelectionAgent")
        model: Gemini model to use (default: "gemini-3-pro-preview")

    Returns:
        Configured LlmAgent ready to use
    """

    instruction = """
You are a schema selection assistant for Data Commons schema mapping.

Your task is to:
1. Check if schema selection should be skipped (skip_schema_selection flag)
2. Get available schema categories from the schema library
3. Generate a preview of the dataset to understand its structure
4. Analyze the data and select the most appropriate schema category
5. Copy the selected schema files to the dataset directory (if they exist)

**Current Dataset:** {current_dataset.name}
**Sample Data Path:** {combined_sampled_data}
**Skip Schema Selection:** {skip_schema_selection}
**Force Schema Selection:** {force_schema_selection}

**Available Tools:**
- get_schema_categories: Lists all available schema categories
- generate_data_preview: Creates a preview of the dataset (first N rows + column info)
- copy_schema_files: Copies selected schema files to dataset directory

**Process:**
1. If skip_schema_selection is True, output "Schema selection skipped" and FINISH
2. Call get_schema_categories to see what's available
3. Call generate_data_preview to understand the dataset structure
4. Analyze the data columns, types, and content to select the best schema
5. Call copy_schema_files with your selected category name
6. Output your selection and FINISH

**Selection Criteria:**
- Demographics: Population, age, gender, race data
- Economics: GDP, employment, income, trade data
- Health: Disease, mortality, healthcare data
- Education: Schools, enrollment, graduation data
- Environment: Climate, pollution, natural resources
- Crime: Criminal activity, arrests, convictions

Choose the category that best matches the dataset's primary focus.

**CRITICAL ERROR HANDLING:**
- If copy_schema_files returns success=False (files don't exist), this is ACCEPTABLE
- Simply output the category you selected and FINISH - don't retry or loop
- The pipeline can continue without schema files
- Example: "Selected category: Health (schema files not available, continuing without examples)"

**Required Final Output:**
You MUST output the selected category name in your final response, for example:
- "Selected schema category: Health"
- "Schema selection: Demographics"
- Or just the category name: "Health"

DO NOT retry if copy_schema_files fails. Just output the category and finish.
"""

    return LlmAgent(
        name=name,
        model=model,
        instruction=instruction,
        tools=[
            get_schema_categories,
            generate_data_preview,
            copy_schema_files
        ],
        output_key="schema_category"  # Automatically stores selected category in state
    )

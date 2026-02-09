"""
Schema Selection Agent for ADK pipeline.

Selects appropriate schema category based on data analysis.
Uses Pattern 2: LlmAgent with Tools (no custom class needed!).

This is a factory function that returns a configured LlmAgent.

Simplified: Uses skeleton_summary from SamplingAgent exclusively for
category decision (no redundant CSV re-reading). Also reads compressed
schema vocab and stores it in state for downstream PVMAP generation.
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
    copy_schema_files,
    read_schema_vocab
)


def create_schema_selection_agent(
    name: str = "SchemaSelectionAgent",
    model: str = "gemini-3-pro-preview"
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

    instruction = """
You are a schema selection assistant for Data Commons schema mapping.

Your task is to:
1. Check if schema selection should be skipped (skip_schema_selection flag)
2. Get available schema categories from the schema library
3. Use the skeleton_summary and data_context to select the most appropriate category
4. Copy the selected schema files to the dataset directory (if they exist)

**Current Dataset:** {current_dataset.name}
**Skip Schema Selection:** {skip_schema_selection}
**Force Schema Selection:** {force_schema_selection}

**Skeleton Summary (enriched, from SamplingAgent):** {skeleton_summary}
The skeleton_summary contains a complete column classification table (Section 2),
dimension deep dive (Section 4), and measurement info (Section 5).
Use this as the PRIMARY source for understanding the dataset structure.
Do NOT request data previews — all needed information is in skeleton_summary.

**Data Context (from SamplingAgent):** {data_context}
- column_roles: Maps each column to its role (place, time, dimension, value, metadata)
- dimension_columns: List of dimension columns that define StatVar uniqueness
- population_type: Inferred population type (Person, Household, etc.)

**Schema Base Directory:** {schema_base_dir}
**Dataset Input Directory:** {current_dataset.path}

**Available Tools:**
- get_schema_categories: Lists all available schema categories
- copy_schema_files: Copies selected schema files to dataset directory
- read_schema_vocab: Reads compressed schema vocabulary for a category (optional, for verification)

**Process:**
1. If skip_schema_selection is True, output "Schema selection skipped" and FINISH
2. Call get_schema_categories to see what's available
3. Use skeleton_summary column_roles and dimension_columns to inform your decision:
   - If dimensions include gender, age, race → Demographics
   - If dimensions include industry, sector, occupation → Employment/Economy
   - If dimensions include disease, condition, treatment → Health
   - If dimensions include grade, school, enrollment → Education
   - If columns mention energy, power, generation → Energy
4. Call copy_schema_files with:
   - category: your selected category name
   - schema_base_dir: "{schema_base_dir}" (the schema base directory shown above)
   - input_dir: "{current_dataset.path}" (the dataset input directory shown above)
5. Output your selection and FINISH

**Selection Criteria (use skeleton_summary and data_context to guide):**
- Demographics: Population, age, gender, race data (population_type=Person with demographic dimensions)
- Economics: GDP, business establishments, revenue, trade data
- Health: Disease, mortality, healthcare data
- Education: Schools, enrollment, graduation data
- Employment: Labor force, jobs, wages, unemployment (dimension includes occupation/industry)
- Energy: Power generation, consumption, renewable energy
- Environment: Climate, pollution, natural resources

Choose the category that best matches the dataset's primary focus and detected dimensions.

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
            copy_schema_files,
            read_schema_vocab
        ],
        output_key="schema_category"  # Automatically stores selected category in state
    )

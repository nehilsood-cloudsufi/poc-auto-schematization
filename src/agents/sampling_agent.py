# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#         https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Agentic Data Sampling Agent for ADK pipeline.

This agent uses an LLM to make sampling decisions based on data evidence,
rather than hardcoded heuristics. The LLM decides:
- Which columns are place/time/dimension/value
- What sampling strategy to use
- How many rows to sample

The agent has access to 5 tools that provide statistical evidence:
1. preview_data - Quick overview of file structure
2. analyze_columns - Statistical analysis for classification
3. sample_rows - Execute sampling with chosen strategy
4. check_coverage - Validate dimension hypothesis
5. generate_context - Create DataContext for PVMAP generation

Data Commons Context:
The downstream PVMAP generator needs to understand the data's "Skeleton":
- Anchors: Place (observationAbout) + Time (observationDate)
- Dimensions: Categorical columns that define StatVar uniqueness
- Values: Numeric measurement columns

Rule: Place + Time + StatVar (defined by dimensions) = Unique Observation
"""

import json
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.tools import FunctionTool
from google.genai import types

from src.tools.sampling_tools import (
    preview_data,
    analyze_columns,
    sample_rows,
    check_coverage,
    generate_context,
)


# ============================================================================
# Agent Instruction
# ============================================================================

SAMPLING_AGENT_INSTRUCTION = """
You are a Data Sampling Agent for Data Commons PVMAP generation.

Your job: Understand the data SKELETON and create a strategic sample that
demonstrates how dimensions define unique StatVarObservations.

## IMPORTANT: Check Session State First

Before doing any work, check the session state for:
- `skip_sampling`: If True, skip all work and report success
- `force_resample`: If True, always create new samples even if they exist
- `current_dataset`: The dataset to process (contains path and file info)

## PROCESS

### Step 1: Check Skip Flag
If `skip_sampling` is True in the session state, immediately report success
without doing any work.

### Step 2: Preview Data
Call `preview_data` on the input file to see structure. Look for:
- Column names that suggest place (State, FIPS, Country, geoId)
- Column names that suggest time (Year, Date, Period)
- Wide vs Tall format (are dimensions in headers or rows?)

### Step 3: Analyze Columns (Get Evidence)
Call `analyze_columns` to get statistical evidence:
- Cardinality ratio < 0.1 → likely DIMENSION
- Cardinality ratio > 0.5 + numeric → likely VALUE
- `looks_like_place` = True → likely PLACE
- `looks_like_date` = True → likely TIME

### Step 4: Classify Columns (Your Decision)
Based on evidence, classify EACH column as:
- **place**: Geographic identifier → maps to `observationAbout`
- **time**: Temporal identifier → maps to `observationDate`
- **dimension**: Categorical constraint → defines StatVar uniqueness
- **value**: Numeric measurement → maps to `value`
- **metadata**: Descriptive (source, unit) → context only

### Step 5: Form Hypothesis
Identify which columns form the SKELETON:
"Rows are unique by: Place + Time + [Dimension1, Dimension2, ...]"

### Step 6: Design Sampling Strategy
Based on data format:
- **Tall data with dimensions**: Use `fixed_pivot` mode
  - Fix one place + time, vary all dimensions
  - Shows LLM how dimensions define StatVar
- **Wide data (values in headers)**: Use `head` mode
  - Structure is visible in column names
- **High-cardinality dimensions**: Use `stratified` mode
  - Ensure every dimension value appears

Call `sample_rows` with your chosen strategy:
- mode: "random" | "head" | "stratified" | "fixed_pivot"
- target_rows: 60-100 rows (default 80)
- stratify_by: List of dimension columns (for stratified)
- pivot_config: {"fix": {col: val}, "vary": [cols]} (for fixed_pivot)

### Step 7: Validate Hypothesis
Call `check_coverage` with your dimension hypothesis:
- If `is_unique=True` → hypothesis correct
- If `is_unique=False` → missed a dimension, revise and retry

### Step 8: Generate Context
Call `generate_context` with your classifications.
This creates the skeleton_summary for PVMAP generation.

Store results in session state:
- `sampled_data_files`: List of sampled file paths
- `combined_sampled_data`: Path to main sampled file
- `sampling_success`: True
- `data_context`: Dict from generate_context
- `skeleton_summary`: String from generate_context
- `column_roles`: Your classification dict
- `dimension_columns`: List of dimension column names

## DATA COMMONS UNIQUENESS RULE

> StatVarObservation = Place + Time + StatVar
> StatVar = Measurement + Dimensions (constraints)

If two rows have same Place + Time but different values, there MUST be
a dimension column that differentiates them (gender, age, race, etc.)

## IMPORTANT GUIDELINES

- Tools give EVIDENCE, YOU make DECISIONS
- Don't assume domain - let data tell you
- Target 60-100 rows in sample
- Skeleton sample is MORE important than random coverage

## EDGE CASE: No Clear Dimensions

If analyze_columns shows all columns are unique or highly numeric (no low-cardinality
categorical columns):
1. Use simple `head` sampling (first 60-80 rows)
2. Still provide your analysis of what the columns likely represent
3. Note in context: "No clear dimension columns detected"
4. Let PVMAP agent make the final determination

## EDGE CASE: Pre-formatted Data Commons Data

If columns include `observationAbout`, `observationDate`, `variableMeasured`, `value`:
1. This is already DC-formatted data
2. Use simple `head` sampling
3. Set column_roles to match the DC format
4. Note in context: "Pre-formatted Data Commons data detected"

## OUTPUT FORMAT

After completing all steps, summarize:
1. Column classifications you made
2. Sampling strategy used
3. Coverage statistics
4. Any issues or warnings

Example:
```
Sampling complete for dataset_name:
- Place column: state_fips
- Time column: year
- Dimensions: gender, age_group (2 columns)
- Values: population_count, estimate (2 columns)
- Strategy: stratified by [gender, age_group]
- Sampled: 78 rows covering 95% of dimension combinations
```
"""


# ============================================================================
# Agent Factory
# ============================================================================

def create_sampling_agent(
    name: str = "SamplingAgent",
    model: Optional[str] = None,
) -> LlmAgent:
    """Create an agentic Data Sampling Agent with forced tool calling.

    This agent uses an LLM to make intelligent sampling decisions based on
    data evidence, rather than relying on hardcoded heuristics.

    The agent has access to 5 tools:
    1. preview_data - Quick overview of file structure
    2. analyze_columns - Statistical analysis for classification
    3. sample_rows - Execute sampling with chosen strategy
    4. check_coverage - Validate dimension hypothesis
    5. generate_context - Create DataContext for PVMAP generation

    Uses FunctionCallingConfigMode.ANY to ensure the LLM MUST call at least
    one tool per turn, guaranteeing the workflow is followed.

    Args:
        name: Agent name (default: "SamplingAgent")
        model: LLM model to use (default: from SAMPLING_AGENT_MODEL env var
               or "gemini-2.5-flash")

    Returns:
        Configured LlmAgent ready for pipeline integration
    """
    # Get model from environment or use default
    if model is None:
        model = os.getenv("SAMPLING_AGENT_MODEL", "gemini-2.5-flash")

    # Create function tools
    tools = [
        FunctionTool(func=preview_data),
        FunctionTool(func=analyze_columns),
        FunctionTool(func=sample_rows),
        FunctionTool(func=check_coverage),
        FunctionTool(func=generate_context),
    ]

    # Force tool calling with mode=ANY
    # This ensures the LLM MUST call at least one tool per turn,
    # guaranteeing it follows the complete workflow including generate_context
    generate_content_config = types.GenerateContentConfig(
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode=types.FunctionCallingConfigMode.ANY
            )
        )
    )

    # Create LlmAgent with forced tool calling
    agent = LlmAgent(
        name=name,
        model=model,
        instruction=SAMPLING_AGENT_INSTRUCTION,
        tools=tools,
        generate_content_config=generate_content_config,
    )

    return agent


# ============================================================================
# Backward Compatibility: SamplingAgent class wrapper
# ============================================================================

class SamplingAgent:
    """Wrapper class for backward compatibility.

    The old SamplingAgent was a BaseAgent subclass. This wrapper provides
    the same interface while delegating to the new LlmAgent-based implementation.

    For new code, use create_sampling_agent() directly.
    """

    def __init__(self, name: str = "SamplingAgent", model: Optional[str] = None):
        """Initialize SamplingAgent wrapper.

        Args:
            name: Agent name
            model: LLM model to use
        """
        self._agent = create_sampling_agent(name=name, model=model)
        self.name = name

    @property
    def agent(self) -> LlmAgent:
        """Return the underlying LlmAgent."""
        return self._agent

    def __getattr__(self, name):
        """Delegate attribute access to underlying agent."""
        return getattr(self._agent, name)


# ============================================================================
# SamplingAgentWrapper: BaseAgent for Pipeline Integration
# ============================================================================

class SamplingAgentWrapper(BaseAgent):
    """
    BaseAgent wrapper that manages session state for SamplingAgent.

    The LlmAgent-based SamplingAgent generates context but doesn't automatically
    persist structured results to session state. This wrapper:
    1. Reads current_dataset from session state
    2. Creates the inner LlmAgent and runs it with file paths
    3. Reads the generated data_context.json file
    4. Stores skeleton_summary, data_context, etc. to session state

    ADK State Inputs:
        - current_dataset: DatasetInfo - Current dataset being processed
        - skip_sampling: bool - If True, skip sampling entirely
        - force_resample: bool - If True, always re-run sampling

    ADK State Outputs:
        - skeleton_summary: str - Markdown summary for PVMAP prompt
        - data_context: dict - Full context dictionary
        - column_roles: dict - Column classification
        - dimension_columns: list - Dimension column names
        - sampling_success: bool - Whether sampling succeeded
        - sampled_data_path: str - Path to sampled CSV file
    """

    def __init__(
        self,
        name: str = "SamplingAgent",
        model: Optional[str] = None,
    ):
        """
        Initialize SamplingAgentWrapper.

        Args:
            name: Agent name
            model: LLM model to use (default: from SAMPLING_AGENT_MODEL env var
                   or "gemini-2.5-pro")
        """
        super().__init__(name=name)
        self._model = model or os.getenv("SAMPLING_AGENT_MODEL", "gemini-2.5-pro")
        self._fallback_model = "gemini-2.5-flash"
        self._timeout = float(os.getenv("SAMPLING_AGENT_TIMEOUT", "300"))

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Run sampling workflow and persist results to session state.
        """
        import asyncio

        # Check skip flag
        skip_sampling = ctx.session.state.get("skip_sampling", False)
        if skip_sampling:
            yield self._create_event("Sampling skipped per skip_sampling flag")
            ctx.session.state["sampling_success"] = True
            ctx.session.state["skeleton_summary"] = ""
            return

        # Get current dataset from state
        current_dataset = ctx.session.state.get("current_dataset")
        if not current_dataset:
            yield self._create_event("No current_dataset in session state, skipping sampling")
            ctx.session.state["sampling_success"] = False
            ctx.session.state["error"] = "No current_dataset specified"
            return

        # Get input file path
        input_file = None
        if current_dataset.input_data_files:
            input_file = str(current_dataset.input_data_files[0])
        elif current_dataset.combined_input_data:
            input_file = str(current_dataset.combined_input_data)

        if not input_file or not Path(input_file).exists():
            yield self._create_event(f"No input file found for dataset {current_dataset.name}")
            ctx.session.state["sampling_success"] = False
            ctx.session.state["error"] = "No input data file available"
            return

        # Set up output paths
        output_dir = Path(current_dataset.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = str(output_dir / "agentic_sampled.csv")
        context_file = output_dir / "data_context.json"

        yield self._create_event(f"Starting agentic sampling for {current_dataset.name}")
        yield self._create_event(f"Input: {Path(input_file).name}, Output: {output_file}")

        # Check if we should skip (existing context file and not force_resample)
        force_resample = ctx.session.state.get("force_resample", False)
        if context_file.exists() and not force_resample:
            yield self._create_event(f"Found existing data_context.json, loading from cache")
            try:
                with open(context_file, 'r', encoding='utf-8') as f:
                    cached_context = json.load(f)
                self._populate_state_from_context(ctx, cached_context, str(context_file))
                yield self._create_event("Loaded cached sampling context successfully")
                return
            except Exception as e:
                yield self._create_event(f"Failed to load cached context: {e}, re-running sampling")

        # Create the inner LlmAgent
        sampling_llm = create_sampling_agent(name=f"{self.name}_LLM", model=self._model)

        # Construct message with file paths for the LLM
        message_text = f"""
Sample the data file and generate context for PVMAP generation.

Input file: {input_file}
Output sampled file: {output_file}

Follow the complete workflow:
1. Call preview_data with file_path="{input_file}" to see structure
2. Call analyze_columns with file_path="{input_file}" to get evidence
3. Call sample_rows with file_path="{input_file}", output_path="{output_file}", and strategy_json based on your analysis
4. Call check_coverage with sampled_file="{output_file}" and your identified columns
5. Call generate_context with sampled_file="{output_file}", your classifications as column_roles_json, and dimension_columns list

CRITICAL: You MUST call generate_context at the end to create the skeleton_summary.
The generate_context tool will write the results to a JSON file.
"""

        # Run the LlmAgent using Runner (same pattern as StatVarDiscoveryAgent)
        try:
            from google.adk import Runner
            from google.adk.sessions import InMemorySessionService
            import uuid

            # Create a runner for the sampling agent
            runner = Runner(
                app_name="sampling",
                agent=sampling_llm,
                session_service=InMemorySessionService(),
                auto_create_session=True
            )

            session_id = f"sampling_{uuid.uuid4().hex[:8]}"
            user_message = types.Content(parts=[types.Part(text=message_text)])

            yield self._create_event("Running LLM sampling agent...")

            result_text = ""
            max_events = 50  # Limit to prevent infinite loops with forced tool calling
            event_count = 0

            for event in runner.run(user_id="sampler", session_id=session_id, new_message=user_message):
                event_count += 1
                if event_count > max_events:
                    yield self._create_event(f"Max events ({max_events}) reached, stopping sampling agent")
                    break

                if hasattr(event, 'content') and event.content:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            result_text += part.text

            yield self._create_event(f"LLM sampling agent completed ({event_count} events)")

        except Exception as e:
            yield self._create_event(f"Sampling LLM error: {str(e)}")
            ctx.session.state["sampling_success"] = False
            ctx.session.state["error"] = str(e)
            return

        # After LLM finishes, read the generated context file
        # With FunctionCallingConfigMode.ANY, the LLM is forced to call tools,
        # so generate_context should always be called and context_file should exist
        if context_file.exists():
            try:
                with open(context_file, 'r', encoding='utf-8') as f:
                    data_context = json.load(f)
                self._populate_state_from_context(ctx, data_context, str(context_file))
                yield self._create_event(f"Sampling complete. Skeleton summary stored in state.")
            except Exception as e:
                yield self._create_event(f"Warning: Failed to read data_context.json: {e}")
                ctx.session.state["sampling_success"] = False
                ctx.session.state["error"] = f"Failed to read context file: {e}"
        else:
            # Context file not created - this should not happen with forced tool calling
            yield self._create_event("ERROR: LLM didn't call generate_context despite forced tool calling")
            ctx.session.state["skeleton_summary"] = ""
            ctx.session.state["sampling_success"] = False
            ctx.session.state["error"] = "generate_context was not called by the LLM"

    def _populate_state_from_context(
        self,
        ctx: InvocationContext,
        data_context: dict,
        context_file_path: str
    ):
        """Populate session state from data context dict."""
        ctx.session.state["skeleton_summary"] = data_context.get("skeleton_summary", "")
        ctx.session.state["data_context"] = data_context.get("data_context", data_context)
        ctx.session.state["column_roles"] = data_context.get("column_roles", {})
        ctx.session.state["dimension_columns"] = data_context.get("dimension_columns", [])
        ctx.session.state["sampling_success"] = data_context.get("success", True)
        ctx.session.state["context_file_path"] = context_file_path

        # Also update combined_sampled_data if available
        if data_context.get("data_context", {}).get("sampled_file"):
            sampled_path = data_context["data_context"]["sampled_file"]
            ctx.session.state["sampled_data_path"] = sampled_path

    def _create_event(self, text: str) -> Event:
        """Create an event with text content."""
        return Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=text)])
        )


# ============================================================================
# Module exports
# ============================================================================

__all__ = [
    'create_sampling_agent',
    'SamplingAgent',
    'SamplingAgentWrapper',
    'SAMPLING_AGENT_INSTRUCTION',
]

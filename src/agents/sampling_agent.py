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
import logging
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

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
from src.agents.retry_config import create_resilient_model
from src.agents.template_utils import build_thinking_config


# ============================================================================
# Agent Instruction
# ============================================================================

from src.agents.prompt_loader import load_prompt

SAMPLING_AGENT_INSTRUCTION = load_prompt("sampling_agent.txt")


# ============================================================================
# Agent Factory
# ============================================================================

def create_sampling_agent(
    name: str = "SamplingAgent",
    model: Optional[str] = None,
    thinking_level: Optional[str] = None,
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
    config_kwargs = dict(
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode=types.FunctionCallingConfigMode.ANY
            )
        )
    )
    thinking_config = build_thinking_config(thinking_level, model=model)
    if thinking_config:
        config_kwargs["thinking_config"] = thinking_config
    generate_content_config = types.GenerateContentConfig(**config_kwargs)

    # Create LlmAgent with forced tool calling
    agent = LlmAgent(
        name=name,
        model=create_resilient_model(model),
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

    def __init__(self, name: str = "SamplingAgent", model: Optional[str] = None,
                 thinking_level: Optional[str] = None):
        """Initialize SamplingAgent wrapper.

        Args:
            name: Agent name
            model: LLM model to use
            thinking_level: Thinking level for Gemini models
        """
        self._agent = create_sampling_agent(name=name, model=model, thinking_level=thinking_level)
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
        thinking_level: Optional[str] = None,
    ):
        """
        Initialize SamplingAgentWrapper.

        Args:
            name: Agent name
            model: LLM model to use (default: from SAMPLING_AGENT_MODEL env var
                   or "gemini-2.5-pro")
            thinking_level: Thinking level for Gemini models
        """
        super().__init__(name=name)
        self._model = model or os.getenv("SAMPLING_AGENT_MODEL", "gemini-2.5-pro")
        self._thinking_level = thinking_level
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
        sampling_llm = create_sampling_agent(
            name=f"{self.name}_LLM", model=self._model,
            thinking_level=self._thinking_level,
        )

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
                yield self._create_event(f"ERROR: Failed to read data_context.json: {e}")
                yield self._create_event("Check Gemini API status or manually create agentic_sampled.csv + data_context.json")
                ctx.session.state["sampling_success"] = False
                ctx.session.state["error"] = f"Failed to read context file: {e}"
        else:
            # Context file not created
            yield self._create_event("ERROR: LLM didn't call generate_context despite forced tool calling")
            yield self._create_event("Check Gemini API status or manually create agentic_sampled.csv + data_context.json")
            ctx.session.state["skeleton_summary"] = ""
            ctx.session.state["sampling_success"] = False
            ctx.session.state["error"] = "generate_context was not called by the LLM"

    def _populate_state_from_context(
        self,
        ctx: InvocationContext,
        data_context: dict,
        context_file_path: str
    ):
        """Populate session state from data context dict.

        State Keys (2 keys, ordered by importance):

        1. skeleton_summary (str) — PRIMARY output. Enriched 9-section markdown
           injected directly into the PVMAP generation prompt via {{DATA_CONTEXT}}.
           All downstream LLM consumers should prefer this key.

        2. data_context (dict) — SECONDARY output. Full structured dict for
           programmatic access (evaluation agent, MCP queries, debugging).
           Contains column_roles and dimension_columns for any agent that
           needs them (e.g. data_context.get("column_roles")).
        """
        ctx.session.state["skeleton_summary"] = data_context.get("skeleton_summary", "")
        ctx.session.state["data_context"] = data_context.get("data_context", data_context)
        ctx.session.state["sampling_success"] = data_context.get("success", True)
        ctx.session.state["context_file_path"] = context_file_path

        inner_ctx = data_context.get("data_context", {})
        logger.info(
            "Sampling complete: rows=%s, columns=%s, dimensions=%s",
            inner_ctx.get("row_count", "?"),
            inner_ctx.get("column_count", "?"),
            inner_ctx.get("dimension_columns", []),
        )

        # Set sampled_data_path in state for downstream agents
        sampled_path = data_context.get("data_context", {}).get("sampled_file")
        if sampled_path:
            ctx.session.state["sampled_data_path"] = sampled_path
        else:
            # Fallback: derive from output_dir (where agentic_sampled.csv is written)
            current_dataset = ctx.session.state.get("current_dataset")
            if current_dataset and hasattr(current_dataset, 'output_dir'):
                fallback = Path(current_dataset.output_dir) / "agentic_sampled.csv"
                if fallback.exists():
                    ctx.session.state["sampled_data_path"] = str(fallback)

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

"""
PVMAP Retry Loop using ADK LoopAgent.

This module creates a LoopAgent that orchestrates:
1. PVMAPGeneratorAgent - Generates PVMAP with structured output
2. ValidationAgent - Validates and escalates on success
3. FeedbackAgent - Analyzes errors for retry

The loop exits when:
- ValidationAgent escalates (validation passed), OR
- max_iterations is reached (default: 3)

Key ADK features used:
- LoopAgent for automatic retry mechanism
- EventActions.escalate for early exit on success
- Session state for passing data between iterations
"""

import os
import sys
from pathlib import Path
from typing import Optional, AsyncGenerator

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import LoopAgent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from src.agents.pvmap_generator_agent import create_pvmap_generator
from src.agents.validation_agent import ValidationAgent
from src.agents.feedback_agent import create_feedback_agent


class StatePreparationAgent(BaseAgent):
    """
    Prepares session state before each generator iteration.

    This agent:
    1. Reads data files and populates state with content
    2. Increments attempt_number for tracking
    3. Ensures required state variables are set for the generator

    This is necessary because LlmAgent with output_schema reads state
    via instruction templating, so we need to ensure the state is populated
    with the actual file contents before the generator runs.
    """

    def __init__(self, name: str = "StatePrep"):
        super().__init__(name=name)

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Prepare state for generator iteration."""

        # Increment attempt number (starts at 0)
        current_attempt = ctx.session.state.get("attempt_number", -1)
        ctx.session.state["attempt_number"] = current_attempt + 1
        attempt = ctx.session.state["attempt_number"]

        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text=f"Preparing state for attempt {attempt + 1}...")
            ])
        )

        # Get dataset info
        current_dataset = ctx.session.state.get("current_dataset")
        if not current_dataset:
            ctx.session.state["state_prep_error"] = "No current_dataset in state"
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="ERROR: No current_dataset in state")
                ])
            )
            return

        # Read and populate schema_examples if not already in state
        if "schema_examples" not in ctx.session.state or not ctx.session.state["schema_examples"]:
            schema_content = ""
            if current_dataset.schema_examples and Path(current_dataset.schema_examples).exists():
                try:
                    schema_content = Path(current_dataset.schema_examples).read_text(encoding='utf-8')
                except Exception as e:
                    schema_content = f"(Error reading schema: {e})"
            else:
                schema_content = (
                    "No schema example files found. Generate PVMAP based on "
                    "data structure and Data Commons conventions."
                )
            ctx.session.state["schema_examples"] = schema_content

        # Read and populate sampled_data if not already in state
        if "sampled_data" not in ctx.session.state or not ctx.session.state["sampled_data"]:
            sampled_data = ""
            sampled_path = current_dataset.combined_sampled_data
            if sampled_path and Path(sampled_path).exists():
                try:
                    sampled_data = Path(sampled_path).read_text(encoding='utf-8')
                except Exception as e:
                    sampled_data = f"(Error reading sampled data: {e})"
            ctx.session.state["sampled_data"] = sampled_data

        # Read and populate metadata if not already in state
        if "metadata" not in ctx.session.state or not ctx.session.state["metadata"]:
            metadata = ""
            metadata_path = current_dataset.combined_metadata
            if metadata_path and Path(metadata_path).exists():
                try:
                    metadata = Path(metadata_path).read_text(encoding='utf-8')
                except Exception as e:
                    metadata = f"(Error reading metadata: {e})"
            ctx.session.state["metadata"] = metadata

        # Ensure optional state variables have defaults (for instruction templating)
        if "skeleton_summary" not in ctx.session.state:
            ctx.session.state["skeleton_summary"] = ""
        if "statvar_summary" not in ctx.session.state:
            ctx.session.state["statvar_summary"] = ""
        if "structure_warnings" not in ctx.session.state:
            ctx.session.state["structure_warnings"] = ""

        # Log error feedback status (critical for debugging retry loop)
        existing_feedback = ctx.session.state.get("error_feedback", "")
        if existing_feedback and attempt > 0:
            feedback_preview = existing_feedback[:200] + "..." if len(existing_feedback) > 200 else existing_feedback
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Error feedback from attempt {attempt}: {feedback_preview}")
                ])
            )
        elif attempt == 0:
            # First attempt - ensure error_feedback exists but is empty
            ctx.session.state["error_feedback"] = ""
        # NOTE: Don't reset error_feedback on retries - FeedbackAgent sets it

        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text=f"State prepared for attempt {attempt + 1}")
            ])
        )


class MaxRetriesCheckAgent(BaseAgent):
    """
    Checks if max retries exceeded after FeedbackAgent runs.

    If max retries reached, sets final failure state and escalates
    to exit the loop (even though validation failed).
    """

    def __init__(self, name: str = "MaxRetriesCheck", max_retries: int = 2):
        super().__init__(name=name)
        self._max_retries = max_retries

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Check if max retries exceeded."""

        attempt = ctx.session.state.get("attempt_number", 0)

        if attempt >= self._max_retries:
            # Max retries reached - set failure state and exit loop
            ctx.session.state["generation_success"] = False
            ctx.session.state["retry_count"] = attempt
            error_feedback = ctx.session.state.get("error_feedback", "Unknown error")
            ctx.session.state["error"] = f"Max retries ({self._max_retries + 1}) exceeded. Last error: {error_feedback[:500]}"

            # Update generation notes with final failure status
            try:
                from src.agents.pvmap_generation.helpers import update_generation_notes
                current_dataset = ctx.session.state.get("current_dataset")
                if current_dataset:
                    update_generation_notes(
                        output_dir=Path(current_dataset.output_dir),
                        dataset_name=current_dataset.name,
                        attempt=attempt,
                        llm_result=ctx.session.state.get("pvmap_llm_result", {}),
                        pvmap_csv=ctx.session.state.get("pvmap_csv"),
                        validation_result={"success": False, "error": error_feedback},
                        final_status=f"FAILED after {self._max_retries + 1} attempts"
                    )
            except Exception:
                pass  # Don't fail on logging errors

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Max retries ({self._max_retries + 1}) exceeded. Exiting loop with failure.")
                ]),
                actions=EventActions(escalate=True)  # Exit loop
            )
        else:
            # More retries available
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Attempt {attempt + 1} failed. {self._max_retries - attempt} retries remaining.")
                ]),
                actions=EventActions(escalate=False)  # Continue loop
            )


def create_pvmap_retry_loop(
    model: str = "gemini-2.5-flash",
    max_retries: int = 2,
    use_structured_output: bool = True,
    name: str = "PVMAPRetryLoop",
) -> LoopAgent:
    """
    Create PVMAP generation retry loop using ADK LoopAgent.

    The loop runs:
    1. StatePreparationAgent - Prepares state for generator
    2. PVMAPGeneratorAgent - Generates PVMAP (structured JSON)
    3. ValidationAgent - Validates; ESCALATES on success to exit loop
    4. FeedbackAgent - Analyzes errors for next iteration
    5. MaxRetriesCheckAgent - Checks if max retries exceeded

    The loop exits when:
    - ValidationAgent escalates (success), OR
    - MaxRetriesCheckAgent escalates (max retries), OR
    - max_iterations reached (fallback)

    Args:
        model: Gemini model for generation (default: gemini-2.5-flash)
        max_retries: Max retry attempts (default: 2, for 3 total attempts)
        use_structured_output: Use output_schema for structured JSON (default: True)
        name: Loop agent name (default: PVMAPRetryLoop)

    Returns:
        Configured LoopAgent

    State Inputs (must be set before loop):
        - current_dataset: DatasetInfo - Dataset being processed

    State Outputs (after loop completes):
        - generation_success: bool - Whether generation succeeded
        - pvmap_path: str - Path to generated PVMAP
        - pvmap_csv: str - PVMAP CSV content
        - validation_data_rows: int - Rows in processed output
        - retry_count: int - Number of attempts made
        - error: str - Error message if failed
    """
    # Get model from environment override if available
    model = os.getenv("PVMAP_GENERATOR_MODEL", model)

    # Create sub-agents
    state_prep = StatePreparationAgent(name="StatePrep")

    if use_structured_output:
        generator = create_pvmap_generator(model=model, name="Generator")
    else:
        from src.agents.pvmap_generator_agent import create_pvmap_generator_without_schema
        generator = create_pvmap_generator_without_schema(model=model, name="Generator")

    validator = ValidationAgent(name="Validator")
    feedback = create_feedback_agent(model=model, name="Feedback")
    max_retries_check = MaxRetriesCheckAgent(name="MaxRetriesCheck", max_retries=max_retries)

    # Create loop agent
    # max_iterations = max_retries + 1 (for initial attempt)
    # But we also handle exit via escalation in Validator and MaxRetriesCheck
    loop = LoopAgent(
        name=name,
        max_iterations=max_retries + 1,
        sub_agents=[
            state_prep,      # 1. Prepare state
            generator,       # 2. Generate PVMAP
            validator,       # 3. Validate (escalates on success)
            feedback,        # 4. Analyze errors
            max_retries_check  # 5. Check if max retries exceeded
        ]
    )

    return loop


# ============================================================================
# Alternative: Simple retry loop without MaxRetriesCheck
# ============================================================================

def create_simple_pvmap_retry_loop(
    model: str = "gemini-2.5-flash",
    max_retries: int = 2,
    name: str = "PVMAPRetryLoop",
) -> LoopAgent:
    """
    Create a simpler PVMAP retry loop that relies on LoopAgent's max_iterations.

    This version doesn't include MaxRetriesCheckAgent, so the loop will
    run until:
    - ValidationAgent escalates (success), OR
    - max_iterations is reached (LoopAgent stops automatically)

    Use this if you want simpler behavior without explicit max retries check.

    Args:
        model: Gemini model for generation
        max_retries: Max retry attempts (default: 2, for 3 total attempts)
        name: Loop agent name

    Returns:
        Configured LoopAgent
    """
    model = os.getenv("PVMAP_GENERATOR_MODEL", model)

    state_prep = StatePreparationAgent(name="StatePrep")
    generator = create_pvmap_generator(model=model, name="Generator")
    validator = ValidationAgent(name="Validator")
    feedback = create_feedback_agent(model=model, name="Feedback")

    return LoopAgent(
        name=name,
        max_iterations=max_retries + 1,
        sub_agents=[state_prep, generator, validator, feedback]
    )


# ============================================================================
# Module exports
# ============================================================================

__all__ = [
    'create_pvmap_retry_loop',
    'create_simple_pvmap_retry_loop',
    'StatePreparationAgent',
    'MaxRetriesCheckAgent',
]

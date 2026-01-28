"""
PVMAP Generation Agent for ADK pipeline.

Orchestrates PVMAP generation with retry loop and inline validation.
Uses Pattern 3: Custom BaseAgent with Orchestration.

This agent handles the complete PVMAP generation workflow including:
- Prompt building with error feedback
- LLM generation via LlmAgent
- CSV extraction from LLM output
- Inline validation with subprocess
- Retry loop with accumulated error feedback
"""

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
from google.genai import types
from google.genai import Client

from src.agents.pvmap_generation.helpers import (
    build_prompt_with_feedback,
    extract_csv,
    read_file_content
)
from src.tools.validation_tool import run_validation
from src.state.dataset_info import DatasetInfo
import os


class PVMAPGenerationAgent(BaseAgent):
    """
    Agent for generating PVMAPs with retry loop and inline validation.

    This is a custom BaseAgent that orchestrates:
    1. Building prompts with schema/data/metadata
    2. Calling LlmAgent to generate PVMAP
    3. Extracting CSV from LLM response
    4. Inline validation via subprocess
    5. Retry loop with error feedback

    ADK State Inputs:
        - current_dataset: DatasetInfo - Current dataset being processed
        - error_feedback: Optional[str] - Error feedback from previous attempt
        - retry_count: int - Current retry count

    ADK State Outputs:
        - pvmap_path: Path - Path to generated PVMAP file
        - pvmap_content: str - PVMAP CSV content
        - generation_success: bool - Whether generation succeeded
        - validation_results: dict - Validation results
        - error: Optional[str] - Error message if failed
    """

    def __init__(
        self,
        name: str = "PVMAPGenerationAgent",
        max_retries: int = 2,
        model: str = "gemini-3-pro-preview"
    ):
        """
        Initialize PVMAP Generation Agent.

        Args:
            name: Agent name
            max_retries: Maximum number of retry attempts (default: 2, for 3 total attempts)
            model: Gemini model to use for generation
        """
        super().__init__(name=name)
        self._max_retries = max_retries

        # LlmAgent for PVMAP generation
        self._generator = LlmAgent(
            name=f"{name}_Generator",
            model=model,
            instruction="You are a PVMAP generator. Generate a CSV mapping based on the provided schema, data, and metadata.",
            output_key="pvmap_raw_output"
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Run PVMAP generation with retry loop and inline validation.

        This implements the critical retry loop from run_pvmap_pipeline.py:1374-1415.
        """
        # Get dataset from state
        current_dataset: Optional[DatasetInfo] = ctx.session.state.get("current_dataset")
        if not current_dataset:
            ctx.session.state["generation_success"] = False
            ctx.session.state["error"] = "No current_dataset specified in state"
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="PVMAP generation failed: No current_dataset in state")
                ])
            )
            return

        # Get template path (default to tools/improved_pvmap_prompt.txt)
        tools_dir = PROJECT_ROOT / "tools"
        template_path = Path(ctx.session.state.get(
            "prompt_template_path",
            str(tools_dir / "improved_pvmap_prompt.txt")
        ))

        if not template_path.exists():
            ctx.session.state["generation_success"] = False
            ctx.session.state["error"] = f"Prompt template not found: {template_path}"
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"PVMAP generation failed: Template not found at {template_path}")
                ])
            )
            return

        # Retry loop (0 = first attempt, 1 = first retry, 2 = second retry)
        for attempt in range(self._max_retries + 1):
            try:
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"PVMAP generation attempt {attempt + 1}/{self._max_retries + 1}")
                    ])
                )

                # 1. Build prompt with error feedback
                try:
                    error_feedback = ctx.session.state.get("error_feedback")

                    # Read schema content
                    schema_content = None
                    if current_dataset.schema_examples and current_dataset.schema_examples.exists():
                        schema_content = read_file_content(current_dataset.schema_examples)

                    # Read sampled data
                    if not current_dataset.combined_sampled_data or not current_dataset.combined_sampled_data.exists():
                        raise ValueError("No sampled data available")
                    sampled_data_content = read_file_content(current_dataset.combined_sampled_data)

                    # Read metadata
                    if not current_dataset.combined_metadata or not current_dataset.combined_metadata.exists():
                        raise ValueError("No metadata available")
                    metadata_content = read_file_content(current_dataset.combined_metadata)

                    # Build prompt
                    prompt = build_prompt_with_feedback(
                        template_path=template_path,
                        schema_content=schema_content,
                        sampled_data_content=sampled_data_content,
                        metadata_content=metadata_content,
                        error_feedback=error_feedback
                    )

                    # Store prompt in state
                    ctx.session.state["pvmap_generation_prompt"] = prompt

                except Exception as e:
                    ctx.session.state["generation_success"] = False
                    ctx.session.state["error"] = f"Prompt building failed: {str(e)}"
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[
                            types.Part(text=f"Prompt building failed: {str(e)}")
                        ])
                    )
                    return

                # 2. Call LlmAgent to generate
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text="Calling LLM to generate PVMAP...")
                    ])
                )

                try:
                    # Call Gemini API directly using async
                    import asyncio
                    from functools import partial
                    import traceback as tb

                    try:
                        client = Client(api_key=os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
                        model_name = ctx.session.state.get("model", "gemini-3-pro-preview")

                        # Run sync API call in executor
                        loop = asyncio.get_event_loop()
                        response = await loop.run_in_executor(
                            None,
                            partial(
                                client.models.generate_content,
                                model=model_name,
                                contents=prompt
                            )
                        )
                        raw_output = response.text if hasattr(response, 'text') else str(response)

                        # Store in state
                        ctx.session.state["pvmap_raw_output"] = raw_output

                        if not raw_output:
                            raise ValueError("LLM did not produce output")

                    except Exception as api_error:
                        tb.print_exc()
                        raise

                except Exception as e:
                    ctx.session.state["generation_success"] = False
                    ctx.session.state["error"] = f"LLM generation failed: {str(e)}"
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[
                            types.Part(text=f"LLM generation failed: {str(e)}")
                        ])
                    )
                    return

                # 3. Extract CSV from LLM response
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Extracting CSV from LLM response (length: {len(raw_output) if raw_output else 0})...")
                    ])
                )

                pvmap_csv = extract_csv(raw_output)

                if not pvmap_csv:
                    ctx.session.state["generation_success"] = False
                    ctx.session.state["error"] = "Could not extract CSV from LLM response"
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[
                            types.Part(text="CSV extraction failed: No valid CSV found in response")
                        ])
                    )
                    return


                # Store CSV in state
                ctx.session.state["pvmap_content"] = pvmap_csv

                # Write PVMAP to file
                pvmap_path = current_dataset.output_dir / "generated_pvmap.csv"
                pvmap_path.parent.mkdir(parents=True, exist_ok=True)
                with open(pvmap_path, 'w', encoding='utf-8') as f:
                    f.write(pvmap_csv)
                ctx.session.state["pvmap_path"] = str(pvmap_path)

                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"PVMAP CSV extracted and saved to {pvmap_path}")
                    ])
                )

                # 4. INLINE VALIDATION (subprocess call)
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text="Validating PVMAP with stat_var_processor...")
                    ])
                )

                # Get first input file for validation
                input_file = current_dataset.input_data_files[0] if current_dataset.input_data_files else None
                if not input_file:
                    raise ValueError("No input data files available for validation")

                validation_result = run_validation(
                    input_data=str(input_file),
                    pvmap_path=str(pvmap_path),
                    metadata_file=str(current_dataset.combined_metadata),
                    output_dir=str(current_dataset.output_dir)
                )

                ctx.session.state["validation_results"] = validation_result

                # 5. Check validation success
                if validation_result["success"]:
                    # SUCCESS!
                    ctx.session.state["generation_success"] = True
                    ctx.session.state["error"] = None
                    ctx.session.state["retry_count"] = attempt

                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[
                            types.Part(text=f"PVMAP generation succeeded on attempt {attempt + 1}! ✅")
                        ])
                    )
                    return

                # 6. Validation failed - extract error feedback for retry
                error_logs = validation_result.get("error", "Validation failed with no error details")

                # Sample error logs if too long (limit to ~300 lines)
                from src.tools.logging_tools import extract_log_samples
                sampled_errors = extract_log_samples(error_logs)

                ctx.session.state["error_feedback"] = sampled_errors

                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Validation failed on attempt {attempt + 1}. Error feedback prepared for retry.")
                    ])
                )

                # Check if max retries exceeded
                if attempt >= self._max_retries:
                    ctx.session.state["generation_success"] = False
                    ctx.session.state["error"] = f"Max retries ({self._max_retries + 1}) exceeded. Last error: {sampled_errors[:500]}"
                    ctx.session.state["retry_count"] = attempt

                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[
                            types.Part(text=f"PVMAP generation failed after {self._max_retries + 1} attempts. ❌")
                        ])
                    )
                    return

                # Continue to next retry
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Retrying with error feedback... (attempt {attempt + 2}/{self._max_retries + 1})")
                    ])
                )

            except Exception as e:
                # Catch any exceptions in retry loop
                ctx.session.state["generation_success"] = False
                ctx.session.state["error"] = f"Exception in PVMAP generation: {str(e)}"
                ctx.session.state["retry_count"] = attempt

                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"PVMAP generation exception: {str(e)}")
                    ])
                )
                import traceback
                traceback.print_exc()
                return

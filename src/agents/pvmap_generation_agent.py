"""
PVMAP Generation Agent for ADK pipeline.

Orchestrates PVMAP generation with retry loop and inline validation.
Uses Pattern 3: Custom BaseAgent with Orchestration.

This agent handles the complete PVMAP generation workflow including:
- Prompt building with error feedback
- LLM generation via GeminiClient
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

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from src.agents.pvmap_generation.helpers import (
    build_prompt_with_feedback,
    extract_csv,
    read_file_content,
    save_populated_prompt,
    save_attempt_response,
    append_llm_call_log,
    update_generation_notes,
    convert_pvmap_output_to_csv,
    validate_pvmap_structure,
    parse_structured_json_response
)
from src.agents.pvmap_generation.schemas import PVMAP_OUTPUT_SCHEMA
from src.tools.validation_tool import run_validation
from src.state.dataset_info import DatasetInfo


class PVMAPGenerationAgent(BaseAgent):
    """
    Agent for generating PVMAPs with retry loop and inline validation.

    This is a custom BaseAgent that orchestrates:
    1. Building prompts with schema/data/metadata
    2. Calling GeminiClient to generate PVMAP
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
        model: str = "gemini-3-pro-preview",
        use_structured_output: bool = False
    ):
        """
        Initialize PVMAP Generation Agent.

        Args:
            name: Agent name
            max_retries: Maximum number of retry attempts (default: 2, for 3 total attempts)
            model: Gemini model to use for generation
            use_structured_output: If True, request JSON structured output from LLM
                                  and convert to CSV deterministically
        """
        super().__init__(name=name)
        self._max_retries = max_retries
        self._model = model  # Store model name for GeminiClient
        self._use_structured_output = use_structured_output

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

        # Get template path (default to src/resources/prompts/improved_pvmap_prompt.txt)
        default_template = PROJECT_ROOT / "src" / "resources" / "prompts" / "improved_pvmap_prompt.txt"
        template_path = Path(ctx.session.state.get(
            "prompt_template_path",
            str(default_template)
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

                    # Read metadata (optional)
                    metadata_content = "(No metadata provided)"
                    if current_dataset.combined_metadata and current_dataset.combined_metadata.exists():
                        metadata_content = read_file_content(current_dataset.combined_metadata)

                    # Get discovered StatVars if MCP discovery was performed
                    discovered_statvars = None
                    if ctx.session.state.get("mcp_enabled", False):
                        discovered_statvars = ctx.session.state.get("statvar_summary")

                    # Get data context (skeleton summary) from sampling agent
                    skeleton_summary = ctx.session.state.get("skeleton_summary")

                    # Build prompt with discovered StatVars and data context
                    prompt = build_prompt_with_feedback(
                        template_path=template_path,
                        schema_content=schema_content,
                        sampled_data_content=sampled_data_content,
                        metadata_content=metadata_content,
                        error_feedback=error_feedback,
                        discovered_statvars=discovered_statvars,
                        data_context=skeleton_summary
                    )

                    # Add structured output instructions if enabled
                    if self._use_structured_output:
                        structured_output_instructions = """

---

# OUTPUT FORMAT (STRUCTURED JSON)

Return your response as a JSON object with this exact structure:

```json
{
  "format_detected": "raw",  // or "pre-formatted" if data has variableMeasured/observationAbout columns
  "pvmap_rows": [
    {
      "key": "Year",
      "mappings": [
        {"property": "observationDate", "value": "{Data}"}
      ]
    },
    {
      "key": "Value",
      "mappings": [
        {"property": "value", "value": "{Number}"},
        {"property": "populationType", "value": "dcid:Person"},
        {"property": "measuredProperty", "value": "dcid:count"},
        {"property": "statType", "value": "dcid:measuredValue"}
      ]
    }
  ],
  "validation_notes": "Mapped Year to observationDate, Value to StatVar properties...",
  "confidence": "high"  // or "medium" or "low"
}
```

**IMPORTANT**:
- Each key should match input data EXACTLY (case-sensitive)
- Each mapping has exactly two fields: "property" and "value"
- Use dcid: prefix for Data Commons identifiers
- Use {Data} for string pass-through, {Number} for numeric values
"""
                        prompt = prompt + structured_output_instructions

                    # Store prompt in state
                    ctx.session.state["pvmap_generation_prompt"] = prompt
                    ctx.session.state["use_structured_output"] = self._use_structured_output

                    # Save populated prompt to file (only on first attempt)
                    if attempt == 0:
                        save_populated_prompt(current_dataset.output_dir, prompt)

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
                    # Call Gemini API using GeminiClient (handles API key loading from .env)
                    import asyncio
                    from functools import partial
                    import traceback as tb

                    try:
                        from src.data_commons.api.gemini_client import GeminiClient

                        model_name = ctx.session.state.get("model", self._model)
                        gemini_client = GeminiClient(model_name=model_name)

                        # Run sync API call in executor - use generate_content_with_metadata for full response
                        loop = asyncio.get_event_loop()
                        llm_result = await loop.run_in_executor(
                            None,
                            partial(
                                gemini_client.generate_content_with_metadata,
                                prompt=prompt,
                                temperature=0
                            )
                        )

                        # Extract text from result
                        raw_output = llm_result.get('text', '')

                        # Store in state
                        ctx.session.state["pvmap_raw_output"] = raw_output
                        ctx.session.state["pvmap_llm_result"] = llm_result

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

                pvmap_csv = None
                structure_warnings = []

                # Try structured JSON extraction first if enabled
                if self._use_structured_output:
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[
                            types.Part(text="Attempting structured JSON extraction...")
                        ])
                    )

                    structured_output = parse_structured_json_response(raw_output)
                    if structured_output:
                        # Validate structure
                        structure_warnings = validate_pvmap_structure(structured_output)
                        if structure_warnings:
                            yield Event(
                                author=self.name,
                                content=types.Content(parts=[
                                    types.Part(text=f"Structure warnings: {'; '.join(structure_warnings[:3])}")
                                ])
                            )

                        # Store structured output metadata
                        ctx.session.state["pvmap_format_detected"] = structured_output.format_detected
                        ctx.session.state["pvmap_confidence"] = structured_output.confidence
                        ctx.session.state["pvmap_validation_notes"] = structured_output.validation_notes
                        ctx.session.state["pvmap_structure_warnings"] = structure_warnings

                        # Convert to CSV deterministically
                        pvmap_csv = convert_pvmap_output_to_csv(structured_output)

                        yield Event(
                            author=self.name,
                            content=types.Content(parts=[
                                types.Part(text=f"Structured output converted to CSV (format: {structured_output.format_detected}, confidence: {structured_output.confidence})")
                            ])
                        )
                    else:
                        yield Event(
                            author=self.name,
                            content=types.Content(parts=[
                                types.Part(text="Structured JSON extraction failed, falling back to regex extraction...")
                            ])
                        )

                # Fall back to regex-based CSV extraction
                if not pvmap_csv:
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
                ctx.session.state["pvmap_structure_warnings"] = structure_warnings

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

                # Save attempt response files (md, json, thinking.txt)
                save_attempt_response(
                    output_dir=current_dataset.output_dir,
                    attempt=attempt,
                    llm_result=llm_result,
                    error_feedback=error_feedback,
                    pvmap_csv=pvmap_csv,
                    validation_result=validation_result
                )

                # Append to llm_calls.jsonl
                append_llm_call_log(
                    output_dir=current_dataset.output_dir,
                    attempt=attempt,
                    llm_result=llm_result,
                    prompt_length=len(prompt),
                    validation_success=validation_result.get("success")
                )

                # 5. Check validation success
                if validation_result["success"]:
                    # SUCCESS!
                    ctx.session.state["generation_success"] = True
                    ctx.session.state["error"] = None
                    ctx.session.state["retry_count"] = attempt

                    # Update generation notes with success status
                    update_generation_notes(
                        output_dir=current_dataset.output_dir,
                        dataset_name=current_dataset.name,
                        attempt=attempt,
                        llm_result=llm_result,
                        pvmap_csv=pvmap_csv,
                        validation_result=validation_result,
                        final_status=f"✅ **Success** on attempt {attempt + 1}"
                    )

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
                # Use validation_tool.extract_log_samples which returns str (not dict)
                from src.tools.validation_tool import extract_log_samples
                sampled_errors = extract_log_samples(error_logs)

                ctx.session.state["error_feedback"] = sampled_errors

                # Update generation notes with failure
                update_generation_notes(
                    output_dir=current_dataset.output_dir,
                    dataset_name=current_dataset.name,
                    attempt=attempt,
                    llm_result=llm_result,
                    pvmap_csv=pvmap_csv,
                    validation_result=validation_result,
                    final_status=None if attempt < self._max_retries else f"❌ **Failed** after {self._max_retries + 1} attempts"
                )

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

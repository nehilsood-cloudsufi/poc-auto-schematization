"""
PVMAP Retry Loop using ADK LoopAgent with Quality-Based Retries.

This module creates a LoopAgent that orchestrates:
1. StatePreparationAgent - Prepares state for each iteration
2. [StatVarDiscoveryAgent] - MCP-based StatVar discovery (if MCP enabled)
3. PVMAPGeneratorAgent - Generates PVMAP with structured output
4. ValidationAgent - Validates PVMAP (sets validation_passed flag)
5. [MCPErrorResolverAgent] - MCP-based error resolution (if MCP enabled)
6. QualityEvaluationAgent - Evaluates quality (escalates if acceptable/stagnant)
7. ConditionalQualityFeedbackAgent - Generates quality improvement feedback
8. ConditionalFeedbackAgent - Generates validation error feedback
9. MaxRetriesCheckAgent - Checks if max retries exceeded

The loop exits when:
- QualityEvaluationAgent escalates (quality acceptable or stagnant), OR
- MaxRetriesCheckAgent escalates (max retries exceeded), OR
- max_iterations is reached (fallback)

Key ADK features used:
- LoopAgent for automatic retry mechanism
- EventActions.escalate for early exit conditions
- Session state for passing data between iterations
- Conditional agents for selective feedback generation
"""

import os
import sys
from pathlib import Path
from typing import Optional, AsyncGenerator

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging

from google.adk.agents import LoopAgent, BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from src.agents.pvmap_generator_agent import create_pvmap_generator
from src.agents.validation_agent import ValidationAgent
from src.agents.feedback_agent import create_feedback_agent
from src.agents.quality_evaluation_agent import QualityEvaluationAgent
from src.agents.quality_feedback_agent import ConditionalQualityFeedbackAgent
from src.agents.template_utils import escape_pvmap_placeholders
from src.tools.evaluation_tools import find_ground_truth_pvmaps

logger = logging.getLogger(__name__)


class StatePreparationAgent(BaseAgent):
    """
    Prepares session state before each generator iteration.

    This agent:
    1. Reads data files and populates state with content
    2. Increments attempt_number for tracking
    3. Initializes quality_metrics_history on first attempt
    4. Resets per-iteration flags (validation_passed, quality_acceptable, etc.)
    5. Ensures required state variables are set for the generator
    6. Sets MCP-related state defaults

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
                types.Part(text=f"Preparing state for attempt {attempt + 1} of 4...")
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

        # =====================================================================
        # Initialize tracking state on first attempt
        # =====================================================================
        if attempt == 0:
            ctx.session.state["quality_metrics_history"] = []
            ctx.session.state["error_feedback"] = ""
            ctx.session.state["quality_feedback"] = ""
            ctx.session.state["exit_reason"] = None

            # Discover and cache ground truth PVMAP path (once)
            self._discover_and_cache_ground_truth(ctx)

        # =====================================================================
        # Reset per-iteration flags
        # =====================================================================
        ctx.session.state["validation_passed"] = False
        ctx.session.state["quality_acceptable"] = False
        ctx.session.state["quality_stagnant"] = False

        # =====================================================================
        # MCP-related state defaults
        # =====================================================================
        if "mcp_enrichment_context" not in ctx.session.state:
            ctx.session.state["mcp_enrichment_context"] = {}
        if "mcp_resolved_context" not in ctx.session.state:
            ctx.session.state["mcp_resolved_context"] = ""

        # Set MCP tools instruction (populated when MCP enabled, empty when not)
        mcp_enabled = ctx.session.state.get("mcp_enabled", False)
        if mcp_enabled:
            from src.agents.dc_query_agent import MCP_TOOLS_INSTRUCTION
            ctx.session.state["mcp_tools_instruction"] = MCP_TOOLS_INSTRUCTION
        else:
            if "mcp_tools_instruction" not in ctx.session.state:
                ctx.session.state["mcp_tools_instruction"] = ""

        # =====================================================================
        # Read and populate file contents
        # =====================================================================

        # Read schema_examples if not already in state
        # Respects use_schema_examples flag and prefers compressed vocab
        if "schema_examples" not in ctx.session.state or not ctx.session.state["schema_examples"]:
            use_schema_examples = ctx.session.state.get("use_schema_examples", True)
            schema_content = ""
            if use_schema_examples:
                # 1. Prefer compressed vocab from state
                schema_content = ctx.session.state.get("schema_vocab_content", "")
                # 2. Fallback: read vocab JSON from resource dir using selected category
                if not schema_content:
                    schema_category = ctx.session.state.get("schema_category", "")
                    for cat in ["Health", "Demographics", "Economy", "Education", "Employment", "Energy", "School"]:
                        if cat.lower() in schema_category.lower():
                            schema_category = cat
                            break
                    schema_base = ctx.session.state.get("schema_base_dir", "")
                    if schema_category and schema_base:
                        vocab_path = Path(schema_base) / schema_category / "schema_vocab.json"
                        if vocab_path.exists():
                            try:
                                import json
                                from src.pipeline.schema_selection.schema_selector import format_schema_vocab_for_prompt
                                vocab = json.loads(vocab_path.read_text(encoding="utf-8"))
                                schema_content = format_schema_vocab_for_prompt(vocab)
                            except Exception:
                                pass
                # 3. Fallback: file on disk (for --schema-file override or legacy files)
                if not schema_content and current_dataset.schema_examples and Path(current_dataset.schema_examples).exists():
                    try:
                        schema_content = Path(current_dataset.schema_examples).read_text(encoding='utf-8')
                    except Exception as e:
                        schema_content = f"(Error reading schema: {e})"
            if not schema_content:
                schema_content = (
                    "No schema example files found. Generate PVMAP based on "
                    "data structure and Data Commons conventions."
                )
            ctx.session.state["schema_examples"] = schema_content

        # Read sampled_data if not already in state
        if "sampled_data" not in ctx.session.state or not ctx.session.state["sampled_data"]:
            sampled_data = ""
            # Resolve sampled data path from multiple sources
            sampled_path = ctx.session.state.get("sampled_data_path")
            if not sampled_path or not Path(sampled_path).exists():
                fallback = Path(current_dataset.output_dir) / "agentic_sampled.csv"
                if fallback.exists():
                    sampled_path = str(fallback)
                elif current_dataset.sampled_data_files:
                    sampled_path = str(current_dataset.sampled_data_files[0])
            if sampled_path and Path(sampled_path).exists():
                try:
                    sampled_data = Path(sampled_path).read_text(encoding='utf-8')
                except Exception as e:
                    sampled_data = f"(Error reading sampled data: {e})"
            ctx.session.state["sampled_data"] = sampled_data

        # Read metadata if not already in state (only if use_metadata flag is enabled)
        if "metadata" not in ctx.session.state or not ctx.session.state["metadata"]:
            metadata = ""
            if current_dataset.use_metadata and current_dataset.metadata_files:
                metadata_path = current_dataset.metadata_files[0]
                if metadata_path and Path(metadata_path).exists():
                    try:
                        metadata = Path(metadata_path).read_text(encoding='utf-8')
                    except Exception as e:
                        metadata = f"(Error reading metadata: {e})"
            ctx.session.state["metadata"] = metadata

        # =====================================================================
        # Ensure optional state variables have defaults (for instruction templating)
        # =====================================================================
        if "skeleton_summary" not in ctx.session.state:
            ctx.session.state["skeleton_summary"] = ""
        if "statvar_summary" not in ctx.session.state:
            ctx.session.state["statvar_summary"] = ""
        if "structure_warnings" not in ctx.session.state:
            ctx.session.state["structure_warnings"] = ""
        if "quality_diff_summary" not in ctx.session.state:
            ctx.session.state["quality_diff_summary"] = ""
        if "gt_score_section" not in ctx.session.state:
            ctx.session.state["gt_score_section"] = ""

        # =====================================================================
        # CRITICAL: Escape PVMAP placeholders in feedback to prevent templating errors
        # The generator instruction uses {error_feedback} and {quality_feedback},
        # which may contain PVMAP snippets with {Data}/{Number} from LLM analysis
        # =====================================================================
        error_feedback = ctx.session.state.get("error_feedback", "")
        if error_feedback:
            ctx.session.state["error_feedback"] = escape_pvmap_placeholders(error_feedback)

        quality_feedback = ctx.session.state.get("quality_feedback", "")
        if quality_feedback:
            ctx.session.state["quality_feedback"] = escape_pvmap_placeholders(quality_feedback)

        # =====================================================================
        # Log feedback status (critical for debugging retry loop)
        # =====================================================================
        if attempt > 0:
            error_feedback = ctx.session.state.get("error_feedback", "")
            quality_feedback = ctx.session.state.get("quality_feedback", "")

            if error_feedback:
                preview = error_feedback[:150] + "..." if len(error_feedback) > 150 else error_feedback
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Using validation error feedback: {preview}")
                    ])
                )

            if quality_feedback:
                preview = quality_feedback[:150] + "..." if len(quality_feedback) > 150 else quality_feedback
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Using quality improvement feedback: {preview}")
                    ])
                )

        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text=f"State prepared for attempt {attempt + 1}")
            ])
        )

    def _discover_and_cache_ground_truth(self, ctx: InvocationContext) -> None:
        """
        Discover ground truth PVMAP path on first attempt and cache in state.

        Uses the same precedence logic as EvaluationAgent:
          Tier 1: ground_truth_pvmap (explicit file)
          Tier 2: ground_truth_dir (search directory)
          Tier 3: ground_truth_repo (default: ground_truth/)

        Stores result in gt_pvmap_path_cached (str or None).
        """
        import os

        current_dataset = ctx.session.state.get("current_dataset")
        if not current_dataset:
            ctx.session.state["gt_pvmap_path_cached"] = None
            return

        ground_truth_pvmap = ctx.session.state.get("ground_truth_pvmap")
        ground_truth_dir = ctx.session.state.get("ground_truth_dir")
        ground_truth_repo = ctx.session.state.get(
            "ground_truth_repo",
            os.getenv("GROUND_TRUTH_REPO", str(PROJECT_ROOT / "ground_truth"))
        )

        dataset_name = current_dataset.name

        # Apply same precedence as EvaluationAgent
        if ground_truth_pvmap and Path(ground_truth_pvmap).exists():
            gt_result = find_ground_truth_pvmaps(
                dataset_name=dataset_name,
                explicit_pvmap=ground_truth_pvmap
            )
        elif ground_truth_dir and Path(ground_truth_dir).exists():
            gt_result = find_ground_truth_pvmaps(
                dataset_name=dataset_name,
                search_dir=ground_truth_dir
            )
        else:
            gt_result = find_ground_truth_pvmaps(
                dataset_name=dataset_name,
                source_repo=ground_truth_repo,
                search_dir=str(current_dataset.path) if current_dataset.path else ""
            )

        if gt_result["success"] and gt_result["count"] > 0:
            gt_path = str(gt_result["pvmaps"][0])
            ctx.session.state["gt_pvmap_path_cached"] = gt_path
            logger.info(f"Ground truth PVMAP cached for in-loop scoring: {gt_path}")
        else:
            ctx.session.state["gt_pvmap_path_cached"] = None
            logger.info("No ground truth PVMAP found; in-loop scoring will use heuristics only")


class MCPErrorResolverAgent(BaseAgent):
    """
    Thin wrapper that runs MCP error resolution after validation failure.

    Skips if:
    - MCP is not enabled
    - Validation passed (no errors to resolve)

    Delegates query logic to dc_query_agent.create_error_resolver_agent().
    Writes mcp_resolved_context to state.
    """

    def __init__(self, name: str = "MCPErrorResolver"):
        super().__init__(name=name)

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Run MCP error resolution if needed."""
        mcp_enabled = ctx.session.state.get("mcp_enabled", False)
        validation_passed = ctx.session.state.get("validation_passed", False)

        if not mcp_enabled or validation_passed:
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="MCP error resolution skipped (not needed)")
                ])
            )
            return

        validation_error = ctx.session.state.get("validation_error", "")
        pvmap_csv = ctx.session.state.get("pvmap_csv", "")
        mcp_url = ctx.session.state.get("mcp_url", "http://localhost:3000/mcp")

        if not validation_error:
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="MCP error resolution skipped (no validation error)")
                ])
            )
            return

        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text="Running MCP error resolution...")
            ])
        )

        try:
            from src.agents.dc_query_agent import (
                create_error_resolver_agent,
                run_mcp_query,
            )

            resolver_agent = create_error_resolver_agent(
                mcp_url=mcp_url,
                model="gemini-2.5-pro",
                validation_error=validation_error[:2000],
                pvmap_csv=pvmap_csv[:3000],
            )

            result_text = await run_mcp_query(
                mcp_url, resolver_agent,
                "Resolve the PVMAP validation errors using Data Commons queries."
            )

            ctx.session.state["mcp_resolved_context"] = result_text[:2000]
            logger.info(f"MCP error resolution complete: {len(result_text)} chars")

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"MCP error resolution complete ({len(result_text)} chars)")
                ])
            )

        except Exception as e:
            logger.warning(f"MCP error resolution failed: {e}")
            ctx.session.state["mcp_resolved_context"] = ""
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"MCP error resolution failed (continuing): {str(e)[:100]}")
                ])
            )


class ConditionalFeedbackAgent(BaseAgent):
    """
    Conditional wrapper that only runs FeedbackAgent when validation failed.

    This agent runs the error feedback LlmAgent only when:
    - validation_passed = False (validation failed)

    Otherwise, it skips feedback generation (quality feedback will handle it).
    """

    # Declare feedback_agent as a Pydantic field (ADK agents use Pydantic)
    feedback_agent: LlmAgent

    def __init__(
        self,
        name: str = "ConditionalFeedback",
        model: str = "gemini-2.5-flash"
    ):
        """
        Initialize ConditionalFeedbackAgent.

        Args:
            name: Agent name
            model: Gemini model for the inner LlmAgent
        """
        feedback_agent = create_feedback_agent(model=model)
        super().__init__(
            name=name,
            feedback_agent=feedback_agent,
            sub_agents=[feedback_agent]
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Conditionally run feedback agent.

        Only runs if validation failed.
        """
        validation_passed = ctx.session.state.get("validation_passed", False)

        if not validation_passed:
            # Validation failed - generate error feedback
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Validation failed - generating error feedback...")
                ])
            )

            # =====================================================================
            # CRITICAL: Escape PVMAP placeholders to prevent ADK templating errors
            # {Data} and {Number} in pvmap_csv/validation_error cause KeyError
            # =====================================================================
            self._prepare_feedback_state(ctx)

            # Run the inner feedback agent
            async for event in self.feedback_agent.run_async(ctx):
                yield event

            # Clear quality_feedback since we're using error_feedback
            ctx.session.state["quality_feedback"] = ""

            # Log feedback preview
            error_feedback = ctx.session.state.get("error_feedback", "")
            if error_feedback:
                preview = error_feedback[:200] + "..." if len(error_feedback) > 200 else error_feedback
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Error feedback generated: {preview}")
                    ]),
                    actions=EventActions(escalate=False)  # Explicit: continue loop
                )
        else:
            # Validation passed - skip this agent (quality feedback will handle it)
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Skipping validation feedback (validation passed)")
                ]),
                actions=EventActions(escalate=False)  # Explicit: continue loop
            )

    def _prepare_feedback_state(self, ctx: InvocationContext) -> None:
        """
        Prepare state variables for feedback instruction templating.

        Escapes PVMAP placeholders ({Data}, {Number}) to prevent ADK templating
        conflicts. These get converted to [DATA], [NUMBER].
        """
        # Escape PVMAP content
        pvmap_csv = ctx.session.state.get("pvmap_csv", "")
        if pvmap_csv:
            ctx.session.state["pvmap_csv"] = escape_pvmap_placeholders(pvmap_csv)

        # Escape validation error (may contain PVMAP snippets)
        validation_error = ctx.session.state.get("validation_error", "")
        if validation_error:
            ctx.session.state["validation_error"] = escape_pvmap_placeholders(validation_error)

        # Escape sampled data (unlikely but possible)
        sampled_data = ctx.session.state.get("sampled_data", "")
        if sampled_data:
            ctx.session.state["sampled_data"] = escape_pvmap_placeholders(sampled_data)

        # Escape structure warnings
        structure_warnings = ctx.session.state.get("structure_warnings", "")
        if structure_warnings:
            ctx.session.state["structure_warnings"] = escape_pvmap_placeholders(structure_warnings)

        # Escape MCP resolved context (may contain PVMAP snippets)
        mcp_resolved_context = ctx.session.state.get("mcp_resolved_context", "")
        if mcp_resolved_context:
            ctx.session.state["mcp_resolved_context"] = escape_pvmap_placeholders(mcp_resolved_context)


class MaxRetriesCheckAgent(BaseAgent):
    """
    Checks if max retries exceeded after all feedback agents run.

    If max retries reached, sets final failure state and escalates
    to exit the loop.
    """

    def __init__(self, name: str = "MaxRetriesCheck", max_retries: int = 3):
        super().__init__(name=name)
        self._max_retries = max_retries

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Check if max retries exceeded."""

        attempt = ctx.session.state.get("attempt_number", 0)

        # Check if we should already have exited (quality acceptable or stagnant)
        quality_acceptable = ctx.session.state.get("quality_acceptable", False)
        quality_stagnant = ctx.session.state.get("quality_stagnant", False)

        if quality_acceptable or quality_stagnant:
            # Should have already escalated from QualityEvaluationAgent
            # This is a safety check - must still yield explicit escalate=False
            # to signal ADK that we're continuing (not terminating ambiguously)
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Quality check already handled exit. Skipping max retries check.")
                ]),
                actions=EventActions(escalate=False)  # Explicit: continue loop
            )
            return

        if attempt >= self._max_retries:
            # Max retries reached - set failure state and exit loop
            ctx.session.state["generation_success"] = False
            ctx.session.state["retry_count"] = attempt
            ctx.session.state["exit_reason"] = "max_retries"

            # Determine error message based on what type of feedback we had
            error_feedback = ctx.session.state.get("error_feedback", "")
            quality_feedback = ctx.session.state.get("quality_feedback", "")
            quality_metrics = ctx.session.state.get("quality_metrics", {})

            if error_feedback:
                error_msg = f"Max retries ({self._max_retries + 1}) exceeded. Last validation error: {error_feedback[:500]}"
            elif quality_feedback:
                score = quality_metrics.get("heuristic_score", 0)
                error_msg = f"Max retries ({self._max_retries + 1}) exceeded. Best quality: {score:.1f}%"
            else:
                error_msg = f"Max retries ({self._max_retries + 1}) exceeded."

            ctx.session.state["error"] = error_msg

            # Update generation notes with final failure status
            try:
                from src.agents.pvmap_generation.helpers import update_generation_notes
                current_dataset = ctx.session.state.get("current_dataset")
                if current_dataset:
                    validation_passed = ctx.session.state.get("validation_passed", False)
                    update_generation_notes(
                        output_dir=Path(current_dataset.output_dir),
                        dataset_name=current_dataset.name,
                        attempt=attempt,
                        llm_result=ctx.session.state.get("pvmap_llm_result", {}),
                        pvmap_csv=ctx.session.state.get("pvmap_csv"),
                        validation_result={
                            "success": validation_passed,
                            "error": error_feedback if not validation_passed else ""
                        },
                        final_status=f"FAILED after {self._max_retries + 1} attempts (exit_reason: max_retries)"
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
                    types.Part(text=f"Attempt {attempt + 1} did not meet criteria. {self._max_retries - attempt} retries remaining.")
                ]),
                actions=EventActions(escalate=False)  # Continue loop
            )


def create_pvmap_retry_loop(
    model: str = "gemini-2.5-flash",
    max_retries: int = 3,
    use_structured_output: bool = True,
    name: str = "PVMAPRetryLoop",
    enable_mcp: bool = False,
    mcp_url: Optional[str] = None,
) -> LoopAgent:
    """
    Create PVMAP generation retry loop with quality-based retries.

    The loop runs (without MCP):
    1. StatePreparationAgent - Prepares state for generator
    2. PVMAPGeneratorAgent - Generates PVMAP (structured JSON)
    3. ValidationAgent - Validates; sets validation_passed flag
    4. QualityEvaluationAgent - Evaluates quality; ESCALATES if acceptable/stagnant
    5. ConditionalQualityFeedbackAgent - Generates quality feedback if needed
    6. ConditionalFeedbackAgent - Generates error feedback if validation failed
    7. MaxRetriesCheckAgent - Checks if max retries exceeded

    With MCP enabled, adds:
    - StatVarDiscoveryAgent after StatePrep (loop-aware discovery)
    - MCPErrorResolverAgent after Validator (error resolution)

    The loop exits when:
    - QualityEvaluationAgent escalates (quality acceptable or stagnant), OR
    - MaxRetriesCheckAgent escalates (max retries), OR
    - max_iterations reached (fallback)

    Args:
        model: Gemini model for generation (default: gemini-2.5-flash)
        max_retries: Max retry attempts (default: 3, for 4 total attempts)
        use_structured_output: Use output_schema for structured JSON (default: True)
        name: Loop agent name (default: PVMAPRetryLoop)
        enable_mcp: Enable MCP integration (default: False)
        mcp_url: MCP server URL (required if enable_mcp=True)

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
        - exit_reason: str - "quality_met" | "stagnant" | "max_retries"
        - quality_metrics: dict - Final quality metrics
        - quality_metrics_history: List[dict] - All attempts' metrics
        - error: str - Error message if failed
        - mcp_enrichment_context: dict - MCP discovery results (if MCP enabled)
        - mcp_resolved_context: str - MCP error resolution (if MCP enabled)
    """
    # Get model from environment override if available
    model = os.getenv("PVMAP_GENERATOR_MODEL", model)

    # Create sub-agents
    state_prep = StatePreparationAgent(name="StatePrep")

    if use_structured_output:
        generator = create_pvmap_generator(
            model=model, name="Generator",
            enable_mcp=enable_mcp, mcp_url=mcp_url,
        )
    else:
        from src.agents.pvmap_generator_agent import create_pvmap_generator_without_schema
        generator = create_pvmap_generator_without_schema(model=model, name="Generator")

    validator = ValidationAgent(name="Validator")
    quality_evaluator = QualityEvaluationAgent(name="QualityEvaluator")
    quality_feedback = ConditionalQualityFeedbackAgent(name="QualityFeedback", model=model)
    error_feedback = ConditionalFeedbackAgent(name="ErrorFeedback", model=model)
    max_retries_check = MaxRetriesCheckAgent(name="MaxRetriesCheck", max_retries=max_retries)

    # Build sub_agents list
    sub_agents = [state_prep]

    # Insert StatVarDiscoveryAgent when MCP enabled (loop-aware)
    if enable_mcp and mcp_url:
        from src.agents.statvar_discovery_agent import StatVarDiscoveryAgent
        statvar_discovery = StatVarDiscoveryAgent(
            name="StatVarDiscovery",
            model=model
        )
        sub_agents.append(statvar_discovery)
        logger.info("StatVarDiscoveryAgent added to retry loop (MCP enabled)")

    sub_agents.append(generator)
    sub_agents.append(validator)

    # Insert MCPErrorResolverAgent when MCP enabled
    if enable_mcp and mcp_url:
        error_resolver = MCPErrorResolverAgent(name="MCPErrorResolver")
        sub_agents.append(error_resolver)
        logger.info("MCPErrorResolverAgent added to retry loop (MCP enabled)")

    sub_agents.extend([
        quality_evaluator,
        quality_feedback,
        error_feedback,
        max_retries_check,
    ])

    # Create loop agent
    # max_iterations = max_retries + 1 (for initial attempt)
    # Exit via escalation in QualityEvaluator or MaxRetriesCheck
    loop = LoopAgent(
        name=name,
        max_iterations=max_retries + 1,
        sub_agents=sub_agents
    )

    return loop


# ============================================================================
# Legacy: Simple retry loop without quality-based retries
# ============================================================================

def create_simple_pvmap_retry_loop(
    model: str = "gemini-2.5-flash",
    max_retries: int = 2,
    name: str = "PVMAPSimpleRetryLoop",
) -> LoopAgent:
    """
    Create a simpler PVMAP retry loop without quality-based retries.

    This version only validates and retries on validation failure.
    Use create_pvmap_retry_loop() for the full quality-based retry mechanism.

    Args:
        model: Gemini model for generation
        max_retries: Max retry attempts (default: 2, for 3 total attempts)
        name: Loop agent name

    Returns:
        Configured LoopAgent
    """
    model = os.getenv("PVMAP_GENERATOR_MODEL", model)

    # Note: This uses the OLD ValidationAgent behavior
    # You may need to create a separate ValidationAgentLegacy if needed
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
    'ConditionalFeedbackAgent',
    'MCPErrorResolverAgent',
    'MaxRetriesCheckAgent',
]

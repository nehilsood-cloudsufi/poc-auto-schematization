"""
PVMAP Retry Loop using ADK LoopAgent with Quality-Based Retries.

This module creates a LoopAgent that orchestrates:
1. StatePreparationAgent - Prepares state for each iteration
2. [StatVarDiscoveryAgent] - MCP-based StatVar discovery (if MCP enabled)
3. PVMAPGeneratorAgent - Generates PVMAP with structured output
4. MetadataGenerationAgent - Auto-generates stat_var_processor config
5. [MCPSpotCheckAgent] - Quick pre-validation against DC data (if MCP enabled)
6. ValidationAgent - Validates PVMAP (sets validation_passed flag)
7. [MCPErrorResolverAgent] - MCP-based error resolution (if MCP enabled)
8. QualityEvaluationAgent - Evaluates quality (escalates if acceptable/stagnant)
9. ConditionalFeedbackAgent - Unified feedback for errors or quality issues
10. MaxRetriesCheckAgent - Checks if max retries exceeded

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

from pydantic import PrivateAttr

from google.adk.agents import LoopAgent, BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from src.agents.pvmap_generator_agent import create_pvmap_generator
from src.agents.validation_agent import ValidationAgent
from src.agents.metadata_generation_agent import MetadataGenerationAgent
from src.agents.feedback_agent import create_feedback_agent
from src.agents.quality_evaluation_agent import QualityEvaluationAgent
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

        logger.info("StatePrep: starting attempt %d (0-indexed)", attempt)

        # =====================================================================
        # CRITICAL: Prevent token overflow across retry iterations.
        # ADK's LoopAgent accumulates all events from all sub-agents across
        # iterations in session.events. Even with include_contents='none',
        # the "current turn" detection can still pull in events from previous
        # iterations, causing the LLM context to exceed model limits.
        # =====================================================================
        if attempt > 0:
            self._trim_session_events(ctx)
            # Force re-read of file-backed state that may have been truncated
            # by the feedback agent's instruction preparation step.
            ctx.session.state.pop("sampled_data", None)
            ctx.session.state.pop("schema_examples", None)

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
            # Preserve human feedback if injected (for UI re-runs)
            if not ctx.session.state.get("human_feedback_provided"):
                ctx.session.state["error_feedback"] = ""
            ctx.session.state["exit_reason"] = None
            ctx.session.state["validation_counter_summary"] = ""
            # Initialize best-attempt tracking
            ctx.session.state["best_data_rows"] = 0
            ctx.session.state["best_pvmap_csv"] = None
            ctx.session.state["best_attempt_number"] = None
            ctx.session.state["best_validation_passed"] = False
            ctx.session.state["best_heuristic_score"] = 0
            ctx.session.state["best_pv_accuracy"] = None
            ctx.session.state["best_quality_metrics"] = {}

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
                                # Cache property_vocabulary for enum validation
                                pv = vocab.get("property_vocabulary", {})
                                if pv:
                                    ctx.session.state["property_vocabulary"] = pv
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

        # Cache property_vocabulary for enum validation (if not already cached)
        if not ctx.session.state.get("property_vocabulary"):
            schema_category_raw = ctx.session.state.get("schema_category", "")
            resolved_cat = ""
            for cat in ["Health", "Demographics", "Economy", "Education", "Employment", "Energy", "School"]:
                if schema_category_raw and cat.lower() in schema_category_raw.lower():
                    resolved_cat = cat
                    break
            schema_base = ctx.session.state.get("schema_base_dir", "")
            if resolved_cat and schema_base:
                vocab_path = Path(schema_base) / resolved_cat / "schema_vocab.json"
                if vocab_path.exists():
                    try:
                        import json
                        vocab_data = json.loads(vocab_path.read_text(encoding="utf-8"))
                        pv = vocab_data.get("property_vocabulary", {})
                        if pv:
                            ctx.session.state["property_vocabulary"] = pv
                            logger.info(f"Cached property_vocabulary: {len(pv)} properties for {resolved_cat}")
                    except Exception as e:
                        logger.debug(f"Failed to cache property_vocabulary: {e}")
                else:
                    logger.debug(f"Vocab file not found: {vocab_path}")
            else:
                logger.debug(f"Cannot resolve property_vocabulary: category='{schema_category_raw}' base='{schema_base}'")
        else:
            logger.debug(f"property_vocabulary already in state: {len(ctx.session.state.get('property_vocabulary', {}))} properties")

        # Read sampled_data if not already in state
        if "sampled_data" not in ctx.session.state or not ctx.session.state["sampled_data"]:
            sampled_data = ""
            using_raw_fallback = False
            # Resolve sampled data path from multiple sources
            sampled_path = ctx.session.state.get("sampled_data_path")
            if not sampled_path or not Path(sampled_path).exists():
                fallback = Path(current_dataset.output_dir) / "agentic_sampled.csv"
                if fallback.exists():
                    sampled_path = str(fallback)
                elif current_dataset.sampled_data_files:
                    sampled_path = str(current_dataset.sampled_data_files[0])
            # Level 4: Fallback to raw input file (first N rows)
            if not sampled_path or not Path(sampled_path).exists():
                input_files = getattr(current_dataset, "input_data_files", None)
                if input_files and isinstance(input_files, (list, tuple)) and len(input_files) > 0:
                    raw_path = Path(input_files[0])
                    if raw_path.exists():
                        sampled_path = str(raw_path)
                        using_raw_fallback = True
            if sampled_path and Path(sampled_path).exists():
                try:
                    content = Path(sampled_path).read_text(encoding='utf-8')
                    if using_raw_fallback:
                        # Truncate to first ~100 data rows to stay within token budget
                        lines = content.split('\n')
                        header = lines[0] if lines else ''
                        data_lines = lines[1:101]  # First 100 data rows
                        sampled_data = '\n'.join([header] + data_lines)
                        logger.warning(
                            f"Using raw input fallback (first {len(data_lines)} rows) "
                            f"— sampling was not available"
                        )
                        ctx.session.state["using_raw_input_fallback"] = True
                    else:
                        sampled_data = content
                    # Cap sampled data to ~30K chars (~7.5K tokens) to stay
                    # within model context limits for wide datasets.
                    MAX_SAMPLED_CHARS = 30000
                    if len(sampled_data) > MAX_SAMPLED_CHARS:
                        sd_lines = sampled_data.split('\n')
                        kept = []
                        total = 0
                        for line in sd_lines:
                            if total + len(line) + 1 > MAX_SAMPLED_CHARS:
                                break
                            kept.append(line)
                            total += len(line) + 1
                        orig_rows = len(sd_lines) - 1
                        kept_rows = len(kept) - 1
                        sampled_data = '\n'.join(kept)
                        logger.warning(
                            "Sampled data capped: %d→%d chars (%d→%d rows)",
                            len(content), len(sampled_data), orig_rows, kept_rows,
                        )
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
        # Emergency skeleton generation when skeleton_summary is empty
        # =====================================================================
        if not ctx.session.state.get("skeleton_summary") and ctx.session.state.get("sampled_data"):
            try:
                import pandas as pd
                import io
                data_text = ctx.session.state["sampled_data"]
                df = pd.read_csv(io.StringIO(data_text), nrows=100)
                if len(df.columns) > 1:  # Sanity check: valid CSV
                    from src.pipeline.sampling.data_context import generate_data_context
                    emergency_context = generate_data_context(
                        df, dataset_name=current_dataset.name
                    )
                    ctx.session.state["skeleton_summary"] = emergency_context.to_skeleton_summary()
                    logger.info(
                        f"Generated emergency skeleton_summary "
                        f"({len(df.columns)} columns, {len(df)} rows)"
                    )
            except Exception as e:
                logger.warning(f"Emergency skeleton generation failed: {e}")
                # Still better than empty — provide column list
                try:
                    first_line = ctx.session.state["sampled_data"].split('\n')[0]
                    cols = first_line.split(',')
                    ctx.session.state["skeleton_summary"] = (
                        f"## Column Headers\n"
                        f"The dataset has {len(cols)} columns: "
                        f"{', '.join(f'`{c.strip()}`' for c in cols)}\n"
                    )
                except Exception:
                    pass  # Truly nothing we can do

        # =====================================================================
        # Warn if critical data is missing after all fallbacks
        # =====================================================================
        if not ctx.session.state.get("sampled_data") and not ctx.session.state.get("skeleton_summary"):
            logger.error(
                f"CRITICAL: Both sampled_data and skeleton_summary are empty for "
                f"{current_dataset.name}. PVMAP generation will likely fail."
            )
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=(
                        "WARNING: No sampled data or skeleton summary available. "
                        "The LLM will generate with minimal context."
                    ))
                ])
            )

        # =====================================================================
        # CRITICAL: Escape PVMAP placeholders in feedback to prevent templating errors
        # The generator instruction uses {error_feedback},
        # which may contain PVMAP snippets with {Data}/{Number} from LLM analysis
        # =====================================================================
        error_feedback = ctx.session.state.get("error_feedback", "")
        if error_feedback:
            # Cap feedback size to prevent token overflow across iterations
            if len(error_feedback) > 4000:
                error_feedback = error_feedback[:4000] + "\n...[truncated for token budget]"
            ctx.session.state["error_feedback"] = escape_pvmap_placeholders(error_feedback)

        if "validation_counter_summary" not in ctx.session.state:
            ctx.session.state["validation_counter_summary"] = ""

        # =====================================================================
        # Log feedback status (critical for debugging retry loop)
        # =====================================================================
        if attempt > 0:
            error_feedback = ctx.session.state.get("error_feedback", "")

            if error_feedback:
                preview = error_feedback[:150] + "..." if len(error_feedback) > 150 else error_feedback
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Using feedback: {preview}")
                    ])
                )

        # Log state preparation summary
        schema_cat = ctx.session.state.get("schema_category", "(none)")
        vocab_src = "state" if ctx.session.state.get("schema_vocab_content") else "file/none"
        mcp_on = ctx.session.state.get("mcp_enabled", False)
        logger.info(
            "StatePrep complete: attempt=%d, schema_category=%s, vocab_source=%s, mcp=%s",
            attempt, schema_cat, vocab_src, mcp_on,
        )

        # =====================================================================
        # Populate prompt template and store in state
        # =====================================================================
        # Load improved_pvmap_prompt.txt, fill {{...}} placeholders with state
        # values, then escape all {word} patterns to [word] so ADK doesn't
        # try to resolve them as state variables.
        self._populate_prompt_template(ctx)

        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text=f"State prepared for attempt {attempt + 1}")
            ])
        )

    def _populate_prompt_template(self, ctx: InvocationContext) -> None:
        """
        Load PVMAP prompt template, populate placeholders, escape, and store.

        Selects template based on prompt_version state variable:
        - v1: improved_pvmap_prompt.txt (777-line original)
        - v2: improved_pvmap_prompt_v2.txt (restructured ~315 lines)

        This makes the template the single source of truth for the generator
        instruction. The populated and escaped result is stored in state as
        'populated_pvmap_prompt', which the generator's instruction
        ({populated_pvmap_prompt}) resolves at runtime.

        Template placeholders ({{...}}) are filled with state values.
        PVMAP placeholders ({Data}, {Number}, {Year}, etc.) are then escaped
        to [DATA], [NUMBER], [Year] to prevent ADK template resolution errors.
        """
        prompt_version = ctx.session.state.get("prompt_version", "v2")
        if prompt_version == "v1":
            template_name = "improved_pvmap_prompt.txt"
        else:
            template_name = "improved_pvmap_prompt_v2.txt"

        template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / template_name

        # Fallback to v1 if v2 doesn't exist yet
        if not template_path.exists() and prompt_version == "v2":
            template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "improved_pvmap_prompt.txt"
            logger.warning("Prompt v2 not found, falling back to v1")

        if not template_path.exists():
            logger.error(f"Prompt template not found: {template_path}")
            ctx.session.state["populated_pvmap_prompt"] = (
                "Generate a PVMAP for the dataset. Map all columns to Data Commons properties."
            )
            return

        try:
            template = template_path.read_text(encoding="utf-8")

            # Populate double-brace template placeholders with state values
            populated = template.replace(
                "{{DATA_CONTEXT}}",
                ctx.session.state.get("skeleton_summary", "")
            )
            populated = populated.replace(
                "{{SCHEMA_EXAMPLES}}",
                ctx.session.state.get("schema_examples", "")
            )
            populated = populated.replace(
                "{{SAMPLED_DATA}}",
                ctx.session.state.get("sampled_data", "")
            )
            populated = populated.replace(
                "{{METADATA_CONFIG}}",
                ctx.session.state.get("metadata", "")
            )
            populated = populated.replace(
                "{{ERROR_FEEDBACK}}",
                ctx.session.state.get("error_feedback", "")
            )
            populated = populated.replace(
                "{{STATVAR_SUMMARY}}",
                ctx.session.state.get("statvar_summary", "")
            )
            populated = populated.replace(
                "{{MCP_TOOLS_INSTRUCTION}}",
                ctx.session.state.get("mcp_tools_instruction", "")
            )

            # Escape ALL {word} patterns to prevent ADK template resolution.
            # This converts {Data}→[DATA], {Number}→[NUMBER], {Year}→[Year], etc.
            # The escape is idempotent (already-escaped [WORD] content is unaffected).
            populated = escape_pvmap_placeholders(populated)

            # Cap total prompt size to prevent exceeding model context limits.
            # 120K chars ≈ 30K tokens — leaves room for output + tool defs.
            MAX_PROMPT_CHARS = 120000
            if len(populated) > MAX_PROMPT_CHARS:
                logger.warning(
                    "Populated prompt exceeds budget: %d chars (max %d). Truncating.",
                    len(populated), MAX_PROMPT_CHARS,
                )
                populated = populated[:MAX_PROMPT_CHARS] + (
                    "\n\n[PROMPT TRUNCATED — generate PVMAP with available context]"
                )

            ctx.session.state["populated_pvmap_prompt"] = populated
            logger.info(
                f"Populated prompt template ({template_name}): {len(populated)} chars "
                f"(from {len(template)} char template)"
            )

        except Exception as e:
            logger.error(f"Failed to populate prompt template: {e}")
            ctx.session.state["populated_pvmap_prompt"] = (
                "Generate a PVMAP for the dataset. Map all columns to Data Commons properties."
            )

    def _trim_session_events(self, ctx: InvocationContext) -> None:
        """Trim old session events to prevent token overflow across iterations.

        ADK's LoopAgent accumulates all events from all sub-agents across all
        iterations in session.events. This causes each subsequent LLM call to
        receive growing conversation history that can exceed model context
        limits (e.g., Gemini's 1M token window).

        We keep only the last few events to provide minimal context without
        unbounded growth. This is safe because inter-iteration communication
        uses session state (not events) for all data passing.
        """
        try:
            events = ctx.session.events
            original_count = len(events)
            max_kept = 20
            if original_count > max_kept:
                del events[:-max_kept]
                logger.info(
                    "Trimmed session events: %d → %d (freed %d)",
                    original_count, len(events), original_count - len(events),
                )
        except Exception as e:
            # Event trimming is best-effort; don't block the pipeline
            logger.warning("Failed to trim session events: %s", e)

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

            # Escape PVMAP placeholders before embedding in inner agent instruction.
            # Raw {Data}/{Number}/{word} patterns in validation_error or pvmap_csv
            # would crash ADK's instruction templating in the inner LlmAgent.
            safe_validation_error = escape_pvmap_placeholders(validation_error[:2000])
            safe_pvmap_csv = escape_pvmap_placeholders(pvmap_csv[:3000])

            resolver_agent = create_error_resolver_agent(
                mcp_url=mcp_url,
                validation_error=safe_validation_error,
                pvmap_csv=safe_pvmap_csv,
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
    Unified conditional feedback agent that handles both validation failures
    and quality issues.

    This agent runs the feedback LlmAgent when:
    - Path A: validation_passed = False (validation failed)
    - Path B: validation_passed = True, quality_acceptable = False,
              quality_stagnant = False (quality low)

    Skips when quality is acceptable or stagnant (loop will exit).
    """

    # Declare feedback_agent as a Pydantic field (ADK agents use Pydantic)
    feedback_agent: LlmAgent

    def __init__(
        self,
        name: str = "UnifiedFeedback",
        model: str = "gemini-2.5-flash",
        thinking_level: Optional[str] = None,
    ):
        """
        Initialize ConditionalFeedbackAgent.

        Args:
            name: Agent name
            model: Gemini model for the inner LlmAgent
            thinking_level: Thinking level for Gemini models
        """
        feedback_agent = create_feedback_agent(model=model, thinking_level=thinking_level)
        super().__init__(
            name=name,
            feedback_agent=feedback_agent,
            sub_agents=[feedback_agent]
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Conditionally run feedback agent for validation errors or quality issues.
        """
        validation_passed = ctx.session.state.get("validation_passed", False)
        quality_acceptable = ctx.session.state.get("quality_acceptable", False)
        quality_stagnant = ctx.session.state.get("quality_stagnant", False)

        if not validation_passed:
            # Path A: Validation failed — generate error feedback
            ctx.session.state["feedback_mode"] = "VALIDATION FAILED - Analyze errors and provide fixes"
            self._prepare_feedback_state(ctx)

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Validation failed - generating error feedback...")
                ])
            )

            try:
                async for event in self.feedback_agent.run_async(ctx):
                    yield event
            except Exception as e:
                logger.error("Feedback LlmAgent crashed: %s", e, exc_info=True)
                ctx.session.state["error_feedback"] = self._build_deterministic_feedback(ctx, e)
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Feedback agent error (continuing): {str(e)[:150]}")
                    ]),
                    actions=EventActions(escalate=False)
                )

            # Log feedback preview
            error_feedback = ctx.session.state.get("error_feedback", "")
            if error_feedback:
                preview = error_feedback[:200] + "..." if len(error_feedback) > 200 else error_feedback
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Error feedback generated: {preview}")
                    ]),
                    actions=EventActions(escalate=False)
                )

        elif not quality_acceptable and not quality_stagnant:
            # Path B: Validation passed but quality low — determine if PV accuracy triggered
            quality_metrics_raw = ctx.session.state.get("quality_metrics", {})
            reject_reason = ""
            if isinstance(quality_metrics_raw, dict):
                reject_reason = quality_metrics_raw.get("quality_reject_reason", "")

            if reject_reason == "pv_accuracy_low":
                ctx.session.state["feedback_mode"] = (
                    "PV ACCURACY LOW - Validation passed and structure is OK, "
                    "but property-value pairs don't match expected patterns. "
                    "Focus on SEMANTIC correctness using the schema vocab and StatVar analysis below."
                )
            else:
                ctx.session.state["feedback_mode"] = (
                    "QUALITY LOW - Validation passed but quality score below threshold. "
                    "Focus on structural issues: row coverage, column mappings, format."
                )
            self._prepare_feedback_state(ctx)

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Quality low - generating improvement feedback...")
                ])
            )

            try:
                async for event in self.feedback_agent.run_async(ctx):
                    yield event
            except Exception as e:
                logger.error("Feedback LlmAgent crashed (quality path): %s", e, exc_info=True)
                ctx.session.state["error_feedback"] = self._build_deterministic_feedback(ctx, e)
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Feedback agent error (continuing): {str(e)[:150]}")
                    ]),
                    actions=EventActions(escalate=False)
                )

            # Log feedback preview
            error_feedback = ctx.session.state.get("error_feedback", "")
            if error_feedback:
                preview = error_feedback[:200] + "..." if len(error_feedback) > 200 else error_feedback
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Quality feedback generated: {preview}")
                    ]),
                    actions=EventActions(escalate=False)
                )

        else:
            # Skip feedback — quality acceptable or stagnant
            if quality_acceptable:
                reason = "quality acceptable"
            elif quality_stagnant:
                reason = "quality stagnant"
            else:
                reason = "not applicable"

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Skipping feedback ({reason})")
                ]),
                actions=EventActions(escalate=False)
            )

    def _build_deterministic_feedback(self, ctx: InvocationContext, error: Exception) -> str:
        """Build structured feedback from session state when the feedback LLM crashes.

        Assembles actionable feedback from already-computed state variables
        instead of returning a generic canned message.

        Args:
            ctx: Invocation context with session state.
            error: The exception that caused the LLM to crash.

        Returns:
            Structured feedback string for the next generation attempt.
        """
        sections = []
        sections.append(f"[Feedback LLM failed: {str(error)[:200]}]")
        sections.append("")

        # Validation error (the actual error from subprocess)
        validation_error = ctx.session.state.get("validation_error", "")
        if validation_error:
            sections.append("## Validation Error")
            sections.append(str(validation_error)[:1000])
            sections.append("")

        # Key match report (column matching analysis)
        key_match_report = ctx.session.state.get("key_match_report", "")
        if key_match_report:
            sections.append("## Key Match Report")
            sections.append(str(key_match_report)[:1500])
            sections.append("")

        # Counter summary (processing metrics)
        counter_summary = ctx.session.state.get("validation_counter_summary", "")
        if counter_summary:
            sections.append("## Processing Metrics")
            sections.append(str(counter_summary)[:500])
            sections.append("")

        # Pre-validation warnings (schema/eval warnings)
        pre_warnings = ctx.session.state.get("pre_validation_warnings", "")
        if pre_warnings:
            sections.append("## Pre-Validation Warnings")
            sections.append(str(pre_warnings)[:500])
            sections.append("")

        # Auto-generated high-impact fixes based on error signals
        sections.append("## High-Impact Fixes")
        error_text = str(validation_error).lower()
        fixes = []

        if "0 rows" in error_text or "0 data rows" in error_text:
            fixes.append(
                "- CRITICAL: 0 output rows — PVMAP keys likely don't match column headers. "
                "Check exact column names (case, whitespace, special characters)."
            )

        if "#eval" in error_text or "eval" in error_text:
            fixes.append(
                "- #Eval expressions may be broken — use simple Python only. "
                "NO f-strings, NO nested double quotes, NO imports. "
                "Split complex logic into per-row #Eval with named variables."
            )

        if "observationabout" in error_text:
            fixes.append(
                "- observationAbout mapping issue — ensure a place/geo column "
                "is mapped to observationAbout with the correct format (geoId/, country/, etc.)."
            )

        if "observationdate" in error_text:
            fixes.append(
                "- observationDate mapping issue — ensure a date/year column "
                "is mapped to observationDate."
            )

        if "key not found" in error_text or "undefined property" in error_text:
            fixes.append(
                "- Key mismatch — PVMAP keys must exactly match column headers. "
                "Check case sensitivity and whitespace."
            )

        if not fixes:
            fixes.append(
                "- Review the validation error above and fix the specific issues mentioned."
            )
            fixes.append(
                "- Ensure all PVMAP keys exactly match column headers from the input data."
            )

        sections.extend(fixes)

        return "\n".join(sections)

    def _prepare_feedback_state(self, ctx: InvocationContext) -> None:
        """
        Prepare state variables for unified feedback instruction templating.

        Handles both validation-failure and quality-low paths:
        - Escapes PVMAP placeholders ({Data}, {Number}) → [DATA], [NUMBER]
        - Extracts quality metrics for display
        - Formats GT score section
        - Sets defaults for all template variables
        """
        # Prepare quality-related state for instruction templating
        # NOTE: quality_metrics may have been overwritten to a string on a
        # previous attempt. Only extract from it if it's still a dict.
        quality_metrics = ctx.session.state.get("quality_metrics", {})
        if isinstance(quality_metrics, dict):
            score = quality_metrics.get("heuristic_score", 0)
            ctx.session.state["quality_score"] = score

            # Format quality_metrics for display (writes string to state)
            metrics_str = self._format_metrics(quality_metrics)
            ctx.session.state["quality_metrics"] = metrics_str

            # Format GT score section
            gt_section = self._format_gt_section(quality_metrics)
            ctx.session.state["gt_score_section"] = gt_section
        else:
            # Already formatted string from prior attempt — keep as-is
            ctx.session.state.setdefault("quality_score", 0)
            ctx.session.state.setdefault("gt_score_section", "Ground truth comparison not available.")

        # Ensure defaults for all template variables
        for key in ["validation_error", "quality_diff_summary", "feedback_mode"]:
            if key not in ctx.session.state:
                ctx.session.state[key] = ""

        # Pass schema context to feedback agent (same context generator had)
        for key in ["schema_vocab_content", "schema_category", "skeleton_summary"]:
            ctx.session.state.setdefault(key, "")

        # Ensure statvar analysis and key match report are available
        ctx.session.state.setdefault("validation_statvar_analysis", "")
        ctx.session.state.setdefault("key_match_report", "")

        # Format pvmap_repair_changes from list to string for template rendering
        repair_changes = ctx.session.state.get("pvmap_repair_changes", [])
        if isinstance(repair_changes, list) and repair_changes:
            repair_str = "\n".join(f"- {c}" for c in repair_changes)
            ctx.session.state["pvmap_repair_changes"] = repair_str
        elif not repair_changes:
            ctx.session.state["pvmap_repair_changes"] = "No auto-repairs were needed."

        # Escape all PVMAP-containing state
        for key in ["pvmap_csv", "validation_error", "sampled_data",
                     "structure_warnings", "mcp_resolved_context",
                     "quality_diff_summary", "pvmap_repair_changes"]:
            val = ctx.session.state.get(key, "")
            if val:
                # structure_warnings can be a list from the validator
                if isinstance(val, list):
                    val = "\n".join(str(item) for item in val)
                    ctx.session.state[key] = escape_pvmap_placeholders(val)
                elif isinstance(val, str):
                    ctx.session.state[key] = escape_pvmap_placeholders(val)

        # Escape schema context, statvar analysis, and key match report
        for key in ["schema_vocab_content", "skeleton_summary",
                     "validation_statvar_analysis", "key_match_report"]:
            val = ctx.session.state.get(key, "")
            if val and isinstance(val, str):
                ctx.session.state[key] = escape_pvmap_placeholders(val)

        # Counter summary escaping
        counter_summary = ctx.session.state.get("validation_counter_summary", "")
        if counter_summary:
            ctx.session.state["validation_counter_summary"] = escape_pvmap_placeholders(counter_summary)
        else:
            ctx.session.state["validation_counter_summary"] = "Processing metrics not available."

        # =====================================================================
        # Cap large state variables for feedback instruction token budget.
        # Per-iteration values (regenerated each attempt) are safe to truncate.
        # File-backed values (sampled_data) will be re-read by StatePrep.
        # skeleton_summary and schema_vocab_content are NOT capped here because
        # they're generated/loaded once and can't be recovered.
        # =====================================================================
        _FEEDBACK_CAPS = {
            "pvmap_csv": 5000,
            "validation_error": 3000,
            "sampled_data": 3000,
            "key_match_report": 2000,
            "validation_statvar_analysis": 2000,
            "quality_diff_summary": 2000,
            "mcp_resolved_context": 2000,
        }
        for key, max_chars in _FEEDBACK_CAPS.items():
            val = ctx.session.state.get(key, "")
            if isinstance(val, str) and len(val) > max_chars:
                ctx.session.state[key] = val[:max_chars] + "\n...[truncated]"

    def _format_metrics(self, metrics: dict) -> str:
        """Format quality metrics dict as readable string."""
        lines = []

        lines.append(f"Heuristic Score: {metrics.get('heuristic_score', 0):.1f}/100")
        breakdown = metrics.get("heuristic_breakdown", {})
        if breakdown:
            lines.append(f"  - Row Coverage: {breakdown.get('row_coverage', 0):.1f}/25")
            lines.append(f"  - Property Coverage: {breakdown.get('prop_coverage', 0):.1f}/25")
            lines.append(f"  - Column Coverage: {breakdown.get('column_coverage', 0):.1f}/25")
            lines.append(f"  - Format Score: {breakdown.get('format_score', 0):.1f}/25")

        if "improvement_from_previous" in metrics:
            lines.append(f"Improvement from previous: {metrics['improvement_from_previous']:.1f}%")

        # Include GT scores inline if available
        gt_node = metrics.get("gt_node_accuracy")
        if gt_node is not None:
            gt_pv = metrics.get("gt_pv_accuracy", 0)
            lines.append(f"GT Node Accuracy: {gt_node:.1f}%")
            lines.append(f"GT PV Accuracy: {gt_pv:.1f}%")

        return "\n".join(lines)

    def _format_gt_section(self, metrics: dict) -> str:
        """Format ground truth scores for the feedback instruction.

        Returns a short section with GT scores if available,
        or a note that GT is not available.
        """
        gt_node = metrics.get("gt_node_accuracy")
        gt_pv = metrics.get("gt_pv_accuracy")

        if gt_node is None:
            return "Ground truth comparison not available for this dataset."

        lines = [
            f"Node Accuracy: {gt_node:.1f}%",
            f"PV Accuracy: {gt_pv:.1f}%",
        ]

        gt_counters = metrics.get("gt_counters_summary", {})
        if gt_counters:
            nodes_matched = gt_counters.get("nodes_matched", 0)
            nodes_gt = gt_counters.get("nodes_ground_truth", 0)
            pvs_matched = gt_counters.get("pvs_matched", 0)
            pvs_modified = gt_counters.get("pvs_modified", 0)
            lines.append(f"Nodes matched: {nodes_matched}/{nodes_gt}")
            lines.append(f"PVs matched: {pvs_matched}, PVs needing fixes: {pvs_modified}")

        lines.append("")
        quality_reject = metrics.get("quality_reject_reason", "")
        if quality_reject == "pv_accuracy_low":
            lines.append("NOTE: PV accuracy is the primary concern. Use the StatVar analysis and")
            lines.append("schema vocabulary below to identify property/value mismatches.")
        else:
            lines.append("NOTE: These scores show distance from ideal. Use them to gauge severity,")
            lines.append("but focus on the heuristic issues above for specific fixes.")

        return "\n".join(lines)


class MaxRetriesCheckAgent(BaseAgent):
    """
    Checks if max retries exceeded after all feedback agents run.

    If max retries reached, sets final failure state and escalates
    to exit the loop.
    """

    _max_retries: int = PrivateAttr(default=3)

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
            # Priority-based best-attempt selection + re-validation
            current_rows = ctx.session.state.get("validation_data_rows", 0)
            best_rows = ctx.session.state.get("best_data_rows", 0)
            best_csv = ctx.session.state.get("best_pvmap_csv")
            best_was_valid = ctx.session.state.get("best_validation_passed", False)
            current_valid = ctx.session.state.get("validation_passed", False)
            restored_best = False

            # Priority-based selection:
            # 1. Valid > Invalid
            # 2. If both same validity → compare accuracy (PV > heuristic > data_rows)
            should_restore = False
            if best_csv and best_csv != ctx.session.state.get("pvmap_csv"):
                if best_was_valid and not current_valid:
                    # Case 1: Best is valid, current is not → restore
                    should_restore = True
                elif current_valid and not best_was_valid:
                    # Case 2: Current is valid, best is not → keep current
                    should_restore = False
                else:
                    # Case 3: Both valid or both invalid → compare accuracy
                    best_pv = ctx.session.state.get("best_pv_accuracy")
                    current_pv = ctx.session.state.get("quality_metrics", {})
                    if isinstance(current_pv, dict):
                        current_pv = current_pv.get("gt_pv_accuracy")
                    else:
                        current_pv = None

                    best_heuristic = ctx.session.state.get("best_heuristic_score", 0)
                    current_metrics = ctx.session.state.get("quality_metrics", {})
                    if isinstance(current_metrics, dict):
                        current_heuristic = current_metrics.get("heuristic_score", 0)
                    else:
                        current_heuristic = 0

                    if best_pv is not None and current_pv is not None:
                        if best_pv > current_pv:
                            should_restore = True
                        elif current_pv > best_pv:
                            should_restore = False
                        else:
                            # PV accuracy tied → tiebreaker: data rows
                            should_restore = best_rows > current_rows
                    elif best_pv is not None:
                        should_restore = True
                    elif current_pv is not None:
                        should_restore = False
                    else:
                        if best_heuristic > current_heuristic:
                            should_restore = True
                        elif current_heuristic > best_heuristic:
                            should_restore = False
                        else:
                            # Heuristic tied → tiebreaker: data rows
                            should_restore = best_rows > current_rows

            if should_restore:
                ctx.session.state["pvmap_csv"] = best_csv
                ctx.session.state["validation_data_rows"] = best_rows
                best_attempt = ctx.session.state.get("best_attempt_number", "?")
                restored_best = True
                logger.info(
                    f"Restored best attempt #{best_attempt} "
                    f"({best_rows} rows vs current {current_rows} rows, "
                    f"best_valid={best_was_valid}, current_valid={current_valid})"
                )
                # Re-save best PVMAP to file
                try:
                    current_dataset = ctx.session.state.get("current_dataset")
                    if current_dataset:
                        pvmap_path = Path(current_dataset.output_dir) / "generated_pvmap.csv"
                        pvmap_path.write_text(best_csv, encoding='utf-8')
                except Exception as e:
                    logger.warning(f"Failed to re-save best PVMAP: {e}")

                # Re-run validation to regenerate processed.csv
                if best_was_valid:
                    try:
                        current_dataset = ctx.session.state.get("current_dataset")
                        if current_dataset:
                            from src.tools.validation_tool import run_validation
                            input_file = (
                                str(current_dataset.input_data_files[0])
                                if current_dataset.input_data_files else None
                            )
                            metadata_file = ""
                            if current_dataset.metadata_files:
                                use_metadata = ctx.session.state.get("use_metadata", False)
                                if use_metadata:
                                    metadata_file = str(current_dataset.metadata_files[0])

                            if input_file:
                                pvmap_path_str = str(
                                    Path(current_dataset.output_dir) / "generated_pvmap.csv"
                                )
                                result = run_validation(
                                    input_data=input_file,
                                    pvmap_path=pvmap_path_str,
                                    metadata_file=metadata_file,
                                    output_dir=str(current_dataset.output_dir),
                                    timeout=300,
                                )
                                ctx.session.state["validation_data_rows"] = result.get(
                                    "data_rows", 0
                                )
                                logger.info(
                                    "Re-validation after restore: success=%s, data_rows=%d",
                                    result["success"],
                                    result.get("data_rows", 0),
                                )
                    except Exception as e:
                        logger.warning(f"Re-validation failed: {e}")

            # If we restored a validated best attempt, mark as success
            if restored_best and best_was_valid:
                ctx.session.state["generation_success"] = True
                ctx.session.state["validation_passed"] = True
                ctx.session.state["exit_reason"] = "best_attempt_restored"
                logger.info(
                    f"Best attempt was validated — marking generation_success=True"
                )
            else:
                ctx.session.state["generation_success"] = False
                ctx.session.state["exit_reason"] = "max_retries"

            ctx.session.state["retry_count"] = attempt

            # Determine error/success message
            error_feedback = ctx.session.state.get("error_feedback", "")
            generation_success = ctx.session.state.get("generation_success", False)

            if generation_success:
                # Best attempt was restored and was valid
                best_attempt = ctx.session.state.get("best_attempt_number", "?")
                msg = (
                    f"Max retries ({self._max_retries + 1}) exceeded, but restored "
                    f"validated attempt #{best_attempt} ({best_rows} data rows). "
                    f"Marking as SUCCESS."
                )
                ctx.session.state["error"] = None
            elif error_feedback:
                msg = f"Max retries ({self._max_retries + 1}) exceeded. Last feedback: {error_feedback[:500]}"
                ctx.session.state["error"] = msg
            else:
                quality_metrics = ctx.session.state.get("quality_metrics", {})
                if isinstance(quality_metrics, dict):
                    score = quality_metrics.get("heuristic_score", 0)
                else:
                    score = ctx.session.state.get("quality_score", 0)
                msg = f"Max retries ({self._max_retries + 1}) exceeded. Best quality: {score:.1f}%"
                ctx.session.state["error"] = msg

            # Update generation notes with final status
            try:
                from src.agents.pvmap_generation.helpers import update_generation_notes
                current_dataset = ctx.session.state.get("current_dataset")
                if current_dataset:
                    validation_passed = ctx.session.state.get("validation_passed", False)
                    if generation_success:
                        final_status = (
                            f"PASSED (restored best attempt #{ctx.session.state.get('best_attempt_number', '?')}) "
                            f"after {self._max_retries + 1} attempts (exit_reason: best_attempt_restored)"
                        )
                    else:
                        final_status = f"FAILED after {self._max_retries + 1} attempts (exit_reason: max_retries)"
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
                        final_status=final_status
                    )
            except Exception:
                pass  # Don't fail on logging errors

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=msg)
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
    min_attempts: Optional[int] = None,
    thinking_level: Optional[str] = None,
) -> LoopAgent:
    """
    Create PVMAP generation retry loop with quality-based retries.

    The loop runs (without MCP):
    1. StatePreparationAgent - Prepares state for generator
    2. PVMAPGeneratorAgent - Generates PVMAP (structured JSON)
    3. MetadataGenerationAgent - Auto-generates stat_var_processor config
    4. ValidationAgent - Validates; sets validation_passed flag
    5. QualityEvaluationAgent - Evaluates quality; ESCALATES if acceptable/stagnant
    6. ConditionalFeedbackAgent - Unified feedback for errors or quality issues
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
        min_attempts: Minimum attempts before allowing quality exit (optional)

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
            thinking_level=thinking_level,
        )
    else:
        from src.agents.pvmap_generator_agent import create_pvmap_generator_without_schema
        generator = create_pvmap_generator_without_schema(
            model=model, name="Generator", thinking_level=thinking_level,
        )

    metadata_generator = MetadataGenerationAgent(name="MetadataGenerator")
    validator = ValidationAgent(name="Validator")
    quality_evaluator = QualityEvaluationAgent(name="QualityEvaluator", min_attempts=min_attempts)
    unified_feedback = ConditionalFeedbackAgent(name="UnifiedFeedback", model=model, thinking_level=thinking_level)
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
    sub_agents.append(metadata_generator)

    # Insert MCPSpotCheckAgent between metadata_generator and validator when MCP enabled
    if enable_mcp and mcp_url:
        from src.agents.mcp_spot_check_agent import MCPSpotCheckAgent
        spot_check = MCPSpotCheckAgent(name="MCPSpotCheck")
        sub_agents.append(spot_check)
        logger.info("MCPSpotCheckAgent added to retry loop (MCP enabled)")

    sub_agents.append(validator)

    # Insert MCPErrorResolverAgent when MCP enabled
    if enable_mcp and mcp_url:
        error_resolver = MCPErrorResolverAgent(name="MCPErrorResolver")
        sub_agents.append(error_resolver)
        logger.info("MCPErrorResolverAgent added to retry loop (MCP enabled)")

    sub_agents.extend([
        quality_evaluator,
        unified_feedback,
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
# Module exports
# ============================================================================

__all__ = [
    'create_pvmap_retry_loop',
    'StatePreparationAgent',
    'ConditionalFeedbackAgent',
    'MCPErrorResolverAgent',
    'MaxRetriesCheckAgent',
]

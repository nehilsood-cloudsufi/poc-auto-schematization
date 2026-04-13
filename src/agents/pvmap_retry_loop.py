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
from typing import Any, Optional, AsyncGenerator

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging
import re

from pydantic import PrivateAttr

from google.adk.agents import LoopAgent, SequentialAgent, BaseAgent, LlmAgent
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


# ============================================================================
# Compaction functions for token overflow prevention
# ============================================================================

# Regex to match section headers like "## 1. ...", "## 1.5 ...", "## 9. ..."
# Handles both "## N. TEXT" (trailing period) and "## N.M TEXT" (no trailing period)
_SECTION_HEADER_RE = re.compile(r'^##\s+(\d+\.?\d*)[.\s]')

# Sections to DROP entirely in feedback compaction (generation-only content)
_FEEDBACK_DROP_SECTIONS = {"6", "7", "9"}

# Sections to COMPACT in feedback (reduce detail level)
_FEEDBACK_COMPACT_SECTIONS = {"1.5", "4"}


def _split_skeleton_sections(skeleton: str) -> list[tuple[str, str]]:
    """Split skeleton_summary into (section_id, section_text) pairs.

    Returns list of tuples: [("header", preamble_text), ("1", section1_text), ...]
    The first element captures any text before the first ## header.
    """
    sections = []
    current_id = "header"
    current_lines: list[str] = []

    for line in skeleton.split('\n'):
        m = _SECTION_HEADER_RE.match(line)
        if m:
            # Save previous section
            sections.append((current_id, '\n'.join(current_lines)))
            current_id = m.group(1).rstrip('.')  # Normalize: "6." → "6", "1.5" → "1.5"
            current_lines = [line]
        else:
            current_lines.append(line)

    # Save last section
    sections.append((current_id, '\n'.join(current_lines)))
    return sections


def _compact_column_reference_table(section_text: str, max_samples: int = 2) -> str:
    """Compact Section 1.5 by reducing sample values per column.

    Keeps column name, type, cardinality but reduces sample values from 5 to max_samples.
    """
    lines = section_text.split('\n')
    result = []
    for line in lines:
        # Match markdown table data rows (start with |, not header separators)
        if line.startswith('|') and '---' not in line:
            parts = [p.strip() for p in line.split('|')]
            # parts: ['', col, type, cardinality, samples, '']
            if len(parts) >= 6:
                samples_str = parts[4]
                # Trim samples to max_samples values
                sample_vals = [s.strip() for s in samples_str.split(',')]
                if len(sample_vals) > max_samples:
                    trimmed = ', '.join(sample_vals[:max_samples])
                    parts[4] = f"{trimmed}, ..."
                    line = '| ' + ' | '.join(parts[1:-1]) + ' |'
        result.append(line)
    return '\n'.join(result)


def _compact_dimension_section(section_text: str, max_values: int = 5) -> str:
    """Compact Section 4 by reducing dimension value lists and dropping aggregate flags.

    Keeps dimension names and counts but reduces value lists to max_values.
    Drops aggregate value warning lines.
    """
    lines = section_text.split('\n')
    result = []
    for line in lines:
        # Drop aggregate warning lines
        if '⚠ Aggregate values detected' in line:
            continue
        # Compact dimension value lists: - **`dim`** (N values): [v1, v2, ...]
        if line.strip().startswith('- **`') and 'values):' in line:
            # Find the bracket content
            bracket_start = line.find('[')
            bracket_end = line.rfind(']')
            if bracket_start >= 0 and bracket_end > bracket_start:
                values_str = line[bracket_start + 1:bracket_end]
                values = [v.strip() for v in values_str.split(',')]
                # Check for existing "... (N total)" suffix
                clean_values = []
                total_hint = ""
                for v in values:
                    if v.startswith('...'):
                        total_hint = v
                    else:
                        clean_values.append(v)
                if len(clean_values) > max_values:
                    trimmed = ', '.join(clean_values[:max_values])
                    total = total_hint if total_hint else f"... ({len(clean_values)} total)"
                    line = line[:bracket_start + 1] + trimmed + ', ' + total + ']'
        result.append(line)
    return '\n'.join(result)


def format_statvar_examples_for_prompt(examples, max_chars=3000):
    """Format StatVar examples as compact reference for the LLM prompt."""
    if not examples:
        return ""
    lines = [
        "## Real Data Commons StatVar Decompositions",
        "Use these as reference for property names and dcs: prefix usage.",
        "Every StatVar MUST decompose into: populationType + measuredProperty + constraint properties.",
        "",
    ]
    for sv in examples:
        dcid = sv.get("dcid", "")
        props = [f"{k}: {v}" for k, v in sv.items() if k != "dcid"]
        line = f"  {dcid}: {', '.join(props)}"
        candidate = "\n".join(lines + [line])
        if len(candidate) > max_chars:
            break
        lines.append(line)
    return "\n".join(lines)


def _compact_skeleton_for_feedback(skeleton: str) -> str:
    """Compact skeleton_summary for feedback agent token budget.

    Strategy: keep diagnostic core, drop generation-only content.
    - KEEP: Sections 1, 2, 3, 5, 8 (topology, classifications, anchors, measurements, DC detection)
    - COMPACT: Section 1.5 (samples 5→2), Section 4 (values 15→5, drop aggregates)
    - DROP: Section 6 (StatVar pattern), Section 7 (one-shot example), Section 9 (coverage)

    Expected reduction: ~60-70% for wide datasets.
    """
    if not skeleton or len(skeleton) < 5000:
        return skeleton

    sections = _split_skeleton_sections(skeleton)
    result_parts = []

    for sec_id, sec_text in sections:
        if sec_id in _FEEDBACK_DROP_SECTIONS:
            continue  # Drop sections 6, 7, 9
        elif sec_id == "1.5":
            result_parts.append(_compact_column_reference_table(sec_text, max_samples=2))
        elif sec_id == "4":
            result_parts.append(_compact_dimension_section(sec_text, max_values=5))
        else:
            result_parts.append(sec_text)

    return '\n'.join(result_parts)


def _compact_skeleton_for_generator(skeleton: str, budget: int = 40000) -> str:
    """Less aggressive compaction for generator, only when skeleton exceeds budget.

    Strategy: preserve all sections but trim verbose content.
    - Section 1.5: Reduce samples 5→3
    - Section 4: Reduce values 15→8
    - All other sections: KEEP unchanged

    Expected reduction: ~30-40% when triggered.
    """
    if not skeleton or len(skeleton) <= budget:
        return skeleton

    sections = _split_skeleton_sections(skeleton)
    result_parts = []

    for sec_id, sec_text in sections:
        if sec_id == "1.5":
            result_parts.append(_compact_column_reference_table(sec_text, max_samples=3))
        elif sec_id == "4":
            result_parts.append(_compact_dimension_section(sec_text, max_values=8))
        else:
            result_parts.append(sec_text)

    compacted = '\n'.join(result_parts)

    # If still over budget after section compaction, truncate from the end
    # but preserve the first section (topology/headers) and last few lines
    if len(compacted) > budget:
        compacted = compacted[:budget] + "\n\n[skeleton truncated for token budget]"

    return compacted


def _compact_vocab_for_feedback(vocab_content: str) -> str:
    """Compact schema_vocab_content for feedback agent token budget.

    Strategy: keep property structure, compact enum lists, drop examples.
    - StatVar Skeletons: KEEP (short, critical)
    - VALID ENUM VALUES: COMPACT — property names + first 3 values + count
    - Representative examples: DROP (generation-only)
    - Schema.org context: KEEP (short, useful)

    Expected reduction: ~50-75%.
    """
    if not vocab_content or len(vocab_content) < 3000:
        return vocab_content

    lines = vocab_content.split('\n')
    result = []
    in_examples = False
    in_enums = False

    for line in lines:
        # Detect section transitions
        if '**Representative examples' in line:
            in_examples = True
            in_enums = False
            continue
        if 'Schema.org base:' in line:
            in_examples = False
            result.append(line)
            continue
        if '**VALID ENUM VALUES' in line:
            in_enums = True
            in_examples = False
            result.append(line)
            continue
        if in_enums and line.startswith('**') and 'VALID ENUM' not in line:
            # Next bold section after enums
            in_enums = False

        # Drop example lines
        if in_examples:
            continue

        # Compact enum lines: "- property: val1, val2, val3, ..." → first 3 + count
        if in_enums and line.startswith('- ') and ':' in line:
            colon_idx = line.index(':')
            prop_name = line[:colon_idx + 1]
            values_str = line[colon_idx + 1:].strip()
            values = [v.strip() for v in values_str.split(',')]
            # Strip "... (N total)" suffix if present
            clean_values = [v for v in values if not v.startswith('...')]
            if len(clean_values) > 3:
                trimmed = ', '.join(clean_values[:3])
                result.append(f"{prop_name} {trimmed}, ... ({len(clean_values)} total)")
            else:
                result.append(line)
            continue

        result.append(line)

    return '\n'.join(result)


def _compact_vocab_for_generator(vocab_content: str, budget: int = 15000) -> str:
    """Less aggressive vocab compaction for generator, only when over budget.

    Strategy: trim enum values from up to 30 to 10, keep examples.
    """
    if not vocab_content or len(vocab_content) <= budget:
        return vocab_content

    lines = vocab_content.split('\n')
    result = []
    in_enums = False

    for line in lines:
        if '**VALID ENUM VALUES' in line:
            in_enums = True
            result.append(line)
            continue
        if in_enums and line.startswith('**') and 'VALID ENUM' not in line:
            in_enums = False

        # Compact enum lines to 10 values
        if in_enums and line.startswith('- ') and ':' in line:
            colon_idx = line.index(':')
            prop_name = line[:colon_idx + 1]
            values_str = line[colon_idx + 1:].strip()
            values = [v.strip() for v in values_str.split(',')]
            clean_values = [v for v in values if not v.startswith('...')]
            if len(clean_values) > 10:
                trimmed = ', '.join(clean_values[:10])
                result.append(f"{prop_name} {trimmed}, ... ({len(clean_values)} total)")
            else:
                result.append(line)
            continue

        result.append(line)

    compacted = '\n'.join(result)
    if len(compacted) > budget:
        compacted = compacted[:budget] + "\n\n[schema vocab truncated for token budget]"
    return compacted


class GeneratorWrapperAgent(BaseAgent):
    """Wrapper that creates a fresh Generator per iteration.

    This ensures MCP toolset SSE connections are fresh each time,
    preventing stale connection hangs on retry attempts. The old
    Generator (and its MCP connection) goes out of scope at the
    end of each iteration and is cleaned up by GC.

    This matches the pattern used by StatVarDiscoveryAgent, which
    also creates a fresh agent per invocation and never hangs.
    """

    _generator_kwargs: dict = PrivateAttr(default_factory=dict)
    _use_structured_output: bool = PrivateAttr(default=True)

    def __init__(
        self,
        name: str = "Generator",
        use_structured_output: bool = True,
        **generator_kwargs,
    ):
        super().__init__(name=name)
        self._generator_kwargs = generator_kwargs
        self._use_structured_output = use_structured_output

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        if self._use_structured_output:
            generator = create_pvmap_generator(name=self.name, **self._generator_kwargs)
        else:
            from src.agents.pvmap_generator_agent import create_pvmap_generator_without_schema
            generator = create_pvmap_generator_without_schema(
                name=self.name,
                model=self._generator_kwargs.get("model", "gemini-3.1-pro-preview"),
                thinking_level=self._generator_kwargs.get("thinking_level"),
            )
        try:
            async for event in generator.run_async(ctx):
                yield event
        finally:
            # Explicit MCP tool cleanup — don't rely on GC
            for tool in getattr(generator, "tools", []) or []:
                close_fn = getattr(tool, "close", None)
                if close_fn and callable(close_fn):
                    try:
                        import asyncio
                        result = close_fn()
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        pass  # Cleanup failures must not crash the loop


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
            # Initialize or load feedback ledger
            ledger_json = ctx.session.state.get("feedback_ledger_json", "")
            if ledger_json:
                # Ledger was passed from feedback.py (accumulated feedback)
                pass  # ledger already in state
            elif ctx.session.state.get("human_feedback_provided"):
                # Legacy: human_feedback was injected as raw string, wrap in ledger
                from src.api.models.feedback import FeedbackEntry, FeedbackType, FeedbackLedger as FL
                raw = ctx.session.state.get("error_feedback", "")
                ledger = FL()
                if raw:
                    ledger.add_entry(FeedbackEntry(
                        type=FeedbackType.FREE_TEXT, round=1,
                        source="human", content=raw,
                    ))
                ctx.session.state["feedback_ledger_json"] = ledger.model_dump_json()
            else:
                from src.api.models.feedback import FeedbackLedger as FL
                ctx.session.state["feedback_ledger_json"] = FL().model_dump_json()
                ctx.session.state["error_feedback"] = ""
            ctx.session.state["exit_reason"] = None
            ctx.session.state["validation_counter_summary"] = ""
            ctx.session.state["column_completeness_report"] = ""
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

            # Generate PVMAP skeleton + verify properties + write artifact
            skip_discovery = ctx.session.state.get("skip_column_discovery", False)
            data_context = ctx.session.state.get("data_context", {})
            if not skip_discovery and data_context and data_context.get("column_roles"):
                try:
                    from src.pipeline.pvmap_skeleton.skeleton_generator import (
                        build_column_manifest, generate_pvmap_skeleton,
                        write_discovery_artifact,
                    )
                    from src.pipeline.pvmap_skeleton.skeleton_verifier import (
                        verify_skeleton_properties,
                        correct_skeleton_from_verification,
                    )
                    manifest = build_column_manifest(data_context)
                    pvmap_skeleton = generate_pvmap_skeleton(manifest, data_context)

                    # Verify properties against Schema.org + DC API + MCP
                    mcp_enabled = ctx.session.state.get("mcp_enabled", False)
                    mcp_url = ctx.session.state.get("mcp_url")
                    # Only use DC API if key is configured
                    import os as _os
                    dc_api_available = bool(_os.environ.get("DC_API_KEY") or _os.environ.get("GEMINI_API_KEY"))
                    verification = verify_skeleton_properties(
                        skeleton_csv=pvmap_skeleton,
                        manifest=manifest,
                        data_context=data_context,
                        use_dc_api=dc_api_available,
                        use_mcp=mcp_enabled,
                        mcp_url=mcp_url,
                    )

                    # Correct invalid properties in skeleton using verification results
                    pvmap_skeleton = correct_skeleton_from_verification(
                        pvmap_skeleton, verification,
                    )

                    ctx.session.state["pvmap_skeleton"] = pvmap_skeleton
                    ctx.session.state["column_manifest"] = manifest
                    ctx.session.state["column_verification"] = verification

                    # Write discovery artifact
                    current_dataset = ctx.session.state.get("current_dataset")
                    if current_dataset and hasattr(current_dataset, 'output_dir'):
                        write_discovery_artifact(
                            manifest, verification, data_context,
                            str(current_dataset.output_dir),
                        )

                    logger.info(
                        "Column discovery: %d/%d properties verified, sources=%s",
                        verification.get("properties_valid", 0),
                        verification.get("properties_checked", 0),
                        verification.get("verification_sources", []),
                    )

                    # Phase 3: MCP enrichment (if MCP available)
                    mcp_enabled = ctx.session.state.get("mcp_enabled", False)
                    mcp_url_val = ctx.session.state.get("mcp_url")
                    if mcp_enabled and mcp_url_val:
                        try:
                            from src.pipeline.pvmap_skeleton.mcp_enrichment import (
                                enrich_via_mcp_hybrid,
                                enrich_skeleton_with_results,
                                format_dimension_reference,
                            )
                            enrichment = await enrich_via_mcp_hybrid(
                                data_context=data_context,
                                verification=verification,
                                mcp_url=mcp_url_val,
                            )
                            if enrichment.get("enrichment_success"):
                                pvmap_skeleton = enrich_skeleton_with_results(
                                    pvmap_skeleton, enrichment,
                                    verification=verification,
                                )
                                ctx.session.state["pvmap_skeleton"] = pvmap_skeleton
                                dim_ref = format_dimension_reference(enrichment)
                                ctx.session.state["dimension_value_reference"] = dim_ref
                                ctx.session.state["mcp_enrichment"] = enrichment
                                logger.info(
                                    "MCP enrichment: %d mappings, %d patterns, %d suggestions",
                                    len(enrichment.get("column_mappings", {})),
                                    len(enrichment.get("cross_column_patterns", [])),
                                    len(enrichment.get("llm_suggestions", {})),
                                )
                        except Exception as e:
                            logger.warning("MCP enrichment failed (non-fatal): %s", e)
                            ctx.session.state["dimension_value_reference"] = ""
                    else:
                        ctx.session.state["dimension_value_reference"] = ""

                except Exception as e:
                    logger.warning("Failed to generate/verify PVMAP skeleton: %s", e)
                    ctx.session.state["pvmap_skeleton"] = ""
                    ctx.session.state["column_manifest"] = {}
                    ctx.session.state["column_verification"] = {}
                    ctx.session.state["dimension_value_reference"] = ""

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
        if "approved_mapping_plan" not in ctx.session.state:
            ctx.session.state["approved_mapping_plan"] = ""
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
        # Parse auto_feedback_raw from previous iteration into ledger
        # =====================================================================
        auto_raw = ctx.session.state.pop("auto_feedback_raw", "")
        if auto_raw and attempt > 0:
            ledger_json = ctx.session.state.get("feedback_ledger_json", "")
            if ledger_json:
                from src.api.models.feedback import FeedbackEntry, FeedbackType, FeedbackLedger as FL
                ledger = FL.model_validate_json(ledger_json)
                ledger.clear_auto_entries()
                ledger.add_entry(FeedbackEntry(
                    type=FeedbackType.AUTO, round=attempt,
                    source="auto", content=auto_raw,
                ))
                ctx.session.state["feedback_ledger_json"] = ledger.model_dump_json()

        # =====================================================================
        # CRITICAL: Render feedback ledger into prompt sections and escape
        # PVMAP placeholders to prevent ADK templating errors.
        # The generator instruction uses {error_feedback},
        # which may contain PVMAP snippets with {Data}/{Number} from LLM analysis
        # =====================================================================
        ledger_json = ctx.session.state.get("feedback_ledger_json", "")
        if ledger_json:
            from src.api.models.feedback import FeedbackLedger as FL
            from src.api.services.feedback_merger import FeedbackMerger
            ledger = FL.model_validate_json(ledger_json)
            merger = FeedbackMerger()
            human_text, auto_text = merger.render_separate(ledger)
            merged = merger.merge(ledger)

            # Cap and escape each section
            if len(merged) > 4000:
                merged = merged[:4000] + "\n...[truncated for token budget]"

            ctx.session.state["human_feedback_prompt"] = escape_pvmap_placeholders(human_text)
            ctx.session.state["auto_feedback_prompt"] = escape_pvmap_placeholders(auto_text)
            ctx.session.state["error_feedback"] = escape_pvmap_placeholders(merged)
            ctx.session.state["human_feedback_provided"] = ledger.has_human_entries()
            ctx.session.state["human_instructions_summary"] = escape_pvmap_placeholders(
                merger.render_human_summary(ledger)
            )

            # Persist ledger to disk for API access
            try:
                current_dataset = ctx.session.state.get("current_dataset")
                if current_dataset and hasattr(current_dataset, "output_dir"):
                    from src.api.services.feedback_store import save_ledger_to_disk
                    save_ledger_to_disk(ledger, Path(current_dataset.output_dir))
            except Exception as e:
                logger.warning("Failed to persist ledger to disk: %s", e)
        else:
            # Fallback: no ledger, use raw error_feedback
            error_feedback = ctx.session.state.get("error_feedback", "")
            if error_feedback:
                if len(error_feedback) > 4000:
                    error_feedback = error_feedback[:4000] + "\n...[truncated for token budget]"
                ctx.session.state["error_feedback"] = escape_pvmap_placeholders(error_feedback)
            ctx.session.state.setdefault("human_feedback_prompt", "")
            ctx.session.state.setdefault("auto_feedback_prompt", "")
            ctx.session.state.setdefault("human_instructions_summary", "(No human instructions provided)")

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

        This makes the template the single source of truth for the generator
        instruction. The populated and escaped result is stored in state as
        'populated_pvmap_prompt', which the generator's instruction
        ({populated_pvmap_prompt}) resolves at runtime.

        If an enriched mapping plan (with statvar_blueprint) is available in
        state as 'approved_plan_json', the executor prompt is used instead of
        the standard PVMAP prompt. The executor prompt is a simpler, more
        mechanical translation that follows the pre-approved plan faithfully.

        Template placeholders ({{...}}) are filled with state values.
        PVMAP placeholders ({Data}, {Number}, {Year}, etc.) are then escaped
        to [DATA], [NUMBER], [Year] to prevent ADK template resolution errors.
        """
        # =================================================================
        # Check if we have an enriched plan — use executor prompt if so
        # =================================================================
        approved_plan_json = ctx.session.state.get("approved_plan_json", "")
        use_executor = False
        enriched_plan = None

        if approved_plan_json:
            try:
                import json
                plan_data = json.loads(approved_plan_json) if isinstance(approved_plan_json, str) else approved_plan_json
                if "statvar_blueprint" in plan_data:
                    from src.api.models.plan import EnrichedMappingPlan
                    enriched_plan = EnrichedMappingPlan.model_validate(plan_data)
                    use_executor = True
            except Exception as e:
                logger.warning("Failed to parse enriched plan, falling back to standard prompt: %s", e)

        if use_executor and enriched_plan is not None:
            self._populate_executor_prompt(ctx, enriched_plan)
            return

        prompt_version = ctx.session.state.get("prompt_version", "v2")
        template_name = f"improved_pvmap_prompt_{prompt_version}.txt"
        template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / template_name

        if not template_path.exists():
            logger.error(f"Prompt template not found: {template_path}")
            ctx.session.state["populated_pvmap_prompt"] = (
                "Generate a PVMAP for the dataset. Map all columns to Data Commons properties."
            )
            return

        try:
            template = template_path.read_text(encoding="utf-8")

            # =================================================================
            # Budget-based allocation: compact large components BEFORE injection
            # so that error_feedback is NEVER silently truncated on retries.
            # =================================================================
            MAX_PROMPT_CHARS = 120000

            skeleton = ctx.session.state.get("skeleton_summary", "")
            schema_ex = ctx.session.state.get("schema_examples", "")

            # Append StatVar examples to schema context
            schema_vocab_raw = ctx.session.state.get("schema_vocab_content", "")
            if schema_vocab_raw:
                try:
                    import json as _json
                    vocab_data = _json.loads(schema_vocab_raw) if isinstance(schema_vocab_raw, str) and schema_vocab_raw.startswith("{") else {}
                    statvar_examples = vocab_data.get("statvar_examples", [])
                    if statvar_examples:
                        sv_text = format_statvar_examples_for_prompt(statvar_examples)
                        if sv_text:
                            schema_ex = schema_ex + "\n\n" + sv_text if schema_ex else sv_text
                except Exception:
                    pass  # Non-fatal: schema_vocab_content may not be JSON

            sampled = ctx.session.state.get("sampled_data", "")
            error_fb = ctx.session.state.get("error_feedback", "")

            # Prepend repair changes to feedback so generator sees what was auto-fixed
            repair_changes = ctx.session.state.get("pvmap_repair_changes", "")
            if repair_changes and error_fb:
                if isinstance(repair_changes, list):
                    changes_text = "\n".join(f"- {c}" for c in repair_changes[:10])
                else:
                    changes_text = str(repair_changes)
                if changes_text.strip() and "No auto-repairs" not in changes_text:
                    repair_prefix = (
                        "## AUTO-REPAIRS FROM PREVIOUS ATTEMPT\n"
                        "These were fixed programmatically. Generate correctly this time:\n"
                        + changes_text + "\n\n"
                    )
                    error_fb = repair_prefix + error_fb

            metadata = ctx.session.state.get("metadata", "")
            statvar_summary = ctx.session.state.get("statvar_summary", "")
            approved_plan = ctx.session.state.get("approved_mapping_plan", "")
            mcp_instruction = ctx.session.state.get("mcp_tools_instruction", "")

            # Reserve space for template text + smaller/fixed sections + error_feedback
            pvmap_skel = ctx.session.state.get("pvmap_skeleton", "")
            reserved = (
                len(template) + len(error_fb) + len(metadata)
                + len(statvar_summary) + len(mcp_instruction)
                + len(pvmap_skel) + 5000  # safety margin
            )
            remaining = max(MAX_PROMPT_CHARS - reserved, 30000)

            # Allocate remaining budget: 50% skeleton, 25% schema, 25% sampled data
            skeleton_budget = int(remaining * 0.50)
            schema_budget = int(remaining * 0.25)
            sampled_budget = int(remaining * 0.25)

            # Compact if over budget (originals in state are NOT modified)
            if len(skeleton) > skeleton_budget:
                skeleton = _compact_skeleton_for_generator(skeleton, skeleton_budget)
            if len(schema_ex) > schema_budget:
                schema_ex = _compact_vocab_for_generator(schema_ex, schema_budget)
            if len(sampled) > sampled_budget:
                sd_lines = sampled.split('\n')
                kept = [sd_lines[0]] if sd_lines else []  # header
                total = len(kept[0]) if kept else 0
                for line in sd_lines[1:]:
                    if total + len(line) + 1 > sampled_budget:
                        break
                    kept.append(line)
                    total += len(line) + 1
                sampled = '\n'.join(kept)

            logger.info(
                "Prompt budget: skeleton=%d, schema=%d, sampled=%d, feedback=%d, reserved=%d",
                len(skeleton), len(schema_ex), len(sampled), len(error_fb), reserved,
            )

            # Populate double-brace template placeholders with (possibly compacted) values
            populated = template.replace("{{DATA_CONTEXT}}", skeleton)
            populated = populated.replace("{{SCHEMA_EXAMPLES}}", schema_ex)
            populated = populated.replace("{{SAMPLED_DATA}}", sampled)
            populated = populated.replace("{{METADATA_CONFIG}}", metadata)
            populated = populated.replace("{{ERROR_FEEDBACK}}", error_fb)
            populated = populated.replace("{{STATVAR_SUMMARY}}", statvar_summary)
            populated = populated.replace("{{APPROVED_MAPPING_PLAN}}", approved_plan)
            populated = populated.replace("{{MCP_TOOLS_INSTRUCTION}}", mcp_instruction)

            # Inject dimension value reference (from MCP enrichment)
            dim_ref = ctx.session.state.get("dimension_value_reference", "")
            populated = populated.replace("{{DIMENSION_VALUE_REFERENCE}}", dim_ref)

            # v3 split-feedback placeholders
            human_fb_prompt = ctx.session.state.get("human_feedback_prompt", "")
            auto_fb_prompt = ctx.session.state.get("auto_feedback_prompt", "")
            populated = populated.replace("{{HUMAN_FEEDBACK}}", human_fb_prompt)
            populated = populated.replace("{{AUTO_FEEDBACK}}", auto_fb_prompt)

            # Inject PVMAP skeleton — strip entire section if empty
            pvmap_skeleton = ctx.session.state.get("pvmap_skeleton", "")
            if pvmap_skeleton.strip():
                populated = populated.replace("{{PVMAP_SKELETON}}", pvmap_skeleton)
            else:
                # Remove entire skeleton section to avoid confusing the LLM
                import re as _re
                populated = _re.sub(
                    r'## PVMAP Skeleton \(pre-filled baseline\).*?Missing any column from this skeleton causes data corruption\. Treat this as a mandatory checklist\.',
                    '',
                    populated,
                    flags=_re.DOTALL,
                )
                populated = populated.replace("{{PVMAP_SKELETON}}", "")

            # Escape ALL {word} patterns to prevent ADK template resolution.
            # This converts {Data}→[DATA], {Number}→[NUMBER], {Year}→[Year], etc.
            # The escape is idempotent (already-escaped [WORD] content is unaffected).
            populated = escape_pvmap_placeholders(populated)

            # Last-resort cap (should rarely trigger after budget allocation)
            if len(populated) > MAX_PROMPT_CHARS:
                logger.warning(
                    "Populated prompt still exceeds budget after compaction: %d chars (max %d). Truncating.",
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

    def _populate_executor_prompt(
        self, ctx: InvocationContext, enriched_plan: "Any"
    ) -> None:
        """Populate the executor prompt template from an enriched mapping plan.

        The executor prompt is used when a human-approved enriched plan
        (with statvar_blueprint, value_dictionaries, etc.) is available.
        It produces a more mechanical, plan-faithful PVMAP generation prompt.
        """
        template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "pvmap_executor_prompt.txt"
        if not template_path.exists():
            logger.error("Executor prompt template not found: %s", template_path)
            ctx.session.state["populated_pvmap_prompt"] = (
                "Generate a PVMAP for the dataset. Map all columns to Data Commons properties."
            )
            return

        try:
            template = template_path.read_text(encoding="utf-8")

            # --- Build {{PLAN_COLUMN_TABLE}} ---
            table_lines = ["| Column | Role | Property | Value Expression |",
                           "| --- | --- | --- | --- |"]
            for col in enriched_plan.active_columns:
                sel = col.candidates[col.selected_index] if col.candidates else None
                prop = sel.property if sel else ""
                val_expr = sel.value_expression if sel else ""
                table_lines.append(
                    f"| {col.column_name} | {col.role.value} | {prop} | {val_expr} |"
                )
            plan_column_table = "\n".join(table_lines)

            # --- Build {{STATVAR_BLUEPRINT}} ---
            bp = enriched_plan.statvar_blueprint
            bp_lines = [
                f"Base: {bp.base_properties}",
                f"Constraint columns: {bp.constraint_columns}",
                f"Measure columns: {bp.measure_columns}",
            ]
            statvar_blueprint = "\n".join(bp_lines)

            # --- Build {{VALUE_DICTIONARIES}} ---
            vd_lines: list[str] = []
            for vd in enriched_plan.value_dictionaries:
                vd_lines.append(f"**{vd.column_name}** (property: {vd.dc_property}):")
                for m in vd.mappings:
                    if m.action == "MAP" and m.dcid:
                        vd_lines.append(f"  - {m.raw_value} -> {m.dcid}")
                    elif m.action == "DROP_CONSTRAINT":
                        vd_lines.append(
                            f"  - {m.raw_value} -> DROP_CONSTRAINT ({m.reason})"
                        )
                    elif m.action == "DROP_ROW":
                        vd_lines.append(
                            f"  - {m.raw_value} -> DROP_ROW ({m.reason})"
                        )
                    else:
                        vd_lines.append(f"  - {m.raw_value} -> {m.dcid or m.action} ({m.reason})")
                if vd.total_indicators:
                    vd_lines.append(f"  Total indicators: {vd.total_indicators}")
            value_dictionaries = "\n".join(vd_lines) if vd_lines else "(none)"

            # --- Build {{PLACE_RESOLUTION}} ---
            if enriched_plan.place_resolution:
                pr = enriched_plan.place_resolution
                place_lines = [
                    f"Column: {pr.column_name}",
                    f"Format: {pr.format_detected}",
                    f"Prefix rule: {pr.prefix_rule}",
                ]
                if pr.pad_zeros is not None:
                    place_lines.append(f"Pad zeros: {pr.pad_zeros}")
                place_lines.append(f"Resolution rate: {pr.resolution_rate:.0%}")
                place_resolution = "\n".join(place_lines)
            else:
                place_resolution = "(none)"

            # --- Build {{TIME_RESOLUTION}} ---
            if enriched_plan.time_resolution:
                tr = enriched_plan.time_resolution
                time_resolution = (
                    f"Columns: {tr.columns}\n"
                    f"Format: {tr.format_detected}\n"
                    f"Normalization: {tr.normalization_rule}"
                )
            else:
                time_resolution = "(none)"

            # --- Build {{COLUMN_RELATIONSHIPS}} ---
            rel_lines: list[str] = []
            for cr in enriched_plan.column_relationships:
                if cr.relationship.value != "independent":
                    rel_lines.append(
                        f"- {cr.column_a} <-> {cr.column_b}: "
                        f"{cr.relationship.value} (strength={cr.strength:.2f}) — "
                        f"{cr.pvmap_implication}"
                    )
            column_relationships = "\n".join(rel_lines) if rel_lines else "(none)"

            # --- Build {{PVMAP_SKELETON}} from state ---
            pvmap_skeleton = ctx.session.state.get("pvmap_skeleton", "")

            # --- Build {{SAMPLED_DATA}} — header + 5 rows ---
            sampled_data_full = ctx.session.state.get("sampled_data", "")
            if sampled_data_full:
                sd_lines = sampled_data_full.split("\n")
                # Keep header + first 5 data rows
                sampled_data = "\n".join(sd_lines[:6])
            else:
                sampled_data = "(no sampled data available)"

            # --- Fill template ---
            populated = template.replace("{{PLAN_COLUMN_TABLE}}", plan_column_table)
            populated = populated.replace("{{STATVAR_BLUEPRINT}}", statvar_blueprint)
            populated = populated.replace("{{VALUE_DICTIONARIES}}", value_dictionaries)
            populated = populated.replace("{{PLACE_RESOLUTION}}", place_resolution)
            populated = populated.replace("{{TIME_RESOLUTION}}", time_resolution)
            populated = populated.replace("{{COLUMN_RELATIONSHIPS}}", column_relationships)
            populated = populated.replace("{{PVMAP_SKELETON}}", pvmap_skeleton)
            populated = populated.replace("{{SAMPLED_DATA}}", sampled_data)

            # Escape all {word} patterns to prevent ADK template resolution
            populated = escape_pvmap_placeholders(populated)

            ctx.session.state["populated_pvmap_prompt"] = populated
            logger.info(
                "Populated executor prompt: %d chars (enriched plan for '%s')",
                len(populated), enriched_plan.dataset_name,
            )

        except Exception as e:
            logger.error("Failed to populate executor prompt: %s", e)
            # Fall back to standard prompt population
            logger.info("Falling back to standard prompt template after executor failure")
            # Reset the method to use standard path by clearing the early return
            prompt_version = ctx.session.state.get("prompt_version", "v2")
            template_name = f"improved_pvmap_prompt_{prompt_version}.txt"
            fallback_path = PROJECT_ROOT / "src" / "resources" / "prompts" / template_name
            if fallback_path.exists():
                ctx.session.state["populated_pvmap_prompt"] = (
                    escape_pvmap_placeholders(fallback_path.read_text(encoding="utf-8"))
                )
            else:
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


# Keys whose originals are saved before feedback compaction and restored after
_FEEDBACK_RESTORE_KEYS = ["skeleton_summary", "schema_vocab_content"]


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
        feedback_prompt_version: str = "v2",
    ):
        """
        Initialize ConditionalFeedbackAgent.

        Args:
            name: Agent name
            model: Gemini model for the inner LlmAgent
            thinking_level: Thinking level for Gemini models
            feedback_prompt_version: Feedback prompt version ('v1' or 'v2')
        """
        feedback_agent = create_feedback_agent(
            model=model, thinking_level=thinking_level, prompt_version=feedback_prompt_version
        )
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

            # Save originals before compaction (restored in finally block)
            saved = {k: ctx.session.state.get(k) for k in _FEEDBACK_RESTORE_KEYS
                     if ctx.session.state.get(k) is not None}

            self._prepare_feedback_state(ctx)
            self._trim_events_for_feedback(ctx)

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
                ctx.session.state["auto_feedback_raw"] = self._build_deterministic_feedback(ctx, e)
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Feedback agent error (continuing): {str(e)[:150]}")
                    ]),
                    actions=EventActions(escalate=False)
                )
            finally:
                # Restore originals so next Generator iteration gets full context
                for k, v in saved.items():
                    ctx.session.state[k] = v

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

            # Save originals before compaction (restored in finally block)
            saved = {k: ctx.session.state.get(k) for k in _FEEDBACK_RESTORE_KEYS
                     if ctx.session.state.get(k) is not None}

            self._prepare_feedback_state(ctx)
            self._trim_events_for_feedback(ctx)

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
                ctx.session.state["auto_feedback_raw"] = self._build_deterministic_feedback(ctx, e)
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Feedback agent error (continuing): {str(e)[:150]}")
                    ]),
                    actions=EventActions(escalate=False)
                )
            finally:
                # Restore originals so next Generator iteration gets full context
                for k, v in saved.items():
                    ctx.session.state[k] = v

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
            ctx.session.state["quality_metrics_display"] = metrics_str

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

        # Ensure statvar analysis, key match report, and completeness report are available
        ctx.session.state.setdefault("validation_statvar_analysis", "")
        ctx.session.state.setdefault("key_match_report", "")
        ctx.session.state.setdefault("column_completeness_report", "")

        # Format pvmap_repair_changes from list to string for template rendering
        repair_changes = ctx.session.state.get("pvmap_repair_changes", [])
        if isinstance(repair_changes, list) and repair_changes:
            repair_str = "\n".join(f"- {c}" for c in repair_changes)
            ctx.session.state["pvmap_repair_changes"] = repair_str
        elif not repair_changes:
            ctx.session.state["pvmap_repair_changes"] = "No auto-repairs were needed."

        # Escape all PVMAP-containing state
        for key in ["pvmap_csv", "validation_error",
                     "quality_diff_summary", "pvmap_repair_changes"]:
            val = ctx.session.state.get(key, "")
            if val:
                # structure_warnings can be a list from the validator
                if isinstance(val, list):
                    val = "\n".join(str(item) for item in val)
                    ctx.session.state[key] = escape_pvmap_placeholders(val)
                elif isinstance(val, str):
                    ctx.session.state[key] = escape_pvmap_placeholders(val)

        # Escape schema context, statvar analysis, key match report, and completeness report
        for key in ["schema_vocab_content", "skeleton_summary",
                     "validation_statvar_analysis", "key_match_report",
                     "column_completeness_report"]:
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
        # Compact large context variables for feedback token budget.
        # Originals are saved/restored by _run_async_impl's finally block.
        # =====================================================================
        skeleton = ctx.session.state.get("skeleton_summary", "")
        if skeleton and len(skeleton) > 5000:
            ctx.session.state["skeleton_summary"] = _compact_skeleton_for_feedback(skeleton)

        vocab = ctx.session.state.get("schema_vocab_content", "")
        if vocab and len(vocab) > 3000:
            ctx.session.state["schema_vocab_content"] = _compact_vocab_for_feedback(vocab)

        # =====================================================================
        # Cap per-iteration state variables for feedback instruction budget.
        # Per-iteration values (regenerated each attempt) are safe to truncate.
        # File-backed values (sampled_data) will be re-read by StatePrep.
        # =====================================================================
        _FEEDBACK_CAPS = {
            "pvmap_csv": 3000,
            "validation_error": 2000,
            "validation_counter_summary": 2000,
            "key_match_report": 1500,
            "validation_statvar_analysis": 1500,
            "quality_diff_summary": 1500,
        }
        for key, max_chars in _FEEDBACK_CAPS.items():
            val = ctx.session.state.get(key, "")
            if isinstance(val, str) and len(val) > max_chars:
                ctx.session.state[key] = val[:max_chars] + "\n...[truncated]"

        # =====================================================================
        # Total instruction size guard (last-resort fallback).
        # After compaction + per-variable caps, check total. If still over 30K,
        # progressively truncate the largest remaining variables.
        # =====================================================================
        _FEEDBACK_STATE_KEYS = [
            "skeleton_summary", "schema_vocab_content", "pvmap_csv",
            "validation_error", "key_match_report",
            "validation_statvar_analysis", "quality_diff_summary",
            "validation_counter_summary",
        ]
        MAX_FEEDBACK_TOTAL = 30000
        total = sum(len(ctx.session.state.get(k, "")) for k in _FEEDBACK_STATE_KEYS)
        if total > MAX_FEEDBACK_TOTAL:
            logger.warning(
                "Feedback state total %d exceeds %d — applying progressive truncation",
                total, MAX_FEEDBACK_TOTAL,
            )
            # Sort by size descending and truncate the largest until under budget
            sized = sorted(
                [(k, len(ctx.session.state.get(k, ""))) for k in _FEEDBACK_STATE_KEYS],
                key=lambda x: x[1], reverse=True,
            )
            for key, size in sized:
                if total <= MAX_FEEDBACK_TOTAL:
                    break
                # Cut the variable to half its current size
                val = ctx.session.state.get(key, "")
                if isinstance(val, str) and len(val) > 1000:
                    new_size = max(len(val) // 2, 500)
                    ctx.session.state[key] = val[:new_size] + "\n...[truncated for token budget]"
                    total -= (len(val) - new_size)

        # =====================================================================
        # Inject GT feedback section conditionally for v2 prompt template.
        # When GT is available, builds a detailed GT analysis section.
        # When GT is not available, sets empty string (v2 prompt omits section).
        # =====================================================================
        gt_available = bool(ctx.session.state.get("gt_pvmap_path_cached"))
        if gt_available:
            gt_section = self._build_gt_feedback_section(ctx)
        else:
            gt_section = ""
        ctx.session.state["gt_feedback_section"] = gt_section

        logger.info(
            "Feedback state sizes: skeleton=%d, vocab=%d, sampled=%d, total=%d",
            len(ctx.session.state.get("skeleton_summary", "")),
            len(ctx.session.state.get("schema_vocab_content", "")),
            len(ctx.session.state.get("sampled_data", "")),
            total,
        )

    def _trim_events_for_feedback(self, ctx: InvocationContext) -> None:
        """Trim session events before feedback LLM call (defense in depth).

        Prevents the feedback agent from receiving excessively long event history
        which can push the total context over model limits.
        """
        try:
            events = ctx.session.events
            if len(events) > 10:
                orig = len(events)
                del events[:-10]
                logger.info("Pre-feedback event trim: %d -> %d", orig, len(events))
        except Exception as e:
            logger.warning("Pre-feedback event trim failed: %s", e)

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

    def _build_gt_feedback_section(self, ctx: InvocationContext) -> str:
        """Build GT-specific feedback section for the v2 prompt template."""
        quality_metrics = ctx.session.state.get("quality_metrics", {})
        if isinstance(quality_metrics, str):
            # Already formatted from prior attempt; use gt_score_section fallback
            gt_score = ctx.session.state.get("gt_score_section", "")
        else:
            gt_score = self._format_gt_section(quality_metrics)
        return f"""## Ground Truth Comparison
{gt_score}

### PV Accuracy Analysis
The PVMAP structure may be OK but property-value pairs don't match expected patterns:
- Cross-reference generated properties against the schema vocabulary
- Check if dimension values use proper DCIDs from vocabulary
- Verify populationType matches stat_var_skeletons for this domain
- Check StatVar Analysis for corrupted/malformed values
- If raw strings appear where DCIDs expected, suggest Column:Value mappings with vocabulary DCIDs"""


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

        gt_available = bool(ctx.session.state.get("gt_pvmap_path_cached"))
        effective_max = self._max_retries if gt_available else min(self._max_retries, 2)
        if attempt >= effective_max:
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

            gt_tag = "" if gt_available else " (non-GT reduced)"
            if generation_success:
                # Best attempt was restored and was valid
                best_attempt = ctx.session.state.get("best_attempt_number", "?")
                msg = (
                    f"Max retries ({effective_max + 1}{gt_tag}) exceeded, but restored "
                    f"validated attempt #{best_attempt} ({best_rows} data rows). "
                    f"Marking as SUCCESS."
                )
                ctx.session.state["error"] = None
            elif error_feedback:
                msg = f"Max retries ({effective_max + 1}{gt_tag}) exceeded. Last feedback: {error_feedback[:500]}"
                ctx.session.state["error"] = msg
            else:
                quality_metrics = ctx.session.state.get("quality_metrics", {})
                if isinstance(quality_metrics, dict):
                    score = quality_metrics.get("heuristic_score", 0)
                else:
                    score = ctx.session.state.get("quality_score", 0)
                msg = f"Max retries ({effective_max + 1}{gt_tag}) exceeded. Best quality: {score:.1f}%"
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
                    types.Part(text=f"Attempt {attempt + 1} did not meet criteria. {effective_max - attempt} retries remaining.")
                ]),
                actions=EventActions(escalate=False)  # Continue loop
            )


class TieredCorrectionAgent(BaseAgent):
    """Tiered correction pipeline: programmatic fix -> LLM patch -> full regen.

    Only runs if quality is not acceptable after attempt 0.
    Internally runs up to 2 additional validation passes (Tier 1+2 combined, Tier 3).
    """

    _patch_agent: Any = PrivateAttr(default=None)
    _generator_wrapper: Any = PrivateAttr(default=None)
    _metadata_agent: Any = PrivateAttr(default=None)
    _validation_agent: Any = PrivateAttr(default=None)
    _model: str = PrivateAttr(default="gemini-3.1-pro-preview")
    _thinking_level: Optional[str] = PrivateAttr(default=None)
    _enable_mcp: bool = PrivateAttr(default=False)
    _mcp_url: Optional[str] = PrivateAttr(default=None)
    _use_structured_output: bool = PrivateAttr(default=True)
    _feedback_prompt_version: str = PrivateAttr(default="v2")

    def __init__(
        self,
        name: str = "TieredCorrection",
        patch_agent=None,
        generator_wrapper=None,
        metadata_agent=None,
        validation_agent=None,
        model: str = "gemini-3.1-pro-preview",
        thinking_level: Optional[str] = None,
        enable_mcp: bool = False,
        mcp_url: Optional[str] = None,
        use_structured_output: bool = True,
        feedback_prompt_version: str = "v2",
    ):
        super().__init__(name=name)
        self._patch_agent = patch_agent
        self._generator_wrapper = generator_wrapper
        self._metadata_agent = metadata_agent
        self._validation_agent = validation_agent
        self._model = model
        self._thinking_level = thinking_level
        self._enable_mcp = enable_mcp
        self._mcp_url = mcp_url
        self._use_structured_output = use_structured_output
        self._feedback_prompt_version = feedback_prompt_version

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Run tiered correction: programmatic -> LLM patch -> full regen."""
        from src.pipeline.validation.log_filter import filter_counters
        from src.pipeline.validation.pvmap_corrector import apply_correction_rules
        from src.tools.validation_tool import run_validation

        # =====================================================================
        # GATE CHECK: skip if attempt 0 already produced acceptable quality
        # =====================================================================
        quality_acceptable = ctx.session.state.get("quality_acceptable", False)
        quality_stagnant = ctx.session.state.get("quality_stagnant", False)
        validation_passed = ctx.session.state.get("validation_passed", False)

        if quality_acceptable:
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Quality acceptable after attempt 0 -- skipping tiered correction.")
                ])
            )
            return

        if quality_stagnant:
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Quality stagnant after attempt 0 -- skipping tiered correction.")
                ])
            )
            return

        if validation_passed and not ctx.session.state.get("quality_diff_summary"):
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Validation passed with no quality issues -- skipping tiered correction.")
                ])
            )
            return

        # =====================================================================
        # SAVE BEST-SO-FAR from attempt 0
        # =====================================================================
        best_pvmap = ctx.session.state.get("pvmap_csv", "")
        best_rows = ctx.session.state.get("validation_data_rows", 0)
        best_valid = ctx.session.state.get("validation_passed", False)

        current_dataset = ctx.session.state.get("current_dataset")
        if not current_dataset:
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="ERROR: No current_dataset in state -- cannot run tiered correction.")
                ])
            )
            return

        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text="Starting tiered correction pipeline...")
            ])
        )

        # =====================================================================
        # ENFORCE HUMAN FEEDBACK CONSTRAINTS
        # =====================================================================
        ledger_json = ctx.session.state.get("feedback_ledger_json", "")
        if ledger_json:
            from src.agents.feedback_enforcement import apply_enforcement
            from src.api.models.feedback import FeedbackLedger as FL
            ledger = FL.model_validate_json(ledger_json)
            enforced, enforcement_changes = apply_enforcement(best_pvmap, ledger)
            if enforcement_changes:
                best_pvmap = enforced
                ctx.session.state["pvmap_csv"] = enforced
                ctx.session.state["feedback_enforcement_applied"] = True
                ctx.session.state["feedback_enforcement_changes"] = enforcement_changes
                # Write enforced PVMAP to disk
                pvmap_path = Path(current_dataset.output_dir) / "generated_pvmap.csv"
                pvmap_path.write_text(enforced, encoding="utf-8")
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Enforced {len(enforcement_changes)} human feedback constraint(s)")
                    ])
                )

        # =====================================================================
        # TIER 1: Programmatic correction
        # =====================================================================
        counters_path = Path(current_dataset.output_dir) / "processed_counters.txt"
        filtered_logs = None

        if counters_path.exists():
            try:
                filtered_logs = filter_counters(counters_path, attempt_number=1)
                key_match_report = ctx.session.state.get("key_match_report", "")

                input_data_path = None
                if current_dataset.input_data_files:
                    input_data_path = Path(str(current_dataset.input_data_files[0]))

                corrected, changes = apply_correction_rules(
                    pvmap_csv=best_pvmap,
                    filtered_logs=filtered_logs,
                    key_match_report=key_match_report,
                    input_data_path=input_data_path,
                )

                if changes:
                    ctx.session.state["pvmap_csv"] = corrected
                    # Write corrected PVMAP to file
                    pvmap_path = Path(current_dataset.output_dir) / "generated_pvmap.csv"
                    pvmap_path.write_text(corrected, encoding="utf-8")

                    # Run validation
                    tier1_result = self._run_validation_pass(
                        ctx, current_dataset, corrected, "Tier 1"
                    )

                    if tier1_result.get("success"):
                        ctx.session.state["validation_passed"] = True
                        ctx.session.state["validation_data_rows"] = tier1_result.get("data_rows", 0)
                        ctx.session.state["validation_counter_summary"] = tier1_result.get("counter_summary", "")

                        tier1_rows = tier1_result.get("data_rows", 0)
                        if tier1_rows > best_rows or (tier1_result["success"] and not best_valid):
                            best_pvmap = corrected
                            best_rows = tier1_rows
                            best_valid = True
                            ctx.session.state["best_data_rows"] = tier1_rows
                            ctx.session.state["best_pvmap_csv"] = corrected
                            ctx.session.state["best_attempt_number"] = ctx.session.state.get("attempt_number", 0)
                            ctx.session.state["best_validation_passed"] = True

                        # Evaluate quality to check if we can stop
                        score, acceptable = self._evaluate_quality(ctx, corrected)
                        if acceptable:
                            ctx.session.state["quality_acceptable"] = True
                            ctx.session.state["exit_reason"] = "quality_met"
                            ctx.session.state["generation_success"] = True
                            ctx.session.state["retry_count"] = 1
                            yield Event(
                                author=self.name,
                                content=types.Content(parts=[
                                    types.Part(text=f"Tier 1: {len(changes)} programmatic fixes applied. Quality acceptable (score={score:.1f}). Done.")
                                ])
                            )
                            return
                    else:
                        # Tier 1 validation failed -- update best if more rows
                        tier1_rows = tier1_result.get("data_rows", 0)
                        if self._is_better_attempt(tier1_result, best_rows, best_valid):
                            best_pvmap = corrected
                            best_rows = tier1_rows
                            best_valid = tier1_result.get("success", False)

                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[
                            types.Part(text=f"Tier 1: {len(changes)} programmatic fixes applied.")
                        ])
                    )
                else:
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[
                            types.Part(text="Tier 1: No programmatic fixes applicable.")
                        ])
                    )
            except Exception as e:
                logger.warning("Tier 1 correction failed: %s", e, exc_info=True)
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Tier 1: Error ({str(e)[:100]}), continuing to Tier 2.")
                    ])
                )
        else:
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Tier 1: No counters file found, skipping programmatic correction.")
                ])
            )

        # =====================================================================
        # TIER 2: Lightweight LLM patch
        # =====================================================================
        if self._patch_agent:
            try:
                # Start from best known PVMAP
                ctx.session.state["pvmap_csv"] = best_pvmap
                # Ensure state vars referenced by patch agent template exist
                ctx.session.state.setdefault("key_match_report", "")
                ctx.session.state.setdefault("validation_counter_summary", "")
                if filtered_logs:
                    ctx.session.state["validation_counter_summary"] = filtered_logs.to_summary()

                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text="Tier 2: Running lightweight LLM patch...")
                    ])
                )

                # Escape state before running patch agent
                for key in ["pvmap_csv", "validation_counter_summary", "key_match_report"]:
                    val = ctx.session.state.get(key, "")
                    if val and isinstance(val, str):
                        ctx.session.state[key] = escape_pvmap_placeholders(val)

                async for event in self._patch_agent.run_async(ctx):
                    yield event

                patched = ctx.session.state.get("pvmap_csv", "")
                if patched and patched != best_pvmap:
                    # Write and validate
                    pvmap_path = Path(current_dataset.output_dir) / "generated_pvmap.csv"
                    pvmap_path.write_text(patched, encoding="utf-8")

                    tier2_result = self._run_validation_pass(
                        ctx, current_dataset, patched, "Tier 2"
                    )

                    if tier2_result.get("success"):
                        ctx.session.state["validation_passed"] = True
                        ctx.session.state["validation_data_rows"] = tier2_result.get("data_rows", 0)
                        ctx.session.state["validation_counter_summary"] = tier2_result.get("counter_summary", "")

                        tier2_rows = tier2_result.get("data_rows", 0)
                        if self._is_better_attempt(tier2_result, best_rows, best_valid):
                            best_pvmap = patched
                            best_rows = tier2_rows
                            best_valid = True
                            ctx.session.state["best_data_rows"] = tier2_rows
                            ctx.session.state["best_pvmap_csv"] = patched
                            ctx.session.state["best_attempt_number"] = ctx.session.state.get("attempt_number", 0)
                            ctx.session.state["best_validation_passed"] = True

                        score, acceptable = self._evaluate_quality(ctx, patched)
                        if acceptable:
                            ctx.session.state["quality_acceptable"] = True
                            ctx.session.state["exit_reason"] = "quality_met"
                            ctx.session.state["generation_success"] = True
                            ctx.session.state["retry_count"] = 2
                            yield Event(
                                author=self.name,
                                content=types.Content(parts=[
                                    types.Part(text=f"Tier 2: LLM patch improved quality (score={score:.1f}). Done.")
                                ])
                            )
                            return
                    else:
                        # Safety: discard if fewer rows than best
                        tier2_rows = tier2_result.get("data_rows", 0)
                        if self._is_better_attempt(tier2_result, best_rows, best_valid):
                            best_pvmap = patched
                            best_rows = tier2_rows
                            best_valid = tier2_result.get("success", False)

                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[
                            types.Part(text=f"Tier 2: LLM patch applied ({tier2_result.get('data_rows', 0)} rows).")
                        ])
                    )
                else:
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[
                            types.Part(text="Tier 2: LLM patch made no changes.")
                        ])
                    )
            except Exception as e:
                logger.warning("Tier 2 LLM patch failed: %s", e, exc_info=True)
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Tier 2: LLM patch error ({str(e)[:100]}), continuing to Tier 3.")
                    ])
                )

        # =====================================================================
        # TIER 3: Full regeneration (ONE time)
        # =====================================================================
        if self._generator_wrapper and self._metadata_agent and self._validation_agent:
            try:
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text="Tier 3: Full regeneration with feedback...")
                    ])
                )

                # Prepare state for full regeneration
                ctx.session.state["pvmap_csv"] = best_pvmap
                if filtered_logs:
                    ctx.session.state["error_feedback"] = filtered_logs.to_summary()
                ctx.session.state["attempt_number"] = -1  # StatePrep increments to 0, treating Tier 3 as a fresh start

                # Trim session events to prevent token overflow
                self._trim_session_events(ctx)

                # Reset per-iteration flags
                ctx.session.state["validation_passed"] = False
                ctx.session.state["quality_acceptable"] = False
                ctx.session.state["quality_stagnant"] = False

                # Re-populate prompt template (StatePrep logic)
                # Force re-read of file-backed state
                ctx.session.state.pop("sampled_data", None)
                ctx.session.state.pop("schema_examples", None)

                # Clear stale feedback state before Tier 3 fresh start
                ctx.session.state.pop("auto_feedback_raw", None)
                ctx.session.state.pop("error_feedback", None)

                # Run StatePrep to re-populate state
                state_prep = StatePreparationAgent(name="TieredStatePrep")
                async for event in state_prep.run_async(ctx):
                    yield event

                # Run Generator -> MetadataGen -> Validate
                for agent in [self._generator_wrapper, self._metadata_agent, self._validation_agent]:
                    async for event in agent.run_async(ctx):
                        yield event

                tier3_valid = ctx.session.state.get("validation_passed", False)
                tier3_rows = ctx.session.state.get("validation_data_rows", 0)
                tier3_pvmap = ctx.session.state.get("pvmap_csv", "")

                tier3_result = {
                    "success": tier3_valid,
                    "data_rows": tier3_rows,
                }
                if self._is_better_attempt(tier3_result, best_rows, best_valid):
                    best_pvmap = tier3_pvmap
                    best_rows = tier3_rows
                    best_valid = tier3_valid

                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Tier 3: Full regeneration complete ({tier3_rows} rows, valid={tier3_valid}).")
                    ])
                )

            except Exception as e:
                logger.warning("Tier 3 full regeneration failed: %s", e, exc_info=True)
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Tier 3: Full regeneration error ({str(e)[:100]}).")
                    ])
                )

        # =====================================================================
        # FINALIZE: restore best-so-far if current is not the best
        # =====================================================================
        current_pvmap = ctx.session.state.get("pvmap_csv", "")
        current_valid = ctx.session.state.get("validation_passed", False)
        current_rows = ctx.session.state.get("validation_data_rows", 0)

        should_restore = False
        if best_pvmap and best_pvmap != current_pvmap:
            if best_valid and not current_valid:
                should_restore = True
            elif not current_valid and not best_valid and best_rows > current_rows:
                should_restore = True
            elif best_valid and current_valid and best_rows > current_rows:
                should_restore = True

        if should_restore:
            ctx.session.state["pvmap_csv"] = best_pvmap
            ctx.session.state["validation_data_rows"] = best_rows
            ctx.session.state["validation_passed"] = best_valid
            # Re-write best PVMAP to file
            try:
                pvmap_path = Path(current_dataset.output_dir) / "generated_pvmap.csv"
                pvmap_path.write_text(best_pvmap, encoding="utf-8")
            except Exception:
                pass
            logger.info(
                "Restored best PVMAP: %d rows (valid=%s) vs current %d rows (valid=%s)",
                best_rows, best_valid, current_rows, current_valid,
            )

        # Set final state
        if not ctx.session.state.get("exit_reason"):
            if best_valid:
                ctx.session.state["exit_reason"] = "tiered_correction_complete"
                ctx.session.state["generation_success"] = True
            else:
                ctx.session.state["exit_reason"] = "max_retries"
                ctx.session.state["generation_success"] = False
        if not ctx.session.state.get("retry_count"):
            ctx.session.state["retry_count"] = ctx.session.state.get("attempt_number", 0)

        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text=f"Tiered correction complete: best={best_rows} rows, valid={best_valid}.")
            ])
        )

    def _run_validation_pass(
        self,
        ctx: InvocationContext,
        current_dataset,
        pvmap_csv: str,
        tier_label: str,
    ) -> dict:
        """Write PVMAP to file and run validation subprocess.

        Returns:
            Validation result dict with keys: success, data_rows, counter_summary, etc.
        """
        from src.tools.validation_tool import run_validation

        input_file = None
        if current_dataset.input_data_files:
            input_file = str(current_dataset.input_data_files[0])

        if not input_file or not Path(input_file).exists():
            return {"success": False, "data_rows": 0, "error": "No input file"}

        pvmap_path = Path(current_dataset.output_dir) / "generated_pvmap.csv"

        # Get metadata file (same logic as ValidationAgent)
        metadata_file = None
        generated_config = ctx.session.state.get("generated_config_path")
        if generated_config and Path(generated_config).exists():
            metadata_file = generated_config
        if not metadata_file and current_dataset.use_metadata and current_dataset.metadata_files:
            metadata_file = str(current_dataset.metadata_files[0])
        if not metadata_file:
            if current_dataset.ground_truth_metadata and Path(current_dataset.ground_truth_metadata).exists():
                gt_meta_dir = Path(current_dataset.ground_truth_metadata)
                gt_meta_files = sorted(gt_meta_dir.glob("*.csv"))
                if gt_meta_files:
                    metadata_file = str(gt_meta_files[0])

        logger.info("Running %s validation pass", tier_label)
        result = run_validation(
            input_data=input_file,
            pvmap_path=str(pvmap_path),
            metadata_file=metadata_file or "",
            output_dir=str(current_dataset.output_dir),
            timeout=300,
        )
        logger.info(
            "%s validation: success=%s, data_rows=%d",
            tier_label, result["success"], result.get("data_rows", 0),
        )
        return result

    def _evaluate_quality(
        self, ctx: InvocationContext, pvmap_csv: str
    ) -> tuple:
        """Calculate heuristic quality score.

        Returns:
            Tuple of (score: float, is_acceptable: bool)
        """
        try:
            from src.tools.heuristic_quality import calculate_heuristic_score
            sampled_data = ctx.session.state.get("sampled_data", "")
            metadata = ctx.session.state.get("metadata", "")
            result = calculate_heuristic_score(
                pvmap_csv=pvmap_csv,
                sampled_data=sampled_data,
                metadata=metadata,
            )
            score = result.get("total", 0)
            threshold = 70.0
            return score, score >= threshold
        except Exception as e:
            logger.warning("Quality evaluation failed: %s", e)
            return 0.0, False

    def _is_better_attempt(
        self, current_result: dict, best_rows: int, best_valid: bool
    ) -> bool:
        """Check if current result is better than best-so-far.

        Priority: valid > invalid, then data_rows.
        """
        current_valid = current_result.get("success", False)
        current_rows = current_result.get("data_rows", 0)

        if current_valid and not best_valid:
            return True
        if not current_valid and best_valid:
            return False
        return current_rows > best_rows

    def _trim_session_events(self, ctx: InvocationContext) -> None:
        """Trim old session events to prevent token overflow."""
        try:
            events = ctx.session.events
            original_count = len(events)
            max_kept = 20
            if original_count > max_kept:
                del events[:-max_kept]
                logger.info(
                    "Trimmed session events: %d -> %d",
                    original_count, len(events),
                )
        except Exception as e:
            logger.warning("Failed to trim session events: %s", e)


def create_pvmap_retry_loop(
    model: str = "gemini-2.5-flash",
    max_retries: int = 3,
    use_structured_output: bool = True,
    name: str = "PVMAPRetryLoop",
    enable_mcp: bool = False,
    mcp_url: Optional[str] = None,
    min_attempts: Optional[int] = None,
    thinking_level: Optional[str] = None,
    feedback_prompt_version: str = "v2",
) -> SequentialAgent:
    """
    Create PVMAP generation pipeline with tiered correction.

    The pipeline runs as a SequentialAgent:
    1. StatePreparationAgent - Prepares state for generator (attempt 0)
    2. [StatVarDiscoveryAgent] - MCP-based StatVar discovery (if MCP enabled)
    3. GeneratorWrapperAgent - Generates PVMAP (structured JSON)
    4. MetadataGenerationAgent - Auto-generates stat_var_processor config
    5. [MCPSpotCheckAgent] - Pre-validation via MCP (if MCP enabled)
    6. ValidationAgent - Validates; sets validation_passed flag
    7. [MCPErrorResolverAgent] - MCP error resolution (if MCP enabled)
    8. QualityEvaluationAgent - Evaluates quality (does NOT escalate)
    9. TieredCorrectionAgent - Runs Tier 1/2/3 correction if quality not acceptable

    Replaces the old LoopAgent-based retry loop with a deterministic
    sequential pipeline that tries programmatic fixes first, then LLM
    patch, then full regeneration.

    Args:
        model: Gemini model for generation (default: gemini-2.5-flash)
        max_retries: DEPRECATED -- tiered correction uses fixed 3 validation runs.
            Kept for backward compatibility.
        use_structured_output: Use output_schema for structured JSON (default: True)
        name: Agent name (default: PVMAPRetryLoop)
        enable_mcp: Enable MCP integration (default: False)
        mcp_url: MCP server URL (required if enable_mcp=True)
        min_attempts: Minimum attempts before allowing quality exit (optional)
        thinking_level: Thinking level for Gemini models (optional)
        feedback_prompt_version: Feedback prompt version ('v1' or 'v2')

    Returns:
        Configured SequentialAgent

    State Inputs (must be set before pipeline):
        - current_dataset: DatasetInfo - Dataset being processed

    State Outputs (after pipeline completes):
        - generation_success: bool - Whether generation succeeded
        - pvmap_path: str - Path to generated PVMAP
        - pvmap_csv: str - PVMAP CSV content
        - validation_data_rows: int - Rows in processed output
        - retry_count: int - Number of attempts made
        - exit_reason: str - "quality_met" | "stagnant" | "tiered_correction_complete" | "max_retries"
        - quality_metrics: dict - Final quality metrics
        - quality_metrics_history: List[dict] - All attempts' metrics
        - error: str - Error message if failed
    """
    if max_retries != 3:
        logger.warning(
            "max_retries=%d is deprecated -- tiered correction pipeline uses fixed 3 validation runs",
            max_retries,
        )

    # Get model from environment override if available
    model = os.getenv("PVMAP_GENERATOR_MODEL", model)

    # Create agents for initial attempt (Attempt 0)
    state_prep = StatePreparationAgent(name="StatePrep")

    generator = GeneratorWrapperAgent(
        name="Generator",
        use_structured_output=use_structured_output,
        model=model,
        enable_mcp=enable_mcp,
        mcp_url=mcp_url,
        thinking_level=thinking_level,
    )

    metadata_generator = MetadataGenerationAgent(name="MetadataGenerator")
    validator = ValidationAgent(name="Validator")
    quality_evaluator = QualityEvaluationAgent(
        name="QualityEvaluator",
        min_attempts=min_attempts,
        escalate_on_quality=False,  # Don't escalate in SequentialAgent
    )

    # Create Tier 2 patch agent
    from src.agents.pvmap_patch_agent import create_pvmap_patch_agent
    patch_agent = create_pvmap_patch_agent(model=model, thinking_level=thinking_level)

    # Create tiered correction (only runs if quality not acceptable after attempt 0)
    tiered = TieredCorrectionAgent(
        name="TieredCorrection",
        patch_agent=patch_agent,
        generator_wrapper=generator,
        metadata_agent=metadata_generator,
        validation_agent=validator,
        model=model,
        thinking_level=thinking_level,
        enable_mcp=enable_mcp,
        mcp_url=mcp_url,
        use_structured_output=use_structured_output,
        feedback_prompt_version=feedback_prompt_version,
    )

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
        logger.info("StatVarDiscoveryAgent added to pipeline (MCP enabled)")

    sub_agents.append(generator)
    sub_agents.append(metadata_generator)

    # Insert MCPSpotCheckAgent between metadata_generator and validator when MCP enabled
    if enable_mcp and mcp_url:
        from src.agents.mcp_spot_check_agent import MCPSpotCheckAgent
        spot_check = MCPSpotCheckAgent(name="MCPSpotCheck")
        sub_agents.append(spot_check)
        logger.info("MCPSpotCheckAgent added to pipeline (MCP enabled)")

    sub_agents.append(validator)

    # Insert MCPErrorResolverAgent when MCP enabled
    if enable_mcp and mcp_url:
        error_resolver = MCPErrorResolverAgent(name="MCPErrorResolver")
        sub_agents.append(error_resolver)
        logger.info("MCPErrorResolverAgent added to pipeline (MCP enabled)")

    sub_agents.extend([
        quality_evaluator,
        tiered,
    ])

    return SequentialAgent(name=name, sub_agents=sub_agents)


# ============================================================================
# Module exports
# ============================================================================

__all__ = [
    'create_pvmap_retry_loop',
    'TieredCorrectionAgent',
    'GeneratorWrapperAgent',
    'StatePreparationAgent',
    'ConditionalFeedbackAgent',
    'MCPErrorResolverAgent',
    'MaxRetriesCheckAgent',
]

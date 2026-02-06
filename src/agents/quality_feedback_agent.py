"""
Quality Feedback Agent for ADK pipeline retry loop.

This module provides:
1. LlmAgent for generating quality improvement feedback
2. ConditionalQualityFeedbackAgent wrapper that only runs when needed

Key ADK features used:
- LlmAgent for intelligent quality analysis
- BaseAgent wrapper for conditional execution
- output_key to store feedback in session state
- Instruction templating to read quality metrics from state
"""

import os
import sys
from pathlib import Path
from typing import AsyncGenerator

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import LlmAgent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from src.agents.template_utils import escape_pvmap_placeholders


# ============================================================================
# Quality Feedback Agent Instruction
# ============================================================================

QUALITY_FEEDBACK_INSTRUCTION = """You are analyzing a PVMAP that passed validation but has low quality metrics.

## Current Attempt
Attempt {attempt_number} of 4

## Quality Metrics
Mode: {quality_mode}
Score: {quality_score}%
{quality_metrics}

## Quality Issues / Diff Summary
{quality_diff_summary}

## Generated PVMAP CSV
```csv
{pvmap_csv}
```

## Original Sampled Data (Reference)
{sampled_data}

---

# ANALYSIS GUIDELINES

Your task: Analyze the quality issues and provide **specific, actionable feedback** for the next generation attempt.

## 1. Understand the Quality Gap

### If Ground Truth Mode (diff provided):
- Look at which PVMAP rows don't match the expected ground truth
- Identify key mismatches (wrong column mapped to wrong property)
- Find missing or extra rows
- Note any DCID format differences

### If Heuristic Mode (score breakdown provided):
- Low row coverage: Are there missing dimension mappings?
- Low property coverage: Are observationAbout/observationDate/value mapped?
- Low column coverage: Which data columns weren't mapped?
- Low format score: Are {Data}/{Number} placeholders used correctly?

## 2. Common Quality Issues to Fix

### Key Matching Problems
- Keys don't match exact column headers (case sensitivity)
- Missing Column:Value mappings for categorical dimensions
- Dimension values need individual PVMAP rows

### Property Mapping Issues
- observationAbout mapped to wrong column (should be place/geo column)
- observationDate mapped to wrong column (should be date/year column)
- value mapped to wrong column (should be numeric measurement column)

### StatVar Definition Issues
- Missing populationType, measuredProperty for raw data
- Using wrong DCIDs for properties
- Not using dcid: prefix where needed

## 3. Provide Specific Fixes

Be CONCRETE and SPECIFIC:

**Instead of:** "Improve column coverage"
**Say:** "Add mapping for 'County FIPS' column with observationAbout property pointing to dcid:geoId/[DATA]"

**Instead of:** "Fix the key"
**Say:** "Change key from 'YEAR' to 'Year' to match the exact case in the data"

## 4. Pattern Recognition

If you see systematic errors, note them:
- "All place mappings need geoId/ prefix"
- "All year columns should use observationDate, not variableMeasured"
- "This appears to be pre-formatted data - use passthrough mappings"

---

# OUTPUT FORMAT

Provide your analysis in this structure:

1. **Quality Gap Analysis**: What specific aspects are lowering the quality score

2. **High-Impact Fixes** (prioritized list of 3-5 specific changes):
   - Fix 1: [Specific change with exact values]
   - Fix 2: [Specific change with exact values]
   - Fix 3: [Specific change with exact values]

3. **Pattern Issues**: Any systematic problems affecting multiple rows

4. **Corrected Example**: Show 1-2 corrected PVMAP rows

Keep your response focused and actionable. The generator will read this feedback directly to improve the next attempt."""


def create_quality_feedback_agent(
    model: str = "gemini-2.5-flash",
    name: str = "QualityFeedbackAgent",
) -> LlmAgent:
    """
    Create quality feedback agent for generating improvement suggestions.

    This agent analyzes quality metrics and diff summaries to generate
    actionable feedback for the next generation attempt.

    Args:
        model: Gemini model to use (default: gemini-2.5-flash)
        name: Agent name (default: QualityFeedbackAgent)

    Returns:
        Configured LlmAgent for quality feedback

    State Inputs (read via instruction templating):
        - attempt_number: int - Current attempt number
        - quality_metrics: dict - Quality evaluation results
        - quality_diff_summary: str - Diff or heuristic issues
        - pvmap_csv: str - Generated PVMAP CSV
        - sampled_data: str - Original sampled data for reference

    State Outputs (written via output_key):
        - quality_feedback: str - Actionable feedback for next attempt
    """
    # Get model from environment override if available
    model = os.getenv("QUALITY_FEEDBACK_MODEL", model)

    return LlmAgent(
        name=name,
        model=model,
        instruction=QUALITY_FEEDBACK_INSTRUCTION,
        output_key="quality_feedback",  # Generator reads this on retry
    )


class ConditionalQualityFeedbackAgent(BaseAgent):
    """
    Conditional wrapper that only runs QualityFeedbackAgent when appropriate.

    This agent runs the quality feedback LlmAgent only when:
    - validation_passed = True (validation succeeded)
    - quality_acceptable = False (quality is below threshold)
    - quality_stagnant = False (not stagnating)

    Otherwise, it skips feedback generation.
    """

    # Declare feedback_agent as a Pydantic field (ADK agents use Pydantic)
    feedback_agent: LlmAgent

    def __init__(
        self,
        name: str = "ConditionalQualityFeedback",
        model: str = "gemini-2.5-flash"
    ):
        """
        Initialize ConditionalQualityFeedbackAgent.

        Args:
            name: Agent name
            model: Gemini model for the inner LlmAgent
        """
        feedback_agent = create_quality_feedback_agent(model=model)
        super().__init__(
            name=name,
            feedback_agent=feedback_agent,
            sub_agents=[feedback_agent]
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Conditionally run quality feedback agent.

        Only runs if validation passed, quality is low, and not stagnant.
        """
        validation_passed = ctx.session.state.get("validation_passed", False)
        quality_acceptable = ctx.session.state.get("quality_acceptable", False)
        quality_stagnant = ctx.session.state.get("quality_stagnant", False)

        # Determine if we should run
        should_run = validation_passed and not quality_acceptable and not quality_stagnant

        if should_run:
            # Prepare state variables for instruction templating
            self._prepare_feedback_state(ctx)

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Quality low - generating improvement feedback...")
                ])
            )

            # Run the inner feedback agent
            async for event in self.feedback_agent.run_async(ctx):
                yield event

            # Log feedback preview
            quality_feedback = ctx.session.state.get("quality_feedback", "")
            if quality_feedback:
                preview = quality_feedback[:200] + "..." if len(quality_feedback) > 200 else quality_feedback
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Quality feedback generated: {preview}")
                    ]),
                    actions=EventActions(escalate=False)  # Explicit: continue loop
                )
        else:
            # Skip feedback - explain why
            if not validation_passed:
                reason = "validation failed"
            elif quality_acceptable:
                reason = "quality acceptable"
            elif quality_stagnant:
                reason = "quality stagnant"
            else:
                reason = "not applicable"

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Skipping quality feedback ({reason})")
                ]),
                actions=EventActions(escalate=False)  # Explicit: continue loop
            )

    def _prepare_feedback_state(self, ctx: InvocationContext) -> None:
        """
        Prepare state variables for feedback instruction templating.

        The LlmAgent instruction uses variables like {quality_mode}, {quality_score}
        that need to be extracted from the nested quality_metrics dict.

        IMPORTANT: Also escapes PVMAP placeholders ({Data}, {Number}) to prevent
        ADK templating conflicts. These get converted to [DATA], [NUMBER].
        """
        quality_metrics = ctx.session.state.get("quality_metrics", {})

        # Extract mode
        mode = quality_metrics.get("mode", "unknown")
        ctx.session.state["quality_mode"] = mode

        # Extract score based on mode
        if mode == "ground_truth":
            score = quality_metrics.get("pv_accuracy", 0)
        else:
            score = quality_metrics.get("heuristic_score", 0)
        ctx.session.state["quality_score"] = score

        # Format quality_metrics for display
        metrics_str = self._format_metrics(quality_metrics)
        ctx.session.state["quality_metrics"] = metrics_str

        # Ensure attempt_number has +1 for display
        attempt = ctx.session.state.get("attempt_number", 0)
        ctx.session.state["attempt_number"] = attempt + 1  # 1-indexed for display

        # =====================================================================
        # CRITICAL: Escape PVMAP placeholders to prevent ADK templating errors
        # {Data} and {Number} in pvmap_csv/quality_diff_summary cause KeyError
        # =====================================================================
        pvmap_csv = ctx.session.state.get("pvmap_csv", "")
        if pvmap_csv:
            ctx.session.state["pvmap_csv"] = escape_pvmap_placeholders(pvmap_csv)

        quality_diff_summary = ctx.session.state.get("quality_diff_summary", "")
        if quality_diff_summary:
            ctx.session.state["quality_diff_summary"] = escape_pvmap_placeholders(quality_diff_summary)

        sampled_data = ctx.session.state.get("sampled_data", "")
        if sampled_data:
            ctx.session.state["sampled_data"] = escape_pvmap_placeholders(sampled_data)

    def _format_metrics(self, metrics: dict) -> str:
        """Format quality metrics dict as readable string."""
        lines = []

        if metrics.get("mode") == "ground_truth":
            lines.append(f"PV Accuracy: {metrics.get('pv_accuracy', 0):.1f}%")
            lines.append(f"Node Accuracy: {metrics.get('node_accuracy', 0):.1f}%")
            counters = metrics.get("counters", {})
            if counters:
                lines.append(f"Nodes Matched: {counters.get('nodes-matched', 0)}/{counters.get('nodes-ground-truth', 0)}")
                lines.append(f"PVs Matched: {counters.get('PVs-matched', 0)}")
        else:
            lines.append(f"Heuristic Score: {metrics.get('heuristic_score', 0):.1f}/100")
            breakdown = metrics.get("heuristic_breakdown", {})
            if breakdown:
                lines.append(f"  - Row Coverage: {breakdown.get('row_coverage', 0):.1f}/25")
                lines.append(f"  - Property Coverage: {breakdown.get('prop_coverage', 0):.1f}/25")
                lines.append(f"  - Column Coverage: {breakdown.get('column_coverage', 0):.1f}/25")
                lines.append(f"  - Format Score: {breakdown.get('format_score', 0):.1f}/25")

        if "improvement_from_previous" in metrics:
            lines.append(f"Improvement from previous: {metrics['improvement_from_previous']:.1f}%")

        return "\n".join(lines)


# ============================================================================
# Module exports
# ============================================================================

__all__ = [
    'create_quality_feedback_agent',
    'ConditionalQualityFeedbackAgent',
    'QUALITY_FEEDBACK_INSTRUCTION',
]

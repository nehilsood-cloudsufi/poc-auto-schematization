"""
Unified Feedback Agent for ADK pipeline retry loop.

This LlmAgent analyzes both validation errors AND quality issues, generating
actionable feedback for the next PVMAP generation attempt.

Replaces the previous split between FeedbackAgent (error path) and
QualityFeedbackAgent (quality path) with a single agent that handles both.

Key ADK features used:
- LlmAgent for intelligent error/quality analysis
- output_key to store feedback in session state
- Instruction templating to read validation_error, quality metrics, and
  counter summary from state
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

from google.adk.agents import LlmAgent

from src.agents.prompt_loader import load_prompt
from src.agents.retry_config import create_resilient_model
from src.agents.template_utils import build_thinking_config


# ============================================================================
# Unified Feedback Agent Instruction
# ============================================================================

FEEDBACK_AGENT_INSTRUCTION = load_prompt("feedback_agent.txt")


def create_feedback_agent(
    model: str = "gemini-3-pro-preview",
    name: str = "FeedbackAgent",
    thinking_level: Optional[str] = None,
) -> LlmAgent:
    """
    Create unified feedback agent for error/quality analysis between retry attempts.

    This agent analyzes both validation failures and quality issues, generating
    actionable feedback that gets injected into the next generation attempt.

    Args:
        model: Gemini model to use (default: gemini-2.5-flash)
        name: Agent name (default: FeedbackAgent)

    Returns:
        Configured LlmAgent for error/quality analysis

    State Inputs (read via instruction templating):
        - feedback_mode: str - "VALIDATION FAILED", "QUALITY LOW", or "PV ACCURACY LOW"
        - validation_error: str - Error message from validation
        - pvmap_csv: str - Generated PVMAP CSV that failed
        - sampled_data: str - Original sampled data for reference
        - structure_warnings: str - Structure validation warnings
        - mcp_resolved_context: str - MCP error resolution context
        - quality_score: float - Heuristic quality score
        - quality_metrics: str - Formatted quality metrics
        - quality_diff_summary: str - Quality issues summary
        - gt_score_section: str - Ground truth accuracy section
        - validation_counter_summary: str - Counter summary from stat_var_processor
        - schema_category: str - Selected schema category (Health, Economy, etc.)
        - schema_vocab_content: str - Compressed schema vocabulary for domain
        - skeleton_summary: str - Column classification from sampling analysis
        - validation_statvar_analysis: str - StatVar analysis from MCF output

    State Outputs (written via output_key):
        - error_feedback: str - Actionable feedback for next attempt
    """
    # Get model from environment override if available
    model = os.getenv("FEEDBACK_AGENT_MODEL", model)
    logger.info("Creating FeedbackAgent: model=%s", model)

    from google.genai import types

    kwargs = dict(
        name=name,
        model=create_resilient_model(model),
        instruction=FEEDBACK_AGENT_INSTRUCTION,
        output_key="error_feedback",  # Generator reads this on retry
        include_contents="none",  # Prevent conversation history accumulation across loop iterations
        # Schema.org tools removed: feedback agent only needs to analyze errors
        # and produce concise guidance. The Generator has these tools for PVMAP creation.
    )

    thinking_config = build_thinking_config(thinking_level, model=model)
    gen_config_kwargs = {"max_output_tokens": 1500}
    if thinking_config:
        gen_config_kwargs["thinking_config"] = thinking_config
    kwargs["generate_content_config"] = types.GenerateContentConfig(**gen_config_kwargs)

    return LlmAgent(**kwargs)


# ============================================================================
# Module exports
# ============================================================================

__all__ = [
    'create_feedback_agent',
    'FEEDBACK_AGENT_INSTRUCTION',
]

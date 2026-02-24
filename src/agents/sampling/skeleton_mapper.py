"""Relational skeleton mapping LLM agent.

Single-shot LlmAgent with output_schema=RelationalSkeleton.
No tools — pure structured output from profile + semantic analysis.
"""

import os

from google.adk.agents import LlmAgent

from src.agents.prompt_loader import load_prompt
from src.agents.retry_config import create_resilient_model
from src.agents.sampling.schemas import RelationalSkeleton

SKELETON_MAPPING_INSTRUCTION = load_prompt("skeleton_mapping.txt")


def create_skeleton_mapper(model: str = None) -> LlmAgent:
    """Create a SkeletonMapper LlmAgent with structured output.

    The agent receives {dataset_profile} and {semantic_analysis} state
    variables and outputs a RelationalSkeleton Pydantic model.

    Args:
        model: Gemini model name. Defaults to SAMPLING_AGENT_MODEL env var
               or "gemini-3-pro-preview".

    Returns:
        Configured LlmAgent with output_schema=RelationalSkeleton.
    """
    if model is None:
        model = os.getenv("SAMPLING_AGENT_MODEL", "gemini-3-pro-preview")

    return LlmAgent(
        name="SkeletonMapper",
        model=create_resilient_model(model),
        instruction=SKELETON_MAPPING_INSTRUCTION,
        output_schema=RelationalSkeleton,
        output_key="relational_skeleton",
        include_contents="none",
    )

"""Semantic analysis LLM agent for column classification.

Single-shot LlmAgent with output_schema=SemanticAnalysis.
No tools — pure structured output from dataset profile evidence.
"""

import os

from google.adk.agents import LlmAgent

from src.agents.prompt_loader import load_prompt
from src.agents.retry_config import create_resilient_model
from src.agents.sampling.schemas import SemanticAnalysis

SEMANTIC_ANALYSIS_INSTRUCTION = load_prompt("semantic_analysis.txt")


def create_semantic_analyzer(model: str = None) -> LlmAgent:
    """Create a SemanticAnalyzer LlmAgent with structured output.

    The agent receives a DatasetProfile JSON via the {dataset_profile}
    state variable and outputs a SemanticAnalysis Pydantic model.

    Args:
        model: Gemini model name. Defaults to SAMPLING_AGENT_MODEL env var
               or "gemini-3.1-pro-preview".

    Returns:
        Configured LlmAgent with output_schema=SemanticAnalysis.
    """
    if model is None:
        model = os.getenv("SAMPLING_AGENT_MODEL", "gemini-3.1-pro-preview")

    return LlmAgent(
        name="SemanticAnalyzer",
        model=create_resilient_model(model),
        instruction=SEMANTIC_ANALYSIS_INSTRUCTION,
        output_schema=SemanticAnalysis,
        output_key="semantic_analysis",
        include_contents="none",
    )

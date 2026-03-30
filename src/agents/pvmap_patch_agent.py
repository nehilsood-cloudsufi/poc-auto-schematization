"""Lightweight PVMAP patch agent for Tier 2 correction.

Receives a partially-working PVMAP and specific error diagnostics,
then fixes ONLY the failing rows without touching working ones.
Much lighter than the full PVMAPGenerationAgent (~2K prompt vs ~15K).
"""
import logging
import os
from typing import Optional

from google.adk.agents import LlmAgent
from google.genai import types

from src.agents.prompt_loader import load_prompt
from src.agents.retry_config import create_resilient_model
from src.agents.template_utils import build_thinking_config

logger = logging.getLogger(__name__)


def create_pvmap_patch_agent(
    model: str = "gemini-3.1-pro-preview",
    name: str = "PVMAPPatchAgent",
    thinking_level: Optional[str] = None,
) -> LlmAgent:
    """Create lightweight PVMAP patch agent for Tier 2 correction.

    State Inputs (read via instruction templating):
        - pvmap_csv: str - Current PVMAP CSV content
        - validation_counter_summary: str - Enriched validation diagnostics
        - key_match_report: str - Column header matching analysis

    State Outputs (written via output_key):
        - pvmap_csv: str - Corrected PVMAP CSV content
    """
    model = os.getenv("PATCH_AGENT_MODEL", model)
    logger.info("Creating PVMAPPatchAgent: model=%s", model)

    instruction = load_prompt("pvmap_patch_agent.txt")

    kwargs = dict(
        name=name,
        model=create_resilient_model(model),
        instruction=instruction,
        output_key="pvmap_csv",
        include_contents="none",
    )

    thinking_config = build_thinking_config(thinking_level, model=model)
    gen_config_kwargs = {"max_output_tokens": 4000}
    if thinking_config:
        gen_config_kwargs["thinking_config"] = thinking_config
    kwargs["generate_content_config"] = types.GenerateContentConfig(**gen_config_kwargs)

    return LlmAgent(**kwargs)


__all__ = ["create_pvmap_patch_agent"]

"""
PVMAP Generator Agent using ADK LlmAgent with output_schema.

This agent uses ADK's structured output feature to guarantee valid JSON
responses that can be deterministically converted to CSV.

The prompt content comes from src/resources/prompts/improved_pvmap_prompt.txt,
which is populated by StatePreparationAgent and stored in session state as
'populated_pvmap_prompt'. This agent's instruction simply references that
state variable.

Key ADK features used:
- output_schema: Pydantic model for structured output
- output_key: Stores output in session state automatically
- Instruction templating: {populated_pvmap_prompt} resolved from session state
"""

import os
from pathlib import Path
from typing import Optional

from google.adk.agents import LlmAgent

from src.agents.pvmap_generation.schemas import PVMAPOutput
from src.agents.template_utils import build_thinking_config
from src.tools.schemaorg_tools import (
    lookup_schemaorg_type,
    lookup_schemaorg_property,
    search_schemaorg_vocabulary,
    validate_pvmap_property,
    get_schemaorg_type_hierarchy,
)


# ============================================================================
# Generator Instruction
# ============================================================================
# The full prompt is loaded from improved_pvmap_prompt.txt by
# StatePreparationAgent and stored as 'populated_pvmap_prompt' in session
# state. ADK resolves {populated_pvmap_prompt} at runtime.
PVMAP_GENERATOR_INSTRUCTION = "{populated_pvmap_prompt}"


def create_pvmap_generator(
    model: str = "gemini-2.5-flash",
    name: str = "PVMAPGenerator",
    enable_mcp: bool = False,
    mcp_url: Optional[str] = None,
    thinking_level: Optional[str] = None,
) -> LlmAgent:
    """
    Create PVMAP generator agent with structured output.

    This agent uses ADK's output_schema feature to guarantee structured JSON
    output that matches the PVMAPOutput Pydantic model.

    When MCP is enabled, the generator gets direct access to Data Commons
    MCP tools (search_indicators, get_observations) for live verification.

    Args:
        model: Gemini model to use (default: gemini-2.5-flash)
        name: Agent name (default: PVMAPGenerator)
        enable_mcp: Enable MCP tools on the generator (default: False)
        mcp_url: MCP server URL (required if enable_mcp=True)

    Returns:
        Configured LlmAgent with output_schema

    State Inputs (read from session.state via instruction templating):
        - schema_examples: str - Schema example content
        - sampled_data: str - Sampled CSV data
        - metadata: str - Metadata configuration
        - skeleton_summary: str (optional) - Data context from SamplingAgent
        - statvar_summary: str (optional) - Discovered StatVars from MCP
        - mcp_tools_instruction: str (optional) - MCP tool usage guidance
        - error_feedback: str (optional) - Feedback from validation failure or quality issues

    State Outputs (written via output_key):
        - pvmap_output: dict - Structured PVMAP output (JSON dict matching PVMAPOutput)
    """
    # Get model from environment override if available
    model = os.getenv("PVMAP_GENERATOR_MODEL", model)

    # Build tools list
    tools = []

    # Schema.org vocabulary lookup tools (always available)
    tools.extend([
        lookup_schemaorg_type,
        lookup_schemaorg_property,
        search_schemaorg_vocabulary,
        validate_pvmap_property,
        get_schemaorg_type_hierarchy,
    ])

    # Local DC tools (always available when MCP enabled, no server required)
    if enable_mcp:
        from src.tools.dc_tools import (
            resolve_place_names, validate_statvar_observation, get_entity_type,
        )
        tools.extend([resolve_place_names, validate_statvar_observation, get_entity_type])

    if enable_mcp and mcp_url:
        from src.data_commons.api.mcp_toolset_factory import create_dc_mcp_toolset
        mcp_toolset = create_dc_mcp_toolset(mcp_url=mcp_url)
        tools.append(mcp_toolset)

    kwargs = dict(
        name=name,
        model=model,
        instruction=PVMAP_GENERATOR_INSTRUCTION,
        output_schema=PVMAPOutput,
        output_key="pvmap_output",
        include_contents="none",  # Prevent conversation history accumulation across loop iterations
    )

    if tools:
        kwargs["tools"] = tools

    thinking_config = build_thinking_config(thinking_level, model=model)
    if thinking_config:
        from google.genai import types
        kwargs["generate_content_config"] = types.GenerateContentConfig(
            thinking_config=thinking_config,
        )

    return LlmAgent(**kwargs)


def create_pvmap_generator_without_schema(
    model: str = "gemini-2.5-flash",
    name: str = "PVMAPGenerator",
    thinking_level: Optional[str] = None,
) -> LlmAgent:
    """
    Create PVMAP generator agent WITHOUT output_schema for fallback.

    Some models may not support structured output. This variant uses
    the same instruction but allows free-form output that must be
    parsed manually.

    Args:
        model: Gemini model to use
        name: Agent name

    Returns:
        Configured LlmAgent without output_schema
    """
    model = os.getenv("PVMAP_GENERATOR_MODEL", model)

    kwargs = dict(
        name=name,
        model=model,
        instruction=PVMAP_GENERATOR_INSTRUCTION,
        output_key="pvmap_raw_output",  # Store raw output for parsing
        include_contents="none",  # Prevent conversation history accumulation across loop iterations
    )

    thinking_config = build_thinking_config(thinking_level, model=model)
    if thinking_config:
        from google.genai import types
        kwargs["generate_content_config"] = types.GenerateContentConfig(
            thinking_config=thinking_config,
        )

    return LlmAgent(**kwargs)


# ============================================================================
# Module exports
# ============================================================================

__all__ = [
    'create_pvmap_generator',
    'create_pvmap_generator_without_schema',
    'PVMAP_GENERATOR_INSTRUCTION',
]

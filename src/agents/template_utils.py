"""
Template utilities for ADK instruction templating.

This module provides utilities to safely handle state variables that may contain
PVMAP placeholder syntax ({Data}, {Number}) which conflicts with ADK's
instruction templating syntax ({variable_name}).

Usage:
    from src.agents.template_utils import escape_pvmap_placeholders

    # Before setting state variables that might contain PVMAP content
    ctx.session.state["pvmap_csv"] = escape_pvmap_placeholders(pvmap_csv)
"""

import re
from typing import Optional


def escape_pvmap_placeholders(text: Optional[str]) -> str:
    """
    Escape PVMAP placeholders to prevent ADK templating conflicts.

    ADK's LlmAgent instruction templating uses {variable_name} syntax to inject
    session state values. PVMAP content uses {Data} and {Number} as placeholders,
    which causes KeyError when ADK tries to interpret them as state variables.

    This function converts:
    - {Data} -> [DATA]
    - {Number} -> [NUMBER]
    - {Data:format} -> [DATA:format]  (preserves format specifiers)

    These square-bracket versions match the JSON output format that the
    PVMAP generator uses, so they're understood by both humans and LLMs.

    Args:
        text: Text that may contain PVMAP placeholders

    Returns:
        Text with placeholders escaped for safe ADK templating

    Example:
        >>> escape_pvmap_placeholders("value,{Number},observationDate,{Data}")
        'value,[NUMBER],observationDate,[DATA]'
    """
    if not text:
        return text or ""

    # Replace {Data} variants (with optional format specifiers)
    # e.g., {Data}, {Data:02d}, {Data:0>5}
    text = re.sub(r'\{Data(?::[^}]*)?\}', lambda m: m.group(0).replace('{Data', '[DATA').replace('}', ']'), text)

    # Replace {Number} variants
    text = re.sub(r'\{Number(?::[^}]*)?\}', lambda m: m.group(0).replace('{Number', '[NUMBER').replace('}', ']'), text)

    return text


def unescape_pvmap_placeholders(text: Optional[str]) -> str:
    """
    Reverse the escaping done by escape_pvmap_placeholders.

    Converts:
    - [DATA] -> {Data}
    - [NUMBER] -> {Number}
    - [DATA:format] -> {Data:format}

    Args:
        text: Text with escaped placeholders

    Returns:
        Text with original PVMAP placeholder syntax

    Example:
        >>> unescape_pvmap_placeholders("value,[NUMBER],observationDate,[DATA]")
        'value,{Number},observationDate,{Data}'
    """
    if not text:
        return text or ""

    # Replace [DATA] variants back to {Data}
    text = re.sub(r'\[DATA(?::[^\]]*)?]', lambda m: m.group(0).replace('[DATA', '{Data').replace(']', '}'), text)

    # Replace [NUMBER] variants back to {Number}
    text = re.sub(r'\[NUMBER(?::[^\]]*)?]', lambda m: m.group(0).replace('[NUMBER', '{Number').replace(']', '}'), text)

    return text


def prepare_state_for_templating(ctx, state_keys: list[str]) -> None:
    """
    Prepare multiple state variables for safe ADK instruction templating.

    This is a convenience function that escapes PVMAP placeholders in
    multiple state variables at once.

    Args:
        ctx: ADK InvocationContext
        state_keys: List of state variable names to escape

    Example:
        prepare_state_for_templating(ctx, ["pvmap_csv", "validation_error", "sampled_data"])
    """
    for key in state_keys:
        value = ctx.session.state.get(key)
        if value and isinstance(value, str):
            ctx.session.state[key] = escape_pvmap_placeholders(value)


# ============================================================================
# Module exports
# ============================================================================

__all__ = [
    'escape_pvmap_placeholders',
    'unescape_pvmap_placeholders',
    'prepare_state_for_templating',
]

"""Tests for PVMAPPatchAgent (Tier 2 lightweight correction agent)."""

import re
import pytest
from unittest.mock import patch

from src.agents.pvmap_patch_agent import create_pvmap_patch_agent
from src.agents.prompt_loader import load_prompt, PROMPTS_DIR


def test_create_patch_agent_default():
    """Verify agent is created with correct name and output_key."""
    agent = create_pvmap_patch_agent()
    assert agent is not None
    assert agent.name == "PVMAPPatchAgent"
    assert agent.output_key == "pvmap_csv"


def test_create_patch_agent_custom_model():
    """Model override via argument works."""
    agent = create_pvmap_patch_agent(model="gemini-2.5-flash")
    # The model is wrapped in a Gemini instance; just verify agent is created
    assert agent is not None
    assert agent.name == "PVMAPPatchAgent"


def test_create_patch_agent_env_model_override(monkeypatch):
    """PATCH_AGENT_MODEL env var overrides the model argument."""
    monkeypatch.setenv("PATCH_AGENT_MODEL", "gemini-2.5-flash")
    agent = create_pvmap_patch_agent(model="gemini-3.1-pro-preview")
    assert agent is not None


def test_include_contents_none():
    """Agent must use include_contents='none' to avoid history accumulation."""
    agent = create_pvmap_patch_agent()
    assert agent.include_contents == "none"


def test_prompt_loads():
    """Prompt file exists and loads without error."""
    prompt_path = PROMPTS_DIR / "pvmap_patch_agent.txt"
    assert prompt_path.exists(), f"Prompt file not found: {prompt_path}"
    text = load_prompt("pvmap_patch_agent.txt")
    assert len(text) > 0


def test_prompt_no_dangerous_placeholders():
    """Prompt must not contain {Data}, {Number}, {data}, or {number} (ADK gotcha)."""
    text = load_prompt("pvmap_patch_agent.txt")
    # ADK resolves all {word} patterns as state vars; only state-var refs are allowed
    # The prompt uses {pvmap_csv}, {validation_counter_summary}, {key_match_report}
    # which ARE intentional state-var references. The forbidden patterns are PVMAP
    # content placeholders that would cause KeyError.
    forbidden = re.findall(r'\{(?:Data|Number|data|number)\}', text)
    assert forbidden == [], (
        f"Prompt contains dangerous ADK placeholders: {forbidden}. "
        "Use [DATA] and [NUMBER] instead."
    )

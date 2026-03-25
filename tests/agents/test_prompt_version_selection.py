import pytest
from pathlib import Path
import re
import inspect


def test_v2_template_path():
    """v2 template file exists."""
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    v2_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "improved_pvmap_prompt_v2.txt"
    assert v2_path.exists()


def test_v3_template_path():
    """v3 template file exists."""
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    v3_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "improved_pvmap_prompt_v3.txt"
    assert v3_path.exists()


def test_v3_has_all_placeholders():
    """v3 prompt has same placeholders as v2."""
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    prompts_dir = PROJECT_ROOT / "src" / "resources" / "prompts"
    v2_text = (prompts_dir / "improved_pvmap_prompt_v2.txt").read_text()
    v3_text = (prompts_dir / "improved_pvmap_prompt_v3.txt").read_text()
    v2_ph = set(re.findall(r'\{\{[A-Z_]+\}\}', v2_text))
    v3_ph = set(re.findall(r'\{\{[A-Z_]+\}\}', v3_text))
    assert v2_ph == v3_ph


def test_v3_has_skeleton_heading():
    """v3 skeleton heading matches regex."""
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    v3_text = (PROJECT_ROOT / "src" / "resources" / "prompts" / "improved_pvmap_prompt_v3.txt").read_text()
    assert "## PVMAP Skeleton (pre-filled baseline)" in v3_text


def test_v3_has_skeleton_sentinel():
    """v3 has skeleton sentinel text for regex matching."""
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    v3_text = (PROJECT_ROOT / "src" / "resources" / "prompts" / "improved_pvmap_prompt_v3.txt").read_text()
    assert "Missing any column from this skeleton causes data corruption. Treat this as a mandatory checklist." in v3_text


def test_v3_shorter_than_v2():
    """v3 is significantly shorter than v2."""
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    prompts_dir = PROJECT_ROOT / "src" / "resources" / "prompts"
    v2_lines = len((prompts_dir / "improved_pvmap_prompt_v2.txt").read_text().splitlines())
    v3_lines = len((prompts_dir / "improved_pvmap_prompt_v3.txt").read_text().splitlines())
    assert v3_lines < v2_lines * 0.7


def test_run_dataset_pipeline_accepts_prompt_version():
    """run_dataset_pipeline accepts prompt_version parameter."""
    from src.run_pipeline import run_dataset_pipeline
    sig = inspect.signature(run_dataset_pipeline)
    assert "prompt_version" in sig.parameters
    assert sig.parameters["prompt_version"].default == "v2"

"""Utility for loading prompt templates from src/resources/prompts/."""

import json
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "resources" / "prompts"


def load_prompt(filename: str) -> str:
    """Load a prompt .txt file from the prompts directory."""
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8").strip()


def load_prompt_json(filename: str) -> dict:
    """Load a prompt .json file from the prompts directory."""
    path = PROMPTS_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))

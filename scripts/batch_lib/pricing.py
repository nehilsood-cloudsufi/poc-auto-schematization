"""Pricing table loader + per-call cost computation.

Pricing JSON format:
{
  "models": {
    "<model_id>": {
      "input_per_mtok":    1.25,
      "output_per_mtok":  10.0,
      "thoughts_per_mtok":10.0,
      "is_estimate":      true
    }, ...
  },
  "fallback": { ... same shape ... }
}
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional


@dataclass
class PricingTable:
    models: Dict[str, Dict[str, float]] = field(default_factory=dict)
    fallback: Dict[str, float] = field(default_factory=dict)
    raw: Dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "PricingTable":
        raw = json.loads(Path(path).read_text())
        return cls(
            models=raw.get("models", {}),
            fallback=raw.get("fallback", {}),
            raw=raw,
        )


def compute_cost(
    prompt_tokens: Optional[int],
    response_tokens: Optional[int],
    thoughts_tokens: Optional[int],
    model: str,
    pricing: PricingTable,
) -> Dict[str, object]:
    p = pricing.models.get(model)
    model_used = model
    if not p:
        p = pricing.fallback
        model_used = "fallback"
    pt = prompt_tokens or 0
    rt = response_tokens or 0
    tt = thoughts_tokens or 0
    cost = (
        pt * p.get("input_per_mtok", 0.0) / 1_000_000
        + rt * p.get("output_per_mtok", 0.0) / 1_000_000
        + tt * p.get("thoughts_per_mtok", 0.0) / 1_000_000
    )
    return {
        "cost_usd": round(cost, 6),
        "model_used_for_pricing": model_used,
        "is_estimate": bool(p.get("is_estimate", False)),
    }

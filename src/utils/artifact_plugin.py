"""LLM telemetry plugin.

Captures every LLM call made by any agent and:
  1. Appends one JSON line per call to ``<output_dir>/<dataset>/llm_calls.jsonl``.
  2. Preserves backward-compat behavior: for Generator/PVMAPGenerator calls,
     stashes a ``pvmap_llm_result`` dict in session state so
     ``ValidationAgent.save_attempt_response()`` still works unchanged.

Class is still exported as ``ArtifactLoggingPlugin`` for backward compatibility.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from google.adk.plugins import BasePlugin
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

logger = logging.getLogger(__name__)

# Agent names that also get the legacy per-attempt state stash
_GENERATOR_AGENT_NAMES = ("Generator", "PVMAPGenerator")


class ArtifactLoggingPlugin(BasePlugin):
    """Per-agent LLM telemetry: JSONL sidecar + Generator state stash."""

    def __init__(self, output_dir: Path, dataset_name: str):
        super().__init__(name="llm_telemetry")
        self.output_dir = Path(output_dir)
        self.dataset_name = dataset_name
        # Per-(agent, invocation) call state keyed by an id so nested/concurrent
        # agent calls don't collide. The id is placed on the callback_context.
        self._pending: dict[str, dict] = {}
        self._jsonl_path = self.output_dir / dataset_name / "llm_calls.jsonl"
        self._jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    def _pending_key(self, ctx: CallbackContext) -> str:
        # ADK passes fresh CallbackContext instances to before/after callbacks,
        # so id(ctx) is unstable. Agent names are unique at any moment within
        # a serial pipeline; a single agent never has more than one in-flight
        # LLM call at a time in our current pipeline.
        return ctx.agent_name

    async def before_model_callback(
        self, *, callback_context: CallbackContext, llm_request: LlmRequest,
    ) -> Optional[LlmResponse]:
        req_model = llm_request.model if llm_request.model else None
        cfg = llm_request.config
        temperature = getattr(cfg, "temperature", None) if cfg else None
        max_out = getattr(cfg, "max_output_tokens", None) if cfg else None

        # Rough prompt size proxy: length of the serialized request contents.
        prompt_bytes = 0
        try:
            contents = getattr(llm_request, "contents", None) or []
            for c in contents:
                for part in getattr(c, "parts", []) or []:
                    t = getattr(part, "text", None)
                    if t:
                        prompt_bytes += len(t)
        except Exception:
            prompt_bytes = 0

        self._pending[self._pending_key(callback_context)] = {
            "start_wall": time.time(),
            "model": req_model,
            "temperature": temperature,
            "max_output_tokens": max_out,
            "prompt_bytes": prompt_bytes,
        }
        return None

    async def after_model_callback(
        self, *, callback_context: CallbackContext, llm_response: LlmResponse,
    ) -> Optional[LlmResponse]:
        pending = self._pending.pop(self._pending_key(callback_context), None)
        end_wall = time.time()
        start_wall = pending["start_wall"] if pending else end_wall
        duration_ms = round((end_wall - start_wall) * 1000)

        # Extract response text + thinking parts
        response_text = ""
        thinking_parts: list[str] = []
        if llm_response.content and llm_response.content.parts:
            for part in llm_response.content.parts:
                if getattr(part, "thought", False) and getattr(part, "text", None):
                    thinking_parts.append(part.text)
                elif getattr(part, "text", None):
                    response_text += part.text

        # Token extraction
        prompt_tokens = response_tokens = total_tokens = thoughts_tokens = None
        if llm_response.usage_metadata:
            u = llm_response.usage_metadata
            prompt_tokens = getattr(u, "prompt_token_count", None)
            response_tokens = getattr(u, "candidates_token_count", None)
            total_tokens = getattr(u, "total_token_count", None)
            thoughts_tokens = getattr(u, "thoughts_token_count", None)

        model = (
            llm_response.model_version
            or (pending["model"] if pending else None)
            or "unknown"
        )

        rec = {
            "call_id": uuid.uuid4().hex,
            "timestamp": datetime.fromtimestamp(end_wall).isoformat(),
            "agent": callback_context.agent_name,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "thoughts_tokens": thoughts_tokens,
            "response_tokens": response_tokens,
            "total_tokens": total_tokens,
            "duration_ms": duration_ms,
            "temperature": pending.get("temperature") if pending else None,
            "max_output_tokens": pending.get("max_output_tokens") if pending else None,
            "prompt_bytes": pending.get("prompt_bytes") if pending else None,
            "response_preview": response_text[:200],
        }
        # JSONL append (open in 'a' so concurrent writes from different threads
        # are append-safe on POSIX for small records).
        with open(self._jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

        # Legacy Generator-specific state stash
        if callback_context.agent_name in _GENERATOR_AGENT_NAMES:
            callback_context.state["pvmap_llm_result"] = {
                "model": model,
                "temperature": rec["temperature"],
                "max_tokens": rec["max_output_tokens"],
                "start_time": datetime.fromtimestamp(start_wall).isoformat(),
                "end_time": datetime.fromtimestamp(end_wall).isoformat(),
                "duration_ms": duration_ms,
                "prompt_tokens": prompt_tokens,
                "response_tokens": response_tokens,
                "total_tokens": total_tokens,
                "thoughts_tokens": thoughts_tokens,
                "text": response_text,
                "thinking_content": thinking_parts if thinking_parts else None,
            }

        logger.debug(
            "LLMTelemetry: %s model=%s tokens=%s duration=%dms",
            callback_context.agent_name, model, total_tokens, duration_ms,
        )
        return None

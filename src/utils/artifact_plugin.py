"""Custom plugin for saving agent artifacts."""
from google.adk.plugins import BasePlugin
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types as genai_types
from pathlib import Path
from typing import Optional
from datetime import datetime
import time
import json
import logging

logger = logging.getLogger(__name__)

# Agent names used by the PVMAP generator
_GENERATOR_AGENT_NAMES = ("Generator", "PVMAPGenerator")


class ArtifactLoggingPlugin(BasePlugin):
    """
    Plugin to capture LLM metadata from PVMAP generation calls.

    Captures model name, token usage, timing, and thinking content,
    then stores it in session state as ``pvmap_llm_result`` so that
    ``ValidationAgent.save_attempt_response()`` can write rich artifact files.
    """

    def __init__(self, output_dir: Path, dataset_name: str):
        super().__init__(name="artifact_logger")
        self.output_dir = output_dir
        self.dataset_name = dataset_name

        # Timing state for before/after callback pair
        self._model_call_start: Optional[float] = None
        self._request_config: dict = {}

    async def before_model_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_request: LlmRequest,
    ) -> Optional[LlmResponse]:
        """Capture timing and request config before model call."""
        if callback_context.agent_name not in _GENERATOR_AGENT_NAMES:
            return None

        self._model_call_start = time.time()

        # Extract request config
        self._request_config = {}
        if llm_request.config:
            self._request_config['temperature'] = getattr(
                llm_request.config, 'temperature', None
            )
            self._request_config['max_output_tokens'] = getattr(
                llm_request.config, 'max_output_tokens', None
            )

            # Enable thinking output so the model returns thought parts
            if not llm_request.config.thinking_config:
                llm_request.config.thinking_config = genai_types.ThinkingConfig(
                    include_thoughts=True
                )

        if llm_request.model:
            self._request_config['model'] = llm_request.model

        return None

    async def after_model_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_response: LlmResponse,
    ) -> Optional[LlmResponse]:
        """Extract LLM metadata and store as pvmap_llm_result in session state."""
        if callback_context.agent_name not in _GENERATOR_AGENT_NAMES:
            return None

        # --- Timing ---
        end_time = time.time()
        start_time = self._model_call_start or end_time
        duration_ms = round((end_time - start_time) * 1000)

        # --- Extract response text and thinking content ---
        response_text = ""
        thinking_parts: list[str] = []

        if llm_response.content and llm_response.content.parts:
            for part in llm_response.content.parts:
                if getattr(part, 'thought', False):
                    # This is a thinking/reasoning part
                    if part.text:
                        thinking_parts.append(part.text)
                elif part.text:
                    response_text += part.text

        # --- Extract token usage ---
        prompt_tokens = None
        response_tokens = None
        total_tokens = None
        thoughts_tokens = None

        if llm_response.usage_metadata:
            usage = llm_response.usage_metadata
            prompt_tokens = getattr(usage, 'prompt_token_count', None)
            response_tokens = getattr(usage, 'candidates_token_count', None)
            total_tokens = getattr(usage, 'total_token_count', None)
            thoughts_tokens = getattr(usage, 'thoughts_token_count', None)

        # --- Model version ---
        model = (
            llm_response.model_version
            or self._request_config.get('model')
            or 'unknown'
        )

        # --- Build pvmap_llm_result dict ---
        llm_result = {
            'model': model,
            'temperature': self._request_config.get('temperature'),
            'max_tokens': self._request_config.get('max_output_tokens'),
            'start_time': datetime.fromtimestamp(start_time).isoformat(),
            'end_time': datetime.fromtimestamp(end_time).isoformat(),
            'duration_ms': duration_ms,
            'prompt_tokens': prompt_tokens,
            'response_tokens': response_tokens,
            'total_tokens': total_tokens,
            'thoughts_tokens': thoughts_tokens,
            'text': response_text,
            'thinking_content': thinking_parts if thinking_parts else None,
        }

        # Store in session state for ValidationAgent to pick up
        callback_context.state["pvmap_llm_result"] = llm_result

        logger.debug(
            "ArtifactLoggingPlugin: captured LLM result for %s "
            "(model=%s, tokens=%s, thinking_parts=%d, duration=%dms)",
            callback_context.agent_name,
            model,
            total_tokens,
            len(thinking_parts),
            duration_ms,
        )

        return None  # Don't modify response

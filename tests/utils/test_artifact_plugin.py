"""Tests for ArtifactLoggingPlugin."""
import time
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import pytest
import pytest_asyncio

from src.utils.artifact_plugin import ArtifactLoggingPlugin, _GENERATOR_AGENT_NAMES


# ---------------------------------------------------------------------------
# Helpers to build mock ADK objects
# ---------------------------------------------------------------------------

def _make_part(text: str, thought: bool = False):
    """Create a mock Part with text and optional thought flag."""
    part = MagicMock()
    part.text = text
    part.thought = thought
    return part


def _make_llm_response(
    parts=None,
    model_version=None,
    prompt_token_count=None,
    candidates_token_count=None,
    total_token_count=None,
    thoughts_token_count=None,
):
    """Create a mock LlmResponse with content.parts and usage_metadata."""
    resp = MagicMock()
    resp.model_version = model_version

    if parts is not None:
        resp.content = MagicMock()
        resp.content.parts = parts
    else:
        resp.content = None

    if any(v is not None for v in [
        prompt_token_count, candidates_token_count,
        total_token_count, thoughts_token_count,
    ]):
        usage = MagicMock()
        usage.prompt_token_count = prompt_token_count
        usage.candidates_token_count = candidates_token_count
        usage.total_token_count = total_token_count
        usage.thoughts_token_count = thoughts_token_count
        resp.usage_metadata = usage
    else:
        resp.usage_metadata = None

    return resp


def _make_callback_context(agent_name: str, state: dict | None = None):
    """Create a mock CallbackContext with agent_name and mutable state."""
    ctx = MagicMock()
    type(ctx).agent_name = PropertyMock(return_value=agent_name)
    if state is None:
        state = {}
    ctx.state = state
    return ctx


def _make_llm_request(model=None, temperature=None, max_output_tokens=None):
    """Create a mock LlmRequest."""
    req = MagicMock()
    req.model = model
    if temperature is not None or max_output_tokens is not None:
        req.config = MagicMock()
        req.config.temperature = temperature
        req.config.max_output_tokens = max_output_tokens
    else:
        req.config = None
    return req


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestArtifactLoggingPlugin:
    """Test the ArtifactLoggingPlugin."""

    def setup_method(self):
        self.plugin = ArtifactLoggingPlugin(
            output_dir=Path("/tmp/test_output"),
            dataset_name="test_dataset",
        )

    # ---- after_model_callback: text extraction ----

    async def test_extracts_text_from_content_parts(self):
        """after_model_callback should extract text from content.parts."""
        parts = [_make_part("Hello world")]
        resp = _make_llm_response(parts=parts)
        state = {}
        ctx = _make_callback_context("Generator", state)

        await self.plugin.after_model_callback(
            callback_context=ctx, llm_response=resp
        )

        result = state["pvmap_llm_result"]
        assert result["text"] == "Hello world"

    async def test_concatenates_multiple_text_parts(self):
        """Multiple non-thought text parts should be concatenated."""
        parts = [_make_part("Part1"), _make_part("Part2")]
        resp = _make_llm_response(parts=parts)
        state = {}
        ctx = _make_callback_context("Generator", state)

        await self.plugin.after_model_callback(
            callback_context=ctx, llm_response=resp
        )

        assert state["pvmap_llm_result"]["text"] == "Part1Part2"

    # ---- after_model_callback: thinking extraction ----

    async def test_extracts_thinking_parts(self):
        """Parts with thought=True should go to thinking_content."""
        parts = [
            _make_part("thinking step 1", thought=True),
            _make_part("actual response"),
            _make_part("thinking step 2", thought=True),
        ]
        resp = _make_llm_response(parts=parts)
        state = {}
        ctx = _make_callback_context("Generator", state)

        await self.plugin.after_model_callback(
            callback_context=ctx, llm_response=resp
        )

        result = state["pvmap_llm_result"]
        assert result["text"] == "actual response"
        assert result["thinking_content"] == [
            "thinking step 1", "thinking step 2"
        ]

    async def test_no_thinking_content_returns_none(self):
        """When no thought parts exist, thinking_content should be None."""
        parts = [_make_part("response only")]
        resp = _make_llm_response(parts=parts)
        state = {}
        ctx = _make_callback_context("Generator", state)

        await self.plugin.after_model_callback(
            callback_context=ctx, llm_response=resp
        )

        assert state["pvmap_llm_result"]["thinking_content"] is None

    # ---- after_model_callback: usage_metadata extraction ----

    async def test_extracts_usage_metadata(self):
        """Token counts should be extracted from usage_metadata."""
        parts = [_make_part("ok")]
        resp = _make_llm_response(
            parts=parts,
            prompt_token_count=100,
            candidates_token_count=200,
            total_token_count=300,
            thoughts_token_count=50,
        )
        state = {}
        ctx = _make_callback_context("Generator", state)

        await self.plugin.after_model_callback(
            callback_context=ctx, llm_response=resp
        )

        result = state["pvmap_llm_result"]
        assert result["prompt_tokens"] == 100
        assert result["response_tokens"] == 200
        assert result["total_tokens"] == 300
        assert result["thoughts_tokens"] == 50

    async def test_missing_usage_metadata_gives_none(self):
        """When usage_metadata is None, token fields should be None."""
        parts = [_make_part("ok")]
        resp = _make_llm_response(parts=parts)
        state = {}
        ctx = _make_callback_context("Generator", state)

        await self.plugin.after_model_callback(
            callback_context=ctx, llm_response=resp
        )

        result = state["pvmap_llm_result"]
        assert result["prompt_tokens"] is None
        assert result["response_tokens"] is None
        assert result["total_tokens"] is None
        assert result["thoughts_tokens"] is None

    # ---- after_model_callback: state storage ----

    async def test_stores_pvmap_llm_result_in_state(self):
        """pvmap_llm_result should be stored in callback_context.state."""
        parts = [_make_part("csv content")]
        resp = _make_llm_response(parts=parts, model_version="gemini-2.5-pro")
        state = {}
        ctx = _make_callback_context("Generator", state)

        await self.plugin.after_model_callback(
            callback_context=ctx, llm_response=resp
        )

        assert "pvmap_llm_result" in state
        result = state["pvmap_llm_result"]
        assert result["model"] == "gemini-2.5-pro"
        assert result["text"] == "csv content"
        assert "start_time" in result
        assert "end_time" in result
        assert "duration_ms" in result

    # ---- agent name filtering ----

    async def test_ignores_non_generator_agents(self):
        """Callbacks from non-generator agents should be skipped."""
        parts = [_make_part("should be ignored")]
        resp = _make_llm_response(parts=parts)
        state = {}
        ctx = _make_callback_context("Validator", state)

        await self.plugin.after_model_callback(
            callback_context=ctx, llm_response=resp
        )

        assert "pvmap_llm_result" not in state

    async def test_accepts_pvmap_generator_agent_name(self):
        """Should also work with 'PVMAPGenerator' agent name."""
        parts = [_make_part("response")]
        resp = _make_llm_response(parts=parts)
        state = {}
        ctx = _make_callback_context("PVMAPGenerator", state)

        await self.plugin.after_model_callback(
            callback_context=ctx, llm_response=resp
        )

        assert "pvmap_llm_result" in state

    # ---- before_model_callback: timing + config ----

    async def test_before_model_captures_timing(self):
        """before_model_callback should record start time in the pending dict."""
        req = _make_llm_request(model="gemini-2.5-flash")
        ctx = _make_callback_context("Generator")

        await self.plugin.before_model_callback(
            callback_context=ctx, llm_request=req
        )

        # New impl uses _pending dict keyed by agent_name:id(ctx)
        key = f"Generator:{id(ctx)}"
        assert key in self.plugin._pending
        assert self.plugin._pending[key]["start_wall"] > 0

    async def test_before_model_captures_config(self):
        """before_model_callback should extract temperature and max_output_tokens."""
        req = _make_llm_request(
            model="gemini-2.5-pro",
            temperature=0.5,
            max_output_tokens=8192,
        )
        ctx = _make_callback_context("Generator")

        await self.plugin.before_model_callback(
            callback_context=ctx, llm_request=req
        )

        key = f"Generator:{id(ctx)}"
        pending = self.plugin._pending[key]
        assert pending["temperature"] == 0.5
        assert pending["max_output_tokens"] == 8192
        assert pending["model"] == "gemini-2.5-pro"

    async def test_before_model_ignores_non_generator(self, tmp_path):
        """before_model_callback still records non-generator agents in _pending."""
        # New impl captures ALL agents; non-generators still get JSONL written.
        # Re-instantiate with tmp_path so JSONL dir creation works.
        plugin = ArtifactLoggingPlugin(output_dir=tmp_path, dataset_name="test")
        req = _make_llm_request(model="gemini-2.5-pro", temperature=0.3)
        ctx = _make_callback_context("SchemaSelector")

        await plugin.before_model_callback(
            callback_context=ctx, llm_request=req
        )

        # Pending entry IS created for all agents now
        key = f"SchemaSelector:{id(ctx)}"
        assert key in plugin._pending

    async def test_before_model_does_not_inject_thinking_config(self):
        """before_model_callback should NOT inject ThinkingConfig (thinking disabled)."""
        req = _make_llm_request(model="gemini-2.5-pro", temperature=0.0)
        req.config.thinking_config = None
        ctx = _make_callback_context("Generator")

        await self.plugin.before_model_callback(
            callback_context=ctx, llm_request=req
        )

        assert req.config.thinking_config is None

    # ---- model fallback chain ----

    async def test_model_fallback_to_request_model(self, tmp_path):
        """If model_version is None, should fall back to request model."""
        plugin = ArtifactLoggingPlugin(output_dir=tmp_path, dataset_name="test")
        state = {}
        ctx = _make_callback_context("Generator", state)
        req = _make_llm_request(model="gemini-2.5-flash")
        await plugin.before_model_callback(
            callback_context=ctx, llm_request=req
        )

        parts = [_make_part("response")]
        resp = _make_llm_response(parts=parts, model_version=None)
        await plugin.after_model_callback(
            callback_context=ctx, llm_response=resp
        )

        assert state["pvmap_llm_result"]["model"] == "gemini-2.5-flash"

    async def test_model_fallback_to_unknown(self):
        """If no model info anywhere, should fall back to 'unknown'."""
        parts = [_make_part("response")]
        resp = _make_llm_response(parts=parts, model_version=None)
        state = {}
        ctx = _make_callback_context("Generator", state)

        await self.plugin.after_model_callback(
            callback_context=ctx, llm_response=resp
        )

        assert state["pvmap_llm_result"]["model"] == "unknown"

    # ---- timing in result ----

    async def test_duration_calculated_correctly(self, tmp_path):
        """Duration should be positive when before/after are both called."""
        plugin = ArtifactLoggingPlugin(output_dir=tmp_path, dataset_name="test")
        state = {}
        ctx = _make_callback_context("Generator", state)
        req = _make_llm_request(model="test-model")
        await plugin.before_model_callback(
            callback_context=ctx, llm_request=req
        )

        time.sleep(0.01)

        parts = [_make_part("done")]
        resp = _make_llm_response(parts=parts)
        await plugin.after_model_callback(
            callback_context=ctx, llm_response=resp
        )

        assert state["pvmap_llm_result"]["duration_ms"] >= 10

    # ---- empty content ----

    async def test_handles_none_content(self):
        """Should handle LlmResponse with content=None gracefully."""
        resp = _make_llm_response(parts=None)
        state = {}
        ctx = _make_callback_context("Generator", state)

        await self.plugin.after_model_callback(
            callback_context=ctx, llm_response=resp
        )

        result = state["pvmap_llm_result"]
        assert result["text"] == ""
        assert result["thinking_content"] is None

    # ---- return value ----

    async def test_callbacks_return_none(self):
        """Both callbacks should return None (don't modify request/response)."""
        req = _make_llm_request()
        ctx = _make_callback_context("Generator")

        before_result = await self.plugin.before_model_callback(
            callback_context=ctx, llm_request=req
        )
        assert before_result is None

        parts = [_make_part("ok")]
        resp = _make_llm_response(parts=parts)
        state = {}
        ctx2 = _make_callback_context("Generator", state)
        after_result = await self.plugin.after_model_callback(
            callback_context=ctx2, llm_response=resp
        )
        assert after_result is None


class TestGeneratorAgentNames:
    """Verify the set of recognized generator agent names."""

    def test_contains_generator(self):
        assert "Generator" in _GENERATOR_AGENT_NAMES

    def test_contains_pvmap_generator(self):
        assert "PVMAPGenerator" in _GENERATOR_AGENT_NAMES


# ---------------------------------------------------------------------------
# Tests for generalized LLMTelemetryPlugin behavior
# (every agent captured, JSONL sidecar, Generator-specific stash preserved)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_plugin_writes_jsonl_for_non_generator_agent(tmp_path: Path):
    """Every agent's LLM call appends one line to llm_calls.jsonl."""
    from src.utils.artifact_plugin import ArtifactLoggingPlugin

    plugin = ArtifactLoggingPlugin(output_dir=tmp_path, dataset_name="ds1")
    ctx = _make_callback_context("SchemaSelectionAgent", state={})
    req = MagicMock()
    req.config = MagicMock(temperature=0.0, max_output_tokens=8192)
    req.model = "gemini-2.5-pro"

    await plugin.before_model_callback(callback_context=ctx, llm_request=req)

    parts = [_make_part("ok")]
    resp = _make_llm_response(
        parts=parts, model_version="gemini-2.5-pro",
        prompt_token_count=100, candidates_token_count=20,
        total_token_count=120, thoughts_token_count=10,
    )
    await plugin.after_model_callback(callback_context=ctx, llm_response=resp)

    jsonl = tmp_path / "ds1" / "llm_calls.jsonl"
    assert jsonl.exists(), f"JSONL not written at {jsonl}"
    lines = jsonl.read_text().strip().splitlines()
    assert len(lines) == 1
    import json
    rec = json.loads(lines[0])
    assert rec["agent"] == "SchemaSelectionAgent"
    assert rec["model"] == "gemini-2.5-pro"
    assert rec["prompt_tokens"] == 100
    assert rec["response_tokens"] == 20
    assert rec["total_tokens"] == 120
    assert rec["thoughts_tokens"] == 10
    assert "call_id" in rec
    assert "timestamp" in rec
    assert "duration_ms" in rec


@pytest.mark.asyncio
async def test_plugin_preserves_generator_state_stash(tmp_path: Path):
    """Generator-specific pvmap_llm_result state stash is still written."""
    from src.utils.artifact_plugin import ArtifactLoggingPlugin

    plugin = ArtifactLoggingPlugin(output_dir=tmp_path, dataset_name="ds1")
    state = {}
    ctx = _make_callback_context("Generator", state=state)
    req = MagicMock()
    req.config = MagicMock(temperature=0.0, max_output_tokens=8192)
    req.model = "gemini-3.1-pro-preview"

    await plugin.before_model_callback(callback_context=ctx, llm_request=req)

    parts = [_make_part("pvmap csv body")]
    resp = _make_llm_response(
        parts=parts, model_version="gemini-3.1-pro-preview",
        prompt_token_count=5000, candidates_token_count=500,
        total_token_count=5500, thoughts_token_count=100,
    )
    await plugin.after_model_callback(callback_context=ctx, llm_response=resp)

    # Generator-specific state behavior preserved:
    assert "pvmap_llm_result" in state
    assert state["pvmap_llm_result"]["total_tokens"] == 5500
    assert state["pvmap_llm_result"]["text"] == "pvmap csv body"

    # AND the JSONL line was also written:
    jsonl = tmp_path / "ds1" / "llm_calls.jsonl"
    assert jsonl.exists()


@pytest.mark.asyncio
async def test_plugin_jsonl_appends_multiple_calls(tmp_path: Path):
    """Multiple LLM calls across agents append distinct JSONL lines."""
    from src.utils.artifact_plugin import ArtifactLoggingPlugin

    plugin = ArtifactLoggingPlugin(output_dir=tmp_path, dataset_name="ds1")

    async def one_call(agent_name: str, model: str, tokens: int):
        ctx = _make_callback_context(agent_name, state={})
        req = MagicMock()
        req.config = MagicMock(temperature=0.0, max_output_tokens=None)
        req.model = model
        await plugin.before_model_callback(callback_context=ctx, llm_request=req)
        resp = _make_llm_response(
            parts=[_make_part("x")], model_version=model,
            prompt_token_count=tokens, candidates_token_count=10,
            total_token_count=tokens + 10, thoughts_token_count=0,
        )
        await plugin.after_model_callback(callback_context=ctx, llm_response=resp)

    await one_call("SamplingAgent", "gemini-3.1-pro-preview", 200)
    await one_call("SchemaSelectionAgent", "gemini-2.5-pro", 300)
    await one_call("Generator", "gemini-3.1-pro-preview", 5000)

    import json
    jsonl = tmp_path / "ds1" / "llm_calls.jsonl"
    lines = jsonl.read_text().strip().splitlines()
    assert len(lines) == 3
    agents = [json.loads(l)["agent"] for l in lines]
    assert agents == ["SamplingAgent", "SchemaSelectionAgent", "Generator"]

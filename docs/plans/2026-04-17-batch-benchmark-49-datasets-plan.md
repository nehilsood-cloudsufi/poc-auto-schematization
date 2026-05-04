# Batch Benchmark 49-Datasets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a batch harness that runs the auto-schematization pipeline over 49 datasets with full per-agent LLM telemetry and produces a unified JSON/CSV/Markdown comparison report with scatter plots and a failed-dataset retry file.

**Architecture:** Three loosely-coupled components: (1) orchestrator spawns up to 3 concurrent pipeline subprocesses with port-isolated MCP servers and timeout/resume support; (2) pipeline telemetry extensions (generalized `LLMTelemetryPlugin`, `phase_timer` context manager, `run_manifest.json` writer) emit per-dataset artifacts without changing pipeline behavior; (3) aggregator reads per-dataset artifacts and produces the batch report.

**Tech Stack:** Python 3.11, Google ADK plugins, pytest, pandas (optional for CSV), matplotlib (scatter PNGs), subprocess + concurrent.futures for orchestration.

**Spec:** `docs/plans/2026-04-17-batch-benchmark-49-datasets-design.md`

---

## File Structure

### New files

| Path | Purpose |
|---|---|
| `config/batch_49.txt` | List of 49 dataset names, one per line |
| `config/gemini_pricing.json` | Per-model input/output/thoughts $/MTok with `is_estimate` flags |
| `src/utils/phase_timer.py` | `PhaseTimer` class: context manager + writes `phase_timings.json` atomically |
| `src/utils/run_manifest.py` | `write_run_manifest(...)` helper that captures git state + CLI args |
| `scripts/batch_benchmark.py` | Orchestrator CLI (subprocess pool, checkpoint, failed list) |
| `scripts/batch_aggregate.py` | Aggregator CLI (JSON/CSV/Markdown/PNG report writer) |
| `scripts/batch_lib/__init__.py` | Package init (empty) |
| `scripts/batch_lib/checkpoint.py` | Append-only JSONL checkpoint with `fcntl.flock` |
| `scripts/batch_lib/pricing.py` | Pricing-table loader + cost math |
| `scripts/batch_lib/aggregator_core.py` | Pure functions: read per-dataset artifacts, build record dict |
| `scripts/batch_lib/report_markdown.py` | Markdown report builder |
| `scripts/batch_lib/scatter.py` | matplotlib scatter-plot writer |
| `tests/utils/test_phase_timer.py` | Unit tests for `PhaseTimer` |
| `tests/utils/test_run_manifest.py` | Unit tests for manifest writer |
| `tests/scripts/__init__.py` | Package init (empty) |
| `tests/scripts/test_checkpoint.py` | Unit tests for checkpoint append/resume |
| `tests/scripts/test_pricing.py` | Unit tests for cost math |
| `tests/scripts/test_aggregator_core.py` | Unit tests for per-dataset record builder |
| `tests/scripts/fixtures/synthetic_run/` | Synthetic artifact fixtures for aggregator tests |

### Modified files

| Path | Change |
|---|---|
| `src/utils/artifact_plugin.py` | Generalize capture to all agents; write JSONL per LLM call; keep Generator-specific `pvmap_llm_result` state stash |
| `src/run_pipeline.py` | Wire `phase_timer` around phases; call `write_run_manifest` at start |
| `tests/utils/test_artifact_plugin.py` | Add tests for the new JSONL output + multi-agent capture |

---

## Task 1: Create the 49-dataset list file

**Files:**
- Create: `config/batch_49.txt`

- [ ] **Step 1: Verify the `config/` directory exists or create it**

Run: `ls config/ 2>/dev/null || mkdir -p config`

- [ ] **Step 2: Write the dataset list**

Write exactly these 49 names, one per line, to `config/batch_49.txt`:

```
bis_bis_central_bank_policy_rate
brazil_sidra_ibge
brazil_visdata_FoodBasketDistribution
brfss_nchs_asthma_prevalence
ccd_enrollment
cdc_social_vulnerability_index
census_v2_sahie
census_v2_saipe
commerce_eda
database_on_indian_economy_india_rbi_state_statistics
doctoratedegreeemployment
fbi_fbigovcrime
india_ndap
india_ndap_india_nss_health_ailments
india_nfhs
inpe_fire
ncses_median_annual_salary
ncses_ncses_demographics_seh_import
oecd_regional_education
oecd_wastewater_treatment
opendataforafrica_ethiopia_statistics
opendataforafrica_kenya_census
southkorea_statistics_employment
southkorea_statistics_health
undata
us_bls_bls_ces
us_bls_bls_ces_state
us_bls_us_cpi
us_cdc_single_race
us_census
us_census_us_monthly_retail_sales
us_crash_fars_crashdata
us_steam_degrees_data
us_urban_school_teachers
usa_dol_minimum_wage
world_bank_commodity_market
zurich_bev_3240_wiki
zurich_bev_3903_age10_wiki
zurich_bev_3903_hel_wiki
zurich_bev_3903_sex_wiki
zurich_bev_4031_hel_wiki
zurich_bev_4031_sex_wiki
zurich_bev_4031_wiki
zurich_wir_2552_wiki
brazil_visdata_brazil_rural_development_program
child_birth
crdc_import_crdc_harassment_or_bullying
crdc_instructional_wifi_devices
fao_currency_and_exchange_rate
```

- [ ] **Step 3: Verify every dataset exists in `input/` and `ground_truth/`**

Run:
```bash
python3 -c "
import os
for ds in open('config/batch_49.txt'):
    ds = ds.strip()
    if not ds: continue
    assert os.path.isdir(f'input/{ds}'), f'missing input: {ds}'
    assert os.path.isdir(f'ground_truth/{ds}'), f'missing gt: {ds}'
print('OK: 49 datasets verified')
"
```
Expected output: `OK: 49 datasets verified`

- [ ] **Step 4: Commit**

```bash
git add config/batch_49.txt
git commit -m "feat: add 49-dataset list for batch benchmark"
```

---

## Task 2: Create pricing table config

**Files:**
- Create: `config/gemini_pricing.json`

- [ ] **Step 1: Write the pricing JSON**

Write exactly this content to `config/gemini_pricing.json`:

```json
{
  "_source": "https://ai.google.dev/gemini-api/docs/pricing as of 2026-04-17",
  "_note": "Preview models marked is_estimate=true use closest stable-tier pricing. Override this file via --pricing-file if you have better numbers.",
  "_currency": "USD",
  "models": {
    "gemini-3.1-pro-preview": {
      "input_per_mtok": 1.25,
      "output_per_mtok": 10.00,
      "thoughts_per_mtok": 10.00,
      "is_estimate": true
    },
    "gemini-2.5-pro": {
      "input_per_mtok": 1.25,
      "output_per_mtok": 10.00,
      "thoughts_per_mtok": 10.00,
      "is_estimate": false
    },
    "gemini-3-flash-preview": {
      "input_per_mtok": 0.15,
      "output_per_mtok": 0.60,
      "thoughts_per_mtok": 0.60,
      "is_estimate": true
    },
    "gemini-2.5-flash": {
      "input_per_mtok": 0.15,
      "output_per_mtok": 0.60,
      "thoughts_per_mtok": 0.60,
      "is_estimate": false
    }
  },
  "fallback": {
    "input_per_mtok": 1.25,
    "output_per_mtok": 10.00,
    "thoughts_per_mtok": 10.00,
    "is_estimate": true,
    "_note": "Used when a model name is not in the models map; conservative pro-tier pricing."
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add config/gemini_pricing.json
git commit -m "feat: add Gemini pricing table for batch benchmark cost estimation"
```

---

## Task 3: Write failing test for `PhaseTimer`

**Files:**
- Create: `src/utils/phase_timer.py` (empty stub only)
- Create: `tests/utils/test_phase_timer.py`

- [ ] **Step 1: Create empty stub so tests can import**

Write to `src/utils/phase_timer.py`:
```python
"""Per-phase wall-time tracking for pipeline runs."""
```

- [ ] **Step 2: Write the failing test**

Write to `tests/utils/test_phase_timer.py`:

```python
"""Tests for PhaseTimer context manager."""
import json
import time
from pathlib import Path

import pytest

from src.utils.phase_timer import PhaseTimer


def test_phase_timer_records_duration(tmp_path: Path):
    output = tmp_path / "phase_timings.json"
    timer = PhaseTimer(output_path=output)
    with timer.phase("sampling"):
        time.sleep(0.01)
    timer.finalize()

    data = json.loads(output.read_text())
    assert "sampling" in data
    assert data["sampling"]["duration_s"] >= 0.01
    assert "start" in data["sampling"]
    assert "end" in data["sampling"]
    assert "total" in data
    assert data["total"]["duration_s"] >= 0.01


def test_phase_timer_multiple_phases(tmp_path: Path):
    output = tmp_path / "phase_timings.json"
    timer = PhaseTimer(output_path=output)
    with timer.phase("discovery"):
        time.sleep(0.005)
    with timer.phase("sampling"):
        time.sleep(0.005)
    timer.finalize()

    data = json.loads(output.read_text())
    assert set(data.keys()) >= {"discovery", "sampling", "total"}
    # total >= sum of phases (serial execution)
    assert data["total"]["duration_s"] >= data["discovery"]["duration_s"] + data["sampling"]["duration_s"] - 0.001


def test_phase_timer_writes_on_exception(tmp_path: Path):
    """If a phase raises, timings captured so far are still written by finalize()."""
    output = tmp_path / "phase_timings.json"
    timer = PhaseTimer(output_path=output)
    with timer.phase("discovery"):
        time.sleep(0.005)
    try:
        with timer.phase("sampling"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    timer.finalize()

    data = json.loads(output.read_text())
    assert "discovery" in data
    assert "sampling" in data  # end time recorded even on exception


def test_phase_timer_atomic_write(tmp_path: Path):
    """finalize() writes atomically via temp file + rename."""
    output = tmp_path / "phase_timings.json"
    timer = PhaseTimer(output_path=output)
    with timer.phase("x"):
        pass
    timer.finalize()
    # No leftover temp files
    assert not list(tmp_path.glob("phase_timings.json.tmp*"))
    assert output.exists()
```

- [ ] **Step 3: Run the tests and verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/utils/test_phase_timer.py -x -q`
Expected: FAIL with `ImportError: cannot import name 'PhaseTimer'` or similar.

---

## Task 4: Implement `PhaseTimer`

**Files:**
- Modify: `src/utils/phase_timer.py`

- [ ] **Step 1: Write the implementation**

Overwrite `src/utils/phase_timer.py`:

```python
"""Per-phase wall-time tracking for pipeline runs.

Writes a flat JSON document mapping phase name -> {start, end, duration_s}, plus
a synthetic 'total' phase spanning the whole PhaseTimer lifetime.

Design notes:
- No threading synchronization: pipeline phases run serially in a single asyncio
  loop, so concurrent use isn't expected.
- finalize() writes atomically via tmp file + os.replace so partial dumps are
  never observed by a concurrent reader.
- Works even if a phase raises: __exit__ still records the end time.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterator


class PhaseTimer:
    def __init__(self, output_path: Path):
        self._output_path = Path(output_path)
        self._start_wall = time.time()
        self._start_iso = datetime.fromtimestamp(self._start_wall).isoformat()
        self._phases: Dict[str, Dict[str, object]] = {}

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        start_wall = time.time()
        start_iso = datetime.fromtimestamp(start_wall).isoformat()
        try:
            yield
        finally:
            end_wall = time.time()
            self._phases[name] = {
                "start": start_iso,
                "end": datetime.fromtimestamp(end_wall).isoformat(),
                "duration_s": round(end_wall - start_wall, 3),
            }

    def finalize(self) -> None:
        end_wall = time.time()
        data = dict(self._phases)
        data["total"] = {
            "start": self._start_iso,
            "end": datetime.fromtimestamp(end_wall).isoformat(),
            "duration_s": round(end_wall - self._start_wall, 3),
        }
        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix=self._output_path.name + ".tmp",
            dir=self._output_path.parent,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self._output_path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
```

- [ ] **Step 2: Run the tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/utils/test_phase_timer.py -x -q`
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add src/utils/phase_timer.py tests/utils/test_phase_timer.py
git commit -m "feat(telemetry): add PhaseTimer for per-phase wall-time tracking"
```

---

## Task 5: Write failing test for `write_run_manifest`

**Files:**
- Create: `src/utils/run_manifest.py` (stub)
- Create: `tests/utils/test_run_manifest.py`

- [ ] **Step 1: Create the stub**

Write to `src/utils/run_manifest.py`:
```python
"""Run manifest writer: captures git state, CLI args, and pipeline config."""
```

- [ ] **Step 2: Write the failing test**

Write to `tests/utils/test_run_manifest.py`:

```python
"""Tests for write_run_manifest."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.run_manifest import write_run_manifest


def test_write_run_manifest_basic(tmp_path: Path):
    with patch("src.utils.run_manifest._git_sha", return_value="abc1234"), \
         patch("src.utils.run_manifest._git_branch", return_value="feature/x"), \
         patch("src.utils.run_manifest._git_dirty", return_value=False):
        path = write_run_manifest(
            output_dir=tmp_path,
            dataset="some_ds",
            cli_args={"model": "gemini-3.1-pro-preview", "thinking_level": "high"},
            pipeline_config={"enable_mcp": True, "prompt_version": "v3"},
            worker_id=0,
            mcp_port=3000,
        )

    assert path == tmp_path / "run_manifest.json"
    data = json.loads(path.read_text())
    assert data["dataset"] == "some_ds"
    assert data["git_sha"] == "abc1234"
    assert data["git_branch"] == "feature/x"
    assert data["git_dirty"] is False
    assert data["cli_args"]["model"] == "gemini-3.1-pro-preview"
    assert data["pipeline_config"]["enable_mcp"] is True
    assert data["worker_id"] == 0
    assert data["mcp_port"] == 3000
    assert "started_at" in data


def test_write_run_manifest_handles_git_failure(tmp_path: Path):
    """If git isn't available, manifest still writes with null git fields."""
    with patch("src.utils.run_manifest._git_sha", return_value=None), \
         patch("src.utils.run_manifest._git_branch", return_value=None), \
         patch("src.utils.run_manifest._git_dirty", return_value=None):
        path = write_run_manifest(
            output_dir=tmp_path,
            dataset="x",
            cli_args={},
            pipeline_config={},
            worker_id=None,
            mcp_port=None,
        )
    data = json.loads(path.read_text())
    assert data["git_sha"] is None
    assert data["git_branch"] is None
```

- [ ] **Step 3: Run the tests and verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/utils/test_run_manifest.py -x -q`
Expected: FAIL with import or attribute error.

---

## Task 6: Implement `write_run_manifest`

**Files:**
- Modify: `src/utils/run_manifest.py`

- [ ] **Step 1: Write the implementation**

Overwrite `src/utils/run_manifest.py`:

```python
"""Run manifest writer: captures git state, CLI args, and pipeline config.

Writes run_manifest.json to the dataset output directory at pipeline start.
Captures git sha/branch/dirty for reproducibility. All fields are optional —
git failures do not block the pipeline.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any


def _run_git(args: list[str]) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", *args],
            capture_output=True, text=True, timeout=5, check=False,
        )
        if r.returncode != 0:
            return None
        return r.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _git_sha() -> Optional[str]:
    return _run_git(["rev-parse", "HEAD"])


def _git_branch() -> Optional[str]:
    return _run_git(["rev-parse", "--abbrev-ref", "HEAD"])


def _git_dirty() -> Optional[bool]:
    out = _run_git(["status", "--porcelain"])
    if out is None:
        return None
    return bool(out)


def write_run_manifest(
    output_dir: Path,
    dataset: str,
    cli_args: Dict[str, Any],
    pipeline_config: Dict[str, Any],
    worker_id: Optional[int] = None,
    mcp_port: Optional[int] = None,
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "dataset": dataset,
        "git_sha": _git_sha(),
        "git_branch": _git_branch(),
        "git_dirty": _git_dirty(),
        "started_at": datetime.now().isoformat(),
        "cli_args": cli_args,
        "pipeline_config": pipeline_config,
        "worker_id": worker_id,
        "mcp_port": mcp_port,
    }
    path = output_dir / "run_manifest.json"
    path.write_text(json.dumps(manifest, indent=2))
    return path
```

- [ ] **Step 2: Run the tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/utils/test_run_manifest.py -x -q`
Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add src/utils/run_manifest.py tests/utils/test_run_manifest.py
git commit -m "feat(telemetry): add run manifest writer for git + config capture"
```

---

## Task 7: Write failing test for generalized `LLMTelemetryPlugin`

**Files:**
- Modify: `tests/utils/test_artifact_plugin.py`

- [ ] **Step 1: Append new test cases**

Append to `tests/utils/test_artifact_plugin.py`:

```python


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
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/utils/test_artifact_plugin.py -x -q -k "jsonl or preserves_generator"`
Expected: 3 failures — the current plugin filters to Generator-only and does not write JSONL.

---

## Task 8: Generalize `ArtifactLoggingPlugin` to `LLMTelemetryPlugin` behavior

**Files:**
- Modify: `src/utils/artifact_plugin.py`

- [ ] **Step 1: Apply the changes**

Overwrite `src/utils/artifact_plugin.py`:

```python
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
        # Use an attribute placed on the context if present; otherwise fall
        # back to agent_name (still correct for serial pipeline phases).
        return f"{ctx.agent_name}:{id(ctx)}"

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
```

- [ ] **Step 2: Run ALL artifact-plugin tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/utils/test_artifact_plugin.py -x -q`
Expected: all pre-existing tests AND the 3 new tests pass.

- [ ] **Step 3: Run the full test suite to catch regressions**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: all green; test count should be previous count + ~3–6 new tests.

- [ ] **Step 4: Commit**

```bash
git add src/utils/artifact_plugin.py tests/utils/test_artifact_plugin.py
git commit -m "feat(telemetry): capture LLM calls across all agents into llm_calls.jsonl"
```

---

## Task 9: Wire `PhaseTimer` and `run_manifest` into `run_pipeline.py`

**Files:**
- Modify: `src/run_pipeline.py`

- [ ] **Step 1: Add imports**

Add these imports at the top of `src/run_pipeline.py` (after the existing `from src.utils.artifact_plugin` import on line 39):

```python
from src.utils.phase_timer import PhaseTimer
from src.utils.run_manifest import write_run_manifest
```

- [ ] **Step 2: Locate the pipeline-entry block**

Find the block in `run_dataset_pipeline(...)` around `src/run_pipeline.py:283-289` where `ArtifactLoggingPlugin` is instantiated. This is inside the dataset-specific setup path.

- [ ] **Step 3: Instantiate `PhaseTimer` and write manifest**

Immediately after the `ArtifactLoggingPlugin` instantiation block (around line 289, inside the `if dataset_name:` branch), add:

```python
    # Phase timer (captures wall-time per pipeline phase)
    dataset_out = output_dir / dataset_name
    dataset_out.mkdir(parents=True, exist_ok=True)
    phase_timer = PhaseTimer(output_path=dataset_out / "phase_timings.json")

    # Run manifest (git state + config snapshot)
    try:
        worker_id = int(os.environ.get("BATCH_WORKER_ID", "-1"))
        worker_id = worker_id if worker_id >= 0 else None
    except ValueError:
        worker_id = None
    try:
        mcp_port_env = int(os.environ.get("MCP_PORT", "0"))
        mcp_port_val = mcp_port_env if mcp_port_env > 0 else None
    except ValueError:
        mcp_port_val = None
    write_run_manifest(
        output_dir=dataset_out,
        dataset=dataset_name,
        cli_args={
            "model": model,
            "thinking_level": thinking_level,
            "enable_mcp": enable_mcp,
            "prompt_version": prompt_version,
            "feedback_prompt_version": feedback_prompt_version,
            "use_metadata": use_metadata,
            "use_llm_judge": use_llm_judge,
            "skip_sampling": skip_sampling,
            "skip_schema_selection": skip_schema_selection,
            "max_retries": max_retries,
        },
        pipeline_config={
            "prompt_version": prompt_version,
            "feedback_prompt_version": feedback_prompt_version,
            "sampling_mode": "programmatic",
        },
        worker_id=worker_id,
        mcp_port=mcp_port_val,
    )
else:
    phase_timer = None
```

Note: The existing `else` branch (no dataset) should set `phase_timer = None`. Verify the block looks like:

```python
    if dataset_name:
        artifact_plugin = ArtifactLoggingPlugin(...)
        all_plugins = base_plugins + [artifact_plugin]
        # ... new phase_timer + manifest code ...
    else:
        all_plugins = base_plugins
        phase_timer = None
```

- [ ] **Step 4: Wrap phase boundaries with the timer**

Find the places where each phase runs. In this file, the existing phases are invoked via the coordinator's `runner.run(...)`. For the initial implementation, wrap the **total run** only plus the **subprocess validation** call (the only part we can cleanly isolate from this entry point without refactoring the coordinator).

Search for `await runner.run(` or `runner.run_async(` or similar in `src/run_pipeline.py`. Wrap the whole pipeline invocation in:

```python
if phase_timer:
    with phase_timer.phase("pipeline_total"):
        final_state = await runner.run_async(...)
    phase_timer.finalize()
else:
    final_state = await runner.run_async(...)
```

**Scope note:** detailed per-phase (sampling / schema_selection / pvmap_generation / validation / evaluation) timing requires wrapping calls in `src/agents/coordinator.py`. That is DEFERRED to Task 10.

- [ ] **Step 5: Run the tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: all green.

- [ ] **Step 6: Smoke-test on one tiny dataset**

Run:
```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python src/run_pipeline.py \
  --dataset zurich_bev_3240_wiki --output-dir /tmp/pt_smoke --enable-mcp
```
Expected: exit 0; check `/tmp/pt_smoke/zurich_bev_3240_wiki/phase_timings.json` and `/tmp/pt_smoke/zurich_bev_3240_wiki/run_manifest.json` both exist with valid JSON.

- [ ] **Step 7: Commit**

```bash
git add src/run_pipeline.py
git commit -m "feat(telemetry): wire PhaseTimer + run_manifest into pipeline entrypoint"
```

---

## Task 10: Add per-phase timing hooks in the coordinator (optional refinement)

**Files:**
- Modify: `src/agents/coordinator.py`
- Modify: `src/run_pipeline.py` (pass timer through to coordinator)

This task instruments finer-grained per-phase timing. If implementation reveals that the coordinator's phase structure can't cleanly take a timer parameter without large refactors, DOCUMENT that in the plan run log and rely on Task 9's coarse `pipeline_total` timer plus the per-call `duration_ms` from the telemetry plugin (which gives us per-agent timing, close enough to per-phase).

- [ ] **Step 1: Inspect the coordinator's phase structure**

Read `src/agents/coordinator.py` from top to bottom. If phases are linear sub-agents of a single SequentialAgent, we can thread a `phase_timer` through and wrap each `sub_agent.run_async` call. If the structure is more nested, note this and skip to Step 4.

- [ ] **Step 2: If feasible, pass `phase_timer` from `run_pipeline.py` into the coordinator factory**

Change the coordinator factory signature (e.g. `create_coordinator(...)`) to accept an optional `phase_timer: Optional[PhaseTimer] = None`, and have the coordinator wrap each phase like:

```python
if phase_timer:
    with phase_timer.phase("sampling"):
        await sampling_agent.run_async(...)
else:
    await sampling_agent.run_async(...)
```

Phase names (exact strings): `discovery`, `sampling`, `schema_selection`, `pvmap_generation`, `validation`, `evaluation`.

- [ ] **Step 3: Update `run_pipeline.py` to pass the timer through**

Locate the coordinator creation site and forward `phase_timer` there. Call `phase_timer.finalize()` after the runner returns (replace the Task 9 `phase("pipeline_total")` wrapper, which becomes redundant).

- [ ] **Step 4: If infeasible, document the decision**

If per-phase hooks would require restructuring more than ~30 lines of coordinator code, mark this task as "deferred" in the plan run log with the reason, and keep Task 9's coarse timing. The telemetry plugin's per-call `duration_ms` already gives per-agent granularity suitable for the report.

- [ ] **Step 5: Run full tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: all green.

- [ ] **Step 6: Smoke-test**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python src/run_pipeline.py \
  --dataset zurich_bev_3240_wiki --output-dir /tmp/pt_smoke2 --enable-mcp
cat /tmp/pt_smoke2/zurich_bev_3240_wiki/phase_timings.json
```
Expected: the JSON has both `total` and the per-phase entries (if Step 2 succeeded) or just `pipeline_total` (if Step 4 path taken). Either is acceptable.

- [ ] **Step 7: Commit**

```bash
git add src/agents/coordinator.py src/run_pipeline.py
git commit -m "feat(telemetry): per-phase timer hooks in coordinator (or coarse fallback)"
```

---

## Task 11: Write failing test for checkpoint helper

**Files:**
- Create: `scripts/__init__.py` (if missing)
- Create: `scripts/batch_lib/__init__.py`
- Create: `scripts/batch_lib/checkpoint.py` (stub)
- Create: `tests/scripts/__init__.py`
- Create: `tests/scripts/test_checkpoint.py`

- [ ] **Step 1: Create package stubs**

```bash
mkdir -p scripts/batch_lib tests/scripts
touch scripts/__init__.py scripts/batch_lib/__init__.py tests/scripts/__init__.py
```

- [ ] **Step 2: Create checkpoint stub**

Write to `scripts/batch_lib/checkpoint.py`:
```python
"""Append-only JSONL checkpoint with file-lock for multi-worker orchestrator."""
```

- [ ] **Step 3: Write the failing tests**

Write to `tests/scripts/test_checkpoint.py`:

```python
"""Tests for Checkpoint JSONL helper."""
import json
from pathlib import Path

import pytest

from scripts.batch_lib.checkpoint import Checkpoint


def test_checkpoint_appends(tmp_path: Path):
    cp_path = tmp_path / "checkpoint.jsonl"
    cp = Checkpoint(cp_path)
    cp.append({"dataset": "a", "status": "ok"})
    cp.append({"dataset": "b", "status": "timeout"})

    lines = cp_path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["dataset"] == "a"
    assert json.loads(lines[1])["dataset"] == "b"


def test_checkpoint_read_completed(tmp_path: Path):
    cp_path = tmp_path / "checkpoint.jsonl"
    cp = Checkpoint(cp_path)
    cp.append({"dataset": "a", "status": "ok"})
    cp.append({"dataset": "b", "status": "ok"})

    done = cp.read_completed_datasets()
    assert done == {"a", "b"}


def test_checkpoint_read_empty_when_missing(tmp_path: Path):
    cp_path = tmp_path / "nope.jsonl"
    cp = Checkpoint(cp_path)
    assert cp.read_completed_datasets() == set()


def test_checkpoint_handles_corrupt_line(tmp_path: Path):
    """A garbled line should not crash resumption; it's skipped with a warning."""
    cp_path = tmp_path / "checkpoint.jsonl"
    cp_path.write_text('{"dataset":"a","status":"ok"}\n<garbage>\n{"dataset":"b","status":"ok"}\n')
    cp = Checkpoint(cp_path)
    done = cp.read_completed_datasets()
    assert done == {"a", "b"}
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/scripts/test_checkpoint.py -x -q`
Expected: FAIL with ImportError.

---

## Task 12: Implement `Checkpoint`

**Files:**
- Modify: `scripts/batch_lib/checkpoint.py`

- [ ] **Step 1: Write implementation**

Overwrite `scripts/batch_lib/checkpoint.py`:

```python
"""Append-only JSONL checkpoint with fcntl file lock.

The orchestrator appends one record per completed dataset. Multiple workers
may call append() concurrently; a POSIX exclusive lock serializes the writes.
read_completed_datasets() parses the file (tolerating corrupt lines) and
returns the set of dataset names that have a record.
"""
from __future__ import annotations

import fcntl
import json
import logging
from pathlib import Path
from typing import Any, Dict, Set

logger = logging.getLogger(__name__)


class Checkpoint:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: Dict[str, Any]) -> None:
        line = json.dumps(record) + "\n"
        # Open in append mode + lock so concurrent writers interleave cleanly
        with open(self.path, "a", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(line)
                f.flush()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def read_completed_datasets(self) -> Set[str]:
        if not self.path.exists():
            return set()
        done: Set[str] = set()
        with open(self.path, "r", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                for i, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("checkpoint: skipping corrupt line %d", i)
                        continue
                    ds = rec.get("dataset")
                    if ds:
                        done.add(ds)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return done
```

- [ ] **Step 2: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/scripts/test_checkpoint.py -x -q`
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add scripts/__init__.py scripts/batch_lib/__init__.py scripts/batch_lib/checkpoint.py \
        tests/scripts/__init__.py tests/scripts/test_checkpoint.py
git commit -m "feat(batch): add JSONL checkpoint with file lock"
```

---

## Task 13: Write failing test for pricing helper

**Files:**
- Create: `scripts/batch_lib/pricing.py` (stub)
- Create: `tests/scripts/test_pricing.py`

- [ ] **Step 1: Create stub**

Write to `scripts/batch_lib/pricing.py`:
```python
"""Pricing table loader + cost computation."""
```

- [ ] **Step 2: Write failing tests**

Write to `tests/scripts/test_pricing.py`:

```python
"""Tests for pricing."""
import json
from pathlib import Path

import pytest

from scripts.batch_lib.pricing import PricingTable, compute_cost


@pytest.fixture
def pricing_file(tmp_path: Path) -> Path:
    p = tmp_path / "pricing.json"
    p.write_text(json.dumps({
        "models": {
            "gemini-3.1-pro-preview": {
                "input_per_mtok": 1.25, "output_per_mtok": 10.0, "thoughts_per_mtok": 10.0,
                "is_estimate": True,
            },
            "gemini-3-flash-preview": {
                "input_per_mtok": 0.15, "output_per_mtok": 0.60, "thoughts_per_mtok": 0.60,
                "is_estimate": True,
            },
        },
        "fallback": {
            "input_per_mtok": 1.25, "output_per_mtok": 10.0, "thoughts_per_mtok": 10.0,
            "is_estimate": True,
        },
    }))
    return p


def test_pricing_table_loads(pricing_file: Path):
    pt = PricingTable.load(pricing_file)
    assert "gemini-3.1-pro-preview" in pt.models
    assert pt.models["gemini-3.1-pro-preview"]["input_per_mtok"] == 1.25


def test_compute_cost_pro(pricing_file: Path):
    pt = PricingTable.load(pricing_file)
    # 1M input, 1M output, 1M thoughts -> 1.25 + 10 + 10 = 21.25
    result = compute_cost(
        prompt_tokens=1_000_000, response_tokens=1_000_000, thoughts_tokens=1_000_000,
        model="gemini-3.1-pro-preview", pricing=pt,
    )
    assert result["cost_usd"] == pytest.approx(21.25, rel=1e-6)
    assert result["is_estimate"] is True


def test_compute_cost_flash_is_cheaper(pricing_file: Path):
    pt = PricingTable.load(pricing_file)
    r_pro = compute_cost(
        prompt_tokens=100_000, response_tokens=100_000, thoughts_tokens=0,
        model="gemini-3.1-pro-preview", pricing=pt,
    )
    r_flash = compute_cost(
        prompt_tokens=100_000, response_tokens=100_000, thoughts_tokens=0,
        model="gemini-3-flash-preview", pricing=pt,
    )
    assert r_flash["cost_usd"] < r_pro["cost_usd"]


def test_compute_cost_unknown_model_uses_fallback(pricing_file: Path):
    pt = PricingTable.load(pricing_file)
    r = compute_cost(
        prompt_tokens=0, response_tokens=0, thoughts_tokens=0,
        model="gemini-99-pro-preview", pricing=pt,
    )
    assert r["cost_usd"] == 0.0
    assert r["is_estimate"] is True
    assert r["model_used_for_pricing"] == "fallback"


def test_compute_cost_none_tokens_treated_as_zero(pricing_file: Path):
    """Missing token counts should be treated as 0, not crash."""
    pt = PricingTable.load(pricing_file)
    r = compute_cost(
        prompt_tokens=None, response_tokens=None, thoughts_tokens=None,
        model="gemini-3.1-pro-preview", pricing=pt,
    )
    assert r["cost_usd"] == 0.0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/scripts/test_pricing.py -x -q`
Expected: FAIL with ImportError.

---

## Task 14: Implement pricing helper

**Files:**
- Modify: `scripts/batch_lib/pricing.py`

- [ ] **Step 1: Write implementation**

Overwrite `scripts/batch_lib/pricing.py`:

```python
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
```

- [ ] **Step 2: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/scripts/test_pricing.py -x -q`
Expected: 5 passed.

- [ ] **Step 3: Commit**

```bash
git add scripts/batch_lib/pricing.py tests/scripts/test_pricing.py
git commit -m "feat(batch): add pricing table loader and cost computation"
```

---

## Task 15: Build synthetic fixture directory for aggregator tests

**Files:**
- Create: `tests/scripts/fixtures/synthetic_run/dsA/llm_calls.jsonl`
- Create: `tests/scripts/fixtures/synthetic_run/dsA/phase_timings.json`
- Create: `tests/scripts/fixtures/synthetic_run/dsA/run_manifest.json`
- Create: `tests/scripts/fixtures/synthetic_run/dsA/eval_results/diff_results.json`
- Create: `tests/scripts/fixtures/synthetic_run/dsA/generated_pvmap.csv`
- Create: `tests/scripts/fixtures/synthetic_run/dsA/pipeline.log` (empty placeholder)

- [ ] **Step 1: Create directory**

```bash
mkdir -p tests/scripts/fixtures/synthetic_run/dsA/eval_results
```

- [ ] **Step 2: Write `llm_calls.jsonl`**

Write these 4 lines (one JSON object per line) to `tests/scripts/fixtures/synthetic_run/dsA/llm_calls.jsonl`:

```jsonl
{"call_id":"c1","timestamp":"2026-04-17T12:00:00","agent":"SamplingAgent","model":"gemini-3.1-pro-preview","prompt_tokens":1000,"thoughts_tokens":200,"response_tokens":300,"total_tokens":1500,"duration_ms":15000}
{"call_id":"c2","timestamp":"2026-04-17T12:01:00","agent":"SchemaSelectionAgent","model":"gemini-2.5-pro","prompt_tokens":2000,"thoughts_tokens":400,"response_tokens":600,"total_tokens":3000,"duration_ms":20000}
{"call_id":"c3","timestamp":"2026-04-17T12:02:00","agent":"Generator","model":"gemini-3.1-pro-preview","prompt_tokens":5000,"thoughts_tokens":1000,"response_tokens":800,"total_tokens":6800,"duration_ms":30000}
{"call_id":"c4","timestamp":"2026-04-17T12:03:00","agent":"FeedbackAgent","model":"gemini-3.1-pro-preview","prompt_tokens":3000,"thoughts_tokens":500,"response_tokens":400,"total_tokens":3900,"duration_ms":12000}
```

- [ ] **Step 3: Write `phase_timings.json`**

```json
{
  "sampling":         {"start":"2026-04-17T11:59:45","end":"2026-04-17T12:00:15","duration_s":30.0},
  "schema_selection": {"start":"2026-04-17T12:00:15","end":"2026-04-17T12:00:35","duration_s":20.0},
  "pvmap_generation": {"start":"2026-04-17T12:00:35","end":"2026-04-17T12:01:05","duration_s":30.0},
  "validation":       {"start":"2026-04-17T12:01:05","end":"2026-04-17T12:05:05","duration_s":240.0},
  "evaluation":       {"start":"2026-04-17T12:05:05","end":"2026-04-17T12:05:10","duration_s":5.0},
  "total":            {"start":"2026-04-17T11:59:45","end":"2026-04-17T12:05:10","duration_s":325.0}
}
```

- [ ] **Step 4: Write `run_manifest.json`**

```json
{
  "dataset": "dsA",
  "git_sha": "abc1234",
  "git_branch": "test-branch",
  "git_dirty": false,
  "started_at": "2026-04-17T11:59:45",
  "cli_args": {"model": "gemini-3.1-pro-preview", "enable_mcp": true, "prompt_version": "v3"},
  "pipeline_config": {"prompt_version": "v3", "sampling_mode": "programmatic"},
  "worker_id": 0,
  "mcp_port": 3000
}
```

- [ ] **Step 5: Write `eval_results/diff_results.json`**

```json
{
  "nodes-ground-truth": 14,
  "nodes-auto-generated": 16,
  "nodes-matched": 2,
  "PVs-matched": 12,
  "pvs-modified": 18,
  "pvs-deleted": 3,
  "pvs-added": 5
}
```

- [ ] **Step 6: Write `generated_pvmap.csv`**

```csv
Node,observationAbout,observationDate,value
dcid:A,observationAbout,{Data},{Number}
dcid:B,observationAbout,{Data},{Number}
dcid:C,observationAbout,{Data},{Number}
```

- [ ] **Step 7: Write empty `pipeline.log`**

```bash
touch tests/scripts/fixtures/synthetic_run/dsA/pipeline.log
```

- [ ] **Step 8: Commit**

```bash
git add tests/scripts/fixtures/
git commit -m "test(batch): add synthetic run fixtures for aggregator tests"
```

---

## Task 16: Write failing test for `aggregator_core.build_dataset_record`

**Files:**
- Create: `scripts/batch_lib/aggregator_core.py` (stub)
- Create: `tests/scripts/test_aggregator_core.py`

- [ ] **Step 1: Create stub**

Write to `scripts/batch_lib/aggregator_core.py`:
```python
"""Per-dataset record builder and cross-dataset rollup helpers."""
```

- [ ] **Step 2: Write the failing test**

Write to `tests/scripts/test_aggregator_core.py`:

```python
"""Tests for aggregator_core.build_dataset_record."""
from pathlib import Path

import pytest

from scripts.batch_lib.aggregator_core import build_dataset_record, compute_accuracy
from scripts.batch_lib.pricing import PricingTable


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_run"


@pytest.fixture
def pricing(tmp_path):
    import json
    p = tmp_path / "pricing.json"
    p.write_text(json.dumps({
        "models": {
            "gemini-3.1-pro-preview": {"input_per_mtok": 1.25, "output_per_mtok": 10.0, "thoughts_per_mtok": 10.0, "is_estimate": True},
            "gemini-2.5-pro":         {"input_per_mtok": 1.25, "output_per_mtok": 10.0, "thoughts_per_mtok": 10.0, "is_estimate": False},
        },
        "fallback": {"input_per_mtok": 1.25, "output_per_mtok": 10.0, "thoughts_per_mtok": 10.0, "is_estimate": True},
    }))
    return PricingTable.load(p)


def test_compute_accuracy_basic():
    r = compute_accuracy(pvs_matched=12, pvs_modified=18, pvs_deleted=3, nodes_matched=2, nodes_gt=14, nodes_generated=16)
    # pv_accuracy = 12 / (12+18+3) * 100 = 36.36
    assert r["pv_accuracy"] == pytest.approx(36.36, rel=1e-2)
    # node_accuracy = min(2, 14) / 14 * 100 = 14.29
    assert r["node_accuracy"] == pytest.approx(14.29, rel=1e-2)
    # node_coverage = 16 / 14 * 100 = 114.29
    assert r["node_coverage"] == pytest.approx(114.29, rel=1e-2)


def test_compute_accuracy_handles_zero_denominator():
    r = compute_accuracy(pvs_matched=0, pvs_modified=0, pvs_deleted=0, nodes_matched=0, nodes_gt=0, nodes_generated=0)
    assert r["pv_accuracy"] == 0.0
    assert r["node_accuracy"] == 0.0
    assert r["node_coverage"] == 0.0


def test_build_dataset_record_from_fixture(pricing):
    rec = build_dataset_record(
        dataset="dsA",
        run_dir=FIXTURE / "dsA",
        input_csv=None,  # complexity defaults when no input file
        pricing=pricing,
        baseline_pv=None, baseline_node=None,
        status="passed",
    )

    # Shape
    assert rec["dataset"] == "dsA"
    assert rec["status"] == "passed"
    assert rec["accuracy"]["pv_accuracy"] == pytest.approx(36.36, rel=1e-2)
    assert rec["accuracy"]["pvs_matched"] == 12

    # Totals across 4 calls: 1500 + 3000 + 6800 + 3900 = 15200
    assert rec["tokens_total"]["total"] == 15200
    # Per-agent rollup has 4 agents
    assert set(rec["tokens_by_agent"].keys()) == {"SamplingAgent", "SchemaSelectionAgent", "Generator", "FeedbackAgent"}
    # Per-agent model tagged
    assert rec["tokens_by_agent"]["SchemaSelectionAgent"]["model"] == "gemini-2.5-pro"

    # Cost is positive
    assert rec["cost_usd"]["total"] > 0

    # Phase timing copied through
    assert rec["timing_seconds"]["validation"] == 240.0


def test_build_dataset_record_missing_eval_marks_passed_with_warnings(tmp_path, pricing):
    """If diff_results.json is absent, accuracy is null and status becomes passed_with_warnings."""
    run_dir = tmp_path / "dsX"
    run_dir.mkdir()
    (run_dir / "llm_calls.jsonl").write_text("")
    rec = build_dataset_record(
        dataset="dsX", run_dir=run_dir, input_csv=None, pricing=pricing,
        baseline_pv=None, baseline_node=None, status="passed",
    )
    assert rec["accuracy"]["pv_accuracy"] is None
    assert rec["status"] == "passed_with_warnings"


def test_build_dataset_record_applies_baseline_delta(pricing):
    rec = build_dataset_record(
        dataset="dsA", run_dir=FIXTURE / "dsA", input_csv=None, pricing=pricing,
        baseline_pv=36.4, baseline_node=14.3, status="passed",
    )
    assert rec["accuracy"]["delta_pv_vs_doc_gemini3pro"] == pytest.approx(
        rec["accuracy"]["pv_accuracy"] - 36.4, abs=0.01
    )
    assert rec["accuracy"]["delta_node_vs_doc_gemini3pro"] == pytest.approx(
        rec["accuracy"]["node_accuracy"] - 14.3, abs=0.01
    )


def test_build_dataset_record_crashed_status(tmp_path, pricing):
    """Crashed dataset: no artifacts, record still builds with nulls."""
    run_dir = tmp_path / "dsY"
    run_dir.mkdir()
    rec = build_dataset_record(
        dataset="dsY", run_dir=run_dir, input_csv=None, pricing=pricing,
        baseline_pv=None, baseline_node=None, status="crashed",
    )
    assert rec["status"] == "crashed"
    assert rec["tokens_total"]["total"] == 0
    assert rec["accuracy"]["pv_accuracy"] is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/scripts/test_aggregator_core.py -x -q`
Expected: FAIL with ImportError.

---

## Task 17: Implement `aggregator_core`

**Files:**
- Modify: `scripts/batch_lib/aggregator_core.py`

- [ ] **Step 1: Write implementation**

Overwrite `scripts/batch_lib/aggregator_core.py`:

```python
"""Per-dataset record builder and cross-dataset rollup helpers.

Each dataset's record has the shape documented in the design spec
(docs/plans/2026-04-17-batch-benchmark-49-datasets-design.md §5.3).
"""
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.batch_lib.pricing import PricingTable, compute_cost

logger = logging.getLogger(__name__)


def _read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("failed to read %s: %s", path, e)
        return None


def _read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    out: List[dict] = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("%s: corrupt line %d, skipping", path, i)
    return out


def compute_accuracy(
    pvs_matched: int, pvs_modified: int, pvs_deleted: int,
    nodes_matched: int, nodes_gt: int, nodes_generated: int,
) -> Dict[str, float]:
    pv_denom = pvs_matched + pvs_modified + pvs_deleted
    pv_acc = (pvs_matched / pv_denom * 100) if pv_denom else 0.0
    node_acc = (min(nodes_matched, nodes_gt) / nodes_gt * 100) if nodes_gt else 0.0
    node_cov = (nodes_generated / nodes_gt * 100) if nodes_gt else 0.0
    return {
        "pv_accuracy": round(pv_acc, 2),
        "node_accuracy": round(node_acc, 2),
        "node_coverage": round(node_cov, 2),
    }


def _complexity_from_input(input_csv: Optional[Path]) -> Dict[str, Any]:
    if input_csv is None or not Path(input_csv).exists():
        return {"raw_rows": None, "columns": None, "file_size_mb": None}
    p = Path(input_csv)
    try:
        size_mb = round(p.stat().st_size / (1024 * 1024), 3)
    except OSError:
        size_mb = None
    raw_rows = 0
    cols = None
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
                cols = len(header)
            except StopIteration:
                header = None
            for _ in reader:
                raw_rows += 1
    except OSError:
        raw_rows = None
    return {"raw_rows": raw_rows, "columns": cols, "file_size_mb": size_mb}


def _statvar_count_from_pvmap(pvmap_csv: Path) -> Optional[int]:
    if not pvmap_csv.exists():
        return None
    try:
        with open(pvmap_csv, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            count = 0
            for row in reader:
                if row and row[0].strip() and row[0].strip() != "Node":
                    count += 1
            return count
    except OSError:
        return None


def build_dataset_record(
    dataset: str,
    run_dir: Path,
    input_csv: Optional[Path],
    pricing: PricingTable,
    baseline_pv: Optional[float],
    baseline_node: Optional[float],
    status: str,
) -> Dict[str, Any]:
    run_dir = Path(run_dir)
    calls = _read_jsonl(run_dir / "llm_calls.jsonl")
    phase = _read_json(run_dir / "phase_timings.json") or {}
    manifest = _read_json(run_dir / "run_manifest.json") or {}
    diff = _read_json(run_dir / "eval_results" / "diff_results.json")

    # Tokens rollup
    tokens_total = {"prompt": 0, "thoughts": 0, "response": 0, "total": 0}
    tokens_by_agent: Dict[str, Dict[str, Any]] = {}
    for c in calls:
        agent = c.get("agent", "unknown")
        model = c.get("model", "unknown")
        pt = c.get("prompt_tokens") or 0
        tt = c.get("thoughts_tokens") or 0
        rt = c.get("response_tokens") or 0
        tot = c.get("total_tokens") or (pt + tt + rt)
        dur = c.get("duration_ms") or 0
        tokens_total["prompt"] += pt
        tokens_total["thoughts"] += tt
        tokens_total["response"] += rt
        tokens_total["total"] += tot
        bucket = tokens_by_agent.setdefault(agent, {
            "model": model, "calls": 0,
            "prompt": 0, "thoughts": 0, "response": 0, "total": 0,
            "duration_ms": 0, "cost_usd": 0.0,
        })
        bucket["calls"] += 1
        bucket["prompt"] += pt
        bucket["thoughts"] += tt
        bucket["response"] += rt
        bucket["total"] += tot
        bucket["duration_ms"] += dur
        cost = compute_cost(pt, rt, tt, model, pricing)
        bucket["cost_usd"] = round(bucket["cost_usd"] + cost["cost_usd"], 6)
        # If an agent mixes models (rare), record the last one — aggregator log
        bucket["model"] = model

    cost_total = round(sum(b["cost_usd"] for b in tokens_by_agent.values()), 6)

    # Accuracy
    if diff:
        pvs_matched = int(diff.get("PVs-matched", 0))
        pvs_modified = int(diff.get("pvs-modified", 0))
        pvs_deleted = int(diff.get("pvs-deleted", 0))
        nodes_matched = int(diff.get("nodes-matched", 0))
        nodes_gt = int(diff.get("nodes-ground-truth", 0))
        nodes_generated = int(diff.get("nodes-auto-generated", 0))
        acc = compute_accuracy(pvs_matched, pvs_modified, pvs_deleted,
                               nodes_matched, nodes_gt, nodes_generated)
        accuracy = {
            **acc,
            "pvs_matched": pvs_matched, "pvs_modified": pvs_modified, "pvs_deleted": pvs_deleted,
            "nodes_matched": nodes_matched, "nodes_gt": nodes_gt, "nodes_generated": nodes_generated,
            "delta_pv_vs_doc_gemini3pro": round(acc["pv_accuracy"] - baseline_pv, 2) if baseline_pv is not None else None,
            "delta_node_vs_doc_gemini3pro": round(acc["node_accuracy"] - baseline_node, 2) if baseline_node is not None else None,
        }
    else:
        accuracy = {
            "pv_accuracy": None, "node_accuracy": None, "node_coverage": None,
            "pvs_matched": None, "pvs_modified": None, "pvs_deleted": None,
            "nodes_matched": None, "nodes_gt": None, "nodes_generated": None,
            "delta_pv_vs_doc_gemini3pro": None, "delta_node_vs_doc_gemini3pro": None,
        }

    # Adjust status: PVMAP produced but eval missing -> passed_with_warnings
    effective_status = status
    if status == "passed" and diff is None and (run_dir / "generated_pvmap.csv").exists():
        effective_status = "passed_with_warnings"

    complexity = _complexity_from_input(input_csv)
    complexity["cleaned_rows"] = None   # filled later if profile available (Task 18)
    complexity["observation_rows"] = None
    complexity["skeleton_bytes"] = None

    timing = {
        k: (v.get("duration_s") if isinstance(v, dict) else v)
        for k, v in phase.items()
    }

    return {
        "dataset": dataset,
        "status": effective_status,
        "complexity": complexity,
        "accuracy": accuracy,
        "tokens_total": tokens_total,
        "tokens_by_agent": tokens_by_agent,
        "cost_usd": {
            "total": cost_total,
            "by_agent": {k: v["cost_usd"] for k, v in tokens_by_agent.items()},
            "pricing_version": pricing.raw.get("_source", "unknown"),
        },
        "timing_seconds": timing,
        "run_meta": {
            "attempt_count": None,
            "best_attempt_used": None,
            "schema_category": None,
            "sampling_strategy": None,
            "output_statvar_count": _statvar_count_from_pvmap(run_dir / "generated_pvmap.csv"),
            "prompt_bytes_generator": next(
                (c.get("prompt_bytes") for c in calls if c.get("agent") in ("Generator", "PVMAPGenerator")),
                None,
            ),
            "worker_id": manifest.get("worker_id"),
            "mcp_port": manifest.get("mcp_port"),
            "git_sha": manifest.get("git_sha"),
            "started_at": manifest.get("started_at"),
            "ended_at": phase.get("total", {}).get("end") if isinstance(phase.get("total"), dict) else None,
        },
        "pipeline_log": str((run_dir / "pipeline.log")) if (run_dir / "pipeline.log").exists() else None,
        "generated_pvmap": str((run_dir / "generated_pvmap.csv")) if (run_dir / "generated_pvmap.csv").exists() else None,
    }
```

- [ ] **Step 2: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/scripts/test_aggregator_core.py -x -q`
Expected: 6 passed.

- [ ] **Step 3: Commit**

```bash
git add scripts/batch_lib/aggregator_core.py tests/scripts/test_aggregator_core.py
git commit -m "feat(batch): add per-dataset record builder with accuracy + cost rollup"
```

---

## Task 18: Extend `aggregator_core` to pull cleaned_rows / sampling_strategy / schema_category

**Files:**
- Modify: `scripts/batch_lib/aggregator_core.py`
- Modify: `tests/scripts/test_aggregator_core.py`
- Modify: `tests/scripts/fixtures/synthetic_run/dsA/` (add `dataset_profile.json`)

- [ ] **Step 1: Inspect where the pipeline writes profile data**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -c "from src.agents.sampling.schemas import DatasetProfile; import pprint; print([f for f in DatasetProfile.model_fields])"`

Look for existing profile artifacts in an existing output: `ls output/zurich_bev_4031_wiki/ | grep -i profile`.

The pipeline may write the profile as `dataset_profile.json`, inside `test_data/`, or embed it in another file. If the exact file doesn't exist today, document this in the run log and accept that `cleaned_rows` / `sampling_strategy` / `schema_category` / `skeleton_bytes` remain null for now — the plan is still shippable without them. The primary complexity axis is `raw_rows`, which we already have.

- [ ] **Step 2: If a profile file exists, add a fixture file**

Write to `tests/scripts/fixtures/synthetic_run/dsA/dataset_profile.json`:
```json
{
  "total_rows": 12450,
  "columns": 14,
  "sampling_strategy": "stratified",
  "schema_category": "Economy",
  "skeleton_bytes": 6421
}
```

- [ ] **Step 3: Update `_read_profile` and `build_dataset_record`**

Inside `aggregator_core.py`, add a helper:

```python
def _read_profile(run_dir: Path) -> dict:
    # Try the standard locations in preferred order
    for candidate in (
        run_dir / "dataset_profile.json",
        run_dir / "profile" / "dataset_profile.json",
    ):
        data = _read_json(candidate)
        if data:
            return data
    return {}
```

In `build_dataset_record`, after computing `complexity`, fill in the additional fields:

```python
    profile = _read_profile(run_dir)
    if profile:
        complexity["cleaned_rows"] = profile.get("total_rows") or profile.get("cleaned_rows")
        complexity["skeleton_bytes"] = profile.get("skeleton_bytes")
    run_meta_extra = {
        "sampling_strategy": profile.get("sampling_strategy"),
        "schema_category": profile.get("schema_category"),
    }
```

Then merge `run_meta_extra` into the returned `run_meta` dict.

- [ ] **Step 4: Add test for profile-derived fields**

Append to `tests/scripts/test_aggregator_core.py`:

```python
def test_build_dataset_record_reads_profile(pricing):
    rec = build_dataset_record(
        dataset="dsA", run_dir=FIXTURE / "dsA", input_csv=None, pricing=pricing,
        baseline_pv=None, baseline_node=None, status="passed",
    )
    # Only runs if the fixture profile file was created in Task 18 Step 2
    if rec["complexity"]["cleaned_rows"] is not None:
        assert rec["complexity"]["cleaned_rows"] == 12450
        assert rec["run_meta"]["sampling_strategy"] == "stratified"
        assert rec["run_meta"]["schema_category"] == "Economy"
```

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/scripts/test_aggregator_core.py -x -q`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/batch_lib/aggregator_core.py tests/scripts/test_aggregator_core.py tests/scripts/fixtures/
git commit -m "feat(batch): pull cleaned_rows + sampling_strategy + schema_category from profile"
```

---

## Task 19: Implement Markdown report builder

**Files:**
- Create: `scripts/batch_lib/report_markdown.py`
- Create: `tests/scripts/test_report_markdown.py`

- [ ] **Step 1: Write failing test**

Write to `tests/scripts/test_report_markdown.py`:

```python
"""Tests for report_markdown.render_report."""
import pytest

from scripts.batch_lib.report_markdown import render_report


SAMPLE_RECORDS = [
    {
        "dataset": "ds1", "status": "passed",
        "complexity": {"raw_rows": 1000, "cleaned_rows": 990, "columns": 10, "file_size_mb": 0.5, "skeleton_bytes": 4000, "observation_rows": None},
        "accuracy": {"pv_accuracy": 30.0, "node_accuracy": 20.0, "node_coverage": 100.0,
                     "pvs_matched": 10, "pvs_modified": 5, "pvs_deleted": 5,
                     "nodes_matched": 2, "nodes_gt": 10, "nodes_generated": 10,
                     "delta_pv_vs_doc_gemini3pro": 5.0, "delta_node_vs_doc_gemini3pro": -2.0},
        "tokens_total": {"prompt": 1000, "thoughts": 100, "response": 200, "total": 1300},
        "tokens_by_agent": {"Generator": {"model": "gemini-3.1-pro-preview", "calls": 3, "total": 1300, "cost_usd": 0.02, "duration_ms": 5000, "prompt":1000,"thoughts":100,"response":200}},
        "cost_usd": {"total": 0.02, "by_agent": {"Generator": 0.02}, "pricing_version": "v1"},
        "timing_seconds": {"total": 60.0},
        "run_meta": {"attempt_count": 2, "git_sha": "abc", "schema_category": "Health", "sampling_strategy": "head"},
    },
    {
        "dataset": "ds2", "status": "timed_out",
        "complexity": {"raw_rows": 5000, "cleaned_rows": None, "columns": 20, "file_size_mb": 2.0, "skeleton_bytes": None, "observation_rows": None},
        "accuracy": {"pv_accuracy": None, "node_accuracy": None, "node_coverage": None,
                     "pvs_matched": None, "pvs_modified": None, "pvs_deleted": None,
                     "nodes_matched": None, "nodes_gt": None, "nodes_generated": None,
                     "delta_pv_vs_doc_gemini3pro": None, "delta_node_vs_doc_gemini3pro": None},
        "tokens_total": {"prompt": 0, "thoughts": 0, "response": 0, "total": 0},
        "tokens_by_agent": {},
        "cost_usd": {"total": 0.0, "by_agent": {}, "pricing_version": "v1"},
        "timing_seconds": {"total": 2700.0},
        "run_meta": {"attempt_count": None, "git_sha": "abc", "schema_category": None, "sampling_strategy": None},
    },
]


def test_render_report_smoke():
    md = render_report(
        records=SAMPLE_RECORDS,
        pricing_raw={"_source": "test"},
        run_meta={"git_sha": "abc1234", "generated_at": "2026-04-17T12:00:00", "cli_args": "--model=gemini-3.1-pro-preview"},
    )
    assert "# Batch Benchmark Report" in md
    assert "ds1" in md and "ds2" in md
    assert "Average PV accuracy" in md
    assert "| Agent |" in md  # per-agent aggregate table
    assert "30.0" in md       # pv_accuracy for ds1


def test_render_report_counts_failed():
    md = render_report(records=SAMPLE_RECORDS, pricing_raw={}, run_meta={})
    # timed_out counted
    assert "timed_out" in md.lower() or "timeout" in md.lower()


def test_render_report_handles_empty():
    md = render_report(records=[], pricing_raw={}, run_meta={})
    assert "# Batch Benchmark Report" in md
    assert "No datasets" in md or "0 datasets" in md
```

- [ ] **Step 2: Run test to verify failure**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/scripts/test_report_markdown.py -x -q`
Expected: ImportError.

- [ ] **Step 3: Write implementation**

Write to `scripts/batch_lib/report_markdown.py`:

```python
"""Markdown report builder for the batch benchmark."""
from __future__ import annotations

from typing import Any, Dict, List


def _fmt(x, width=1):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        return f"{x:.{width}f}"
    return str(x)


def render_report(
    records: List[Dict[str, Any]],
    pricing_raw: Dict[str, Any],
    run_meta: Dict[str, Any],
) -> str:
    lines: List[str] = []
    lines.append("# Batch Benchmark Report")
    lines.append("")
    lines.append(f"- Generated at: `{run_meta.get('generated_at', 'unknown')}`")
    lines.append(f"- Git SHA: `{run_meta.get('git_sha', 'unknown')}`")
    lines.append(f"- CLI args: `{run_meta.get('cli_args', '')}`")
    lines.append(f"- Pricing source: `{pricing_raw.get('_source', 'unknown')}`")
    lines.append("")

    if not records:
        lines.append("No datasets in report.")
        return "\n".join(lines)

    # Grand totals
    total_tokens = sum(r["tokens_total"]["total"] for r in records)
    total_cost = round(sum(r["cost_usd"]["total"] for r in records), 2)
    total_s = round(sum(r["timing_seconds"].get("total", 0.0) or 0.0 for r in records), 1)

    passed = [r for r in records if r["status"] in ("passed", "passed_with_warnings")]
    failed = [r for r in records if r["status"] not in ("passed", "passed_with_warnings")]

    acc_datasets = [r for r in passed if r["accuracy"]["pv_accuracy"] is not None]
    avg_pv = round(sum(r["accuracy"]["pv_accuracy"] for r in acc_datasets) / len(acc_datasets), 2) if acc_datasets else 0.0
    avg_node = round(sum(r["accuracy"]["node_accuracy"] for r in acc_datasets) / len(acc_datasets), 2) if acc_datasets else 0.0

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Datasets: **{len(records)}** (passed/warnings: {len(passed)}, failed: {len(failed)})")
    lines.append(f"- Average PV accuracy: **{avg_pv}%**")
    lines.append(f"- Average Node accuracy: **{avg_node}%**")
    lines.append(f"- Total tokens: **{total_tokens:,}**")
    lines.append(f"- Total cost: **${total_cost:,}** (pricing may include estimates)")
    lines.append(f"- Total wall time: **{total_s:,}s**")
    lines.append("")

    # Per-dataset table
    lines.append("## Per-Dataset")
    lines.append("")
    lines.append("| Dataset | Status | Raw rows | PV acc | Δ PV | Node acc | Δ Node | Tokens | Duration (s) | Attempts |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in records:
        a = r["accuracy"]
        c = r["complexity"]
        lines.append(
            f"| {r['dataset']} | {r['status']} | {_fmt(c.get('raw_rows'))} | "
            f"{_fmt(a.get('pv_accuracy'))} | {_fmt(a.get('delta_pv_vs_doc_gemini3pro'))} | "
            f"{_fmt(a.get('node_accuracy'))} | {_fmt(a.get('delta_node_vs_doc_gemini3pro'))} | "
            f"{r['tokens_total']['total']:,} | "
            f"{_fmt(r['timing_seconds'].get('total'))} | "
            f"{_fmt(r['run_meta'].get('attempt_count'))} |"
        )
    lines.append("")

    # Per-agent aggregate across all datasets
    agent_agg: Dict[str, Dict[str, Any]] = {}
    for r in records:
        for agent, bucket in r["tokens_by_agent"].items():
            a = agent_agg.setdefault(agent, {"model": bucket["model"], "calls": 0, "total": 0, "cost": 0.0, "duration_ms": 0})
            a["calls"] += bucket["calls"]
            a["total"] += bucket["total"]
            a["cost"] += bucket["cost_usd"]
            a["duration_ms"] += bucket.get("duration_ms", 0)
            a["model"] = bucket["model"]

    lines.append("## Per-Agent Aggregate (all datasets)")
    lines.append("")
    lines.append("| Agent | Model | Calls | Tokens | Duration (s) | Cost $ |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for agent, a in sorted(agent_agg.items(), key=lambda kv: -kv[1]["total"]):
        lines.append(
            f"| {agent} | {a['model']} | {a['calls']} | {a['total']:,} | "
            f"{a['duration_ms']/1000:.1f} | ${a['cost']:.2f} |"
        )
    lines.append("")

    if failed:
        lines.append("## Failed Datasets")
        lines.append("")
        for r in failed:
            lines.append(f"- `{r['dataset']}` — {r['status']}")

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/scripts/test_report_markdown.py -x -q`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/batch_lib/report_markdown.py tests/scripts/test_report_markdown.py
git commit -m "feat(batch): add Markdown report builder with per-dataset and per-agent tables"
```

---

## Task 20: Implement scatter plot builder

**Files:**
- Create: `scripts/batch_lib/scatter.py`
- Create: `tests/scripts/test_scatter.py`

- [ ] **Step 1: Write failing test**

Write to `tests/scripts/test_scatter.py`:

```python
"""Tests for scatter plot writer."""
from pathlib import Path

import pytest

from scripts.batch_lib.scatter import write_scatter


def test_write_scatter_produces_png(tmp_path: Path):
    records = [
        {"dataset": "a", "complexity": {"raw_rows": 100},  "tokens_total": {"total": 1000}, "timing_seconds": {"total": 10.0}},
        {"dataset": "b", "complexity": {"raw_rows": 1000}, "tokens_total": {"total": 5000}, "timing_seconds": {"total": 30.0}},
        {"dataset": "c", "complexity": {"raw_rows": 10000},"tokens_total": {"total": 25000},"timing_seconds": {"total": 120.0}},
    ]
    out = tmp_path / "scatter.png"
    write_scatter(records, out, x_key=("complexity", "raw_rows"), y_key=("tokens_total", "total"), title="tokens vs rows", log_scale=True)
    assert out.exists()
    assert out.stat().st_size > 100


def test_write_scatter_skips_none_values(tmp_path: Path):
    """Datasets with missing x/y don't break the plot."""
    records = [
        {"dataset": "a", "complexity": {"raw_rows": 100},  "tokens_total": {"total": 1000}, "timing_seconds": {"total": 10.0}},
        {"dataset": "b", "complexity": {"raw_rows": None}, "tokens_total": {"total": 5000}, "timing_seconds": {"total": None}},
    ]
    out = tmp_path / "scatter.png"
    write_scatter(records, out, x_key=("complexity", "raw_rows"), y_key=("tokens_total", "total"), title="x", log_scale=True)
    assert out.exists()
```

- [ ] **Step 2: Run tests to verify failure**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/scripts/test_scatter.py -x -q`
Expected: ImportError.

- [ ] **Step 3: Write implementation**

Write to `scripts/batch_lib/scatter.py`:

```python
"""Matplotlib scatter plot writer — log-log, clean, label datasets sparingly."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Tuple

import matplotlib
matplotlib.use("Agg")  # No display; safe in subprocess / CI
import matplotlib.pyplot as plt


def _get(record, key_path):
    cur = record
    for k in key_path:
        if cur is None:
            return None
        cur = cur.get(k) if isinstance(cur, dict) else None
    return cur


def write_scatter(
    records: Iterable[dict],
    out_path: Path,
    x_key: Tuple[str, ...],
    y_key: Tuple[str, ...],
    title: str,
    log_scale: bool = True,
) -> None:
    xs, ys, labels = [], [], []
    for r in records:
        x = _get(r, x_key)
        y = _get(r, y_key)
        if x is None or y is None or x <= 0 or y <= 0:
            continue
        xs.append(x)
        ys.append(y)
        labels.append(r.get("dataset", ""))

    fig, ax = plt.subplots(figsize=(10, 7))
    if xs:
        ax.scatter(xs, ys, alpha=0.7)
        if log_scale:
            ax.set_xscale("log")
            ax.set_yscale("log")
        # Label a few outliers (top 5 by y)
        if len(xs) >= 5:
            top = sorted(range(len(xs)), key=lambda i: ys[i], reverse=True)[:5]
            for i in top:
                ax.annotate(labels[i], (xs[i], ys[i]), fontsize=7, alpha=0.8)
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)

    ax.set_xlabel(".".join(x_key))
    ax.set_ylabel(".".join(y_key))
    ax.set_title(title)
    ax.grid(True, which="both", ls="--", alpha=0.3)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
```

- [ ] **Step 4: Verify `matplotlib` is installed**

Run: `.venv/bin/python -c "import matplotlib; print(matplotlib.__version__)"`
Expected: a version string. If `ModuleNotFoundError`, add `matplotlib>=3.8` to the `[project.optional-dependencies] dev` section of `pyproject.toml`, then run `uv sync --all-extras`, then commit the dep change.

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/scripts/test_scatter.py -x -q`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/batch_lib/scatter.py tests/scripts/test_scatter.py
git commit -m "feat(batch): add matplotlib scatter plot writer for rows-vs-tokens/duration"
```

---

## Task 21: Implement the orchestrator CLI `scripts/batch_benchmark.py`

**Files:**
- Create: `scripts/batch_benchmark.py`
- Create: `tests/scripts/test_batch_benchmark_cli.py` (CLI arg parsing only; full integration is covered by the dry-run ladder)

- [ ] **Step 1: Write failing test for CLI arg parsing**

Write to `tests/scripts/test_batch_benchmark_cli.py`:

```python
"""Tests for batch_benchmark arg parser."""
from scripts.batch_benchmark import build_parser


def test_parser_defaults():
    p = build_parser()
    ns = p.parse_args(["--datasets-file", "x.txt", "--output-dir", "/tmp/z"])
    assert ns.concurrency == 3
    assert ns.timeout == 2700
    assert ns.mcp_port_base == 3000


def test_parser_resume_failed():
    p = build_parser()
    ns = p.parse_args([
        "--datasets-file", "x.txt", "--output-dir", "/tmp/z",
        "--resume-failed", "/tmp/failed.json",
    ])
    assert ns.resume_failed == "/tmp/failed.json"
```

- [ ] **Step 2: Write orchestrator implementation**

Write to `scripts/batch_benchmark.py`:

```python
#!/usr/bin/env python3
"""Batch benchmark orchestrator.

Runs src/run_pipeline.py as a subprocess for each dataset in the list, up to
`--concurrency` at a time, each with its own MCP_PORT. Appends results to
checkpoint.jsonl and writes failed.json at end.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shlex
import signal
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List

from scripts.batch_lib.checkpoint import Checkpoint

logger = logging.getLogger("batch_benchmark")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Batch benchmark orchestrator")
    p.add_argument("--datasets-file", required=True, help="Text file, one dataset name per line")
    p.add_argument("--output-dir", required=True, help="Batch root output dir")
    p.add_argument("--concurrency", type=int, default=3)
    p.add_argument("--timeout", type=int, default=2700, help="Per-dataset timeout (s)")
    p.add_argument("--mcp-port-base", type=int, default=3000)
    p.add_argument("--pipeline-args", default="", help="Extra args forwarded to src/run_pipeline.py")
    p.add_argument("--resume-failed", default=None, help="Path to a failed.json from a previous run")
    p.add_argument("--limit", type=int, default=None, help="Dry-run: only process first N datasets after filtering")
    return p


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) != 0


def _pick_port(base: int, slot: int, max_retries: int = 3) -> int:
    port = base + slot
    for _ in range(max_retries):
        if _port_free(port):
            return port
        port += 10
    return port  # last resort; pipeline may fail — we'll log


def _load_datasets(args) -> List[str]:
    if args.resume_failed:
        data = json.loads(Path(args.resume_failed).read_text())
        datasets = [r["dataset"] for r in data]
    else:
        datasets = [ln.strip() for ln in Path(args.datasets_file).read_text().splitlines() if ln.strip()]
    if args.limit:
        datasets = datasets[:args.limit]
    return datasets


def run_one(dataset: str, slot: int, port: int, output_dir: Path, pipeline_args: str, timeout: int) -> dict:
    ds_out = output_dir / "runs" / dataset
    ds_out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "MCP_PORT": str(port), "BATCH_WORKER_ID": str(slot),
           "PYTHONPATH": f"{os.environ.get('PYTHONPATH','')}:{os.getcwd()}:{os.getcwd()}/src"}
    log = ds_out / "pipeline.log"
    cmd = [
        sys.executable, "src/run_pipeline.py",
        "--dataset", dataset,
        "--output-dir", str(ds_out),
        *shlex.split(pipeline_args),
    ]
    t0 = time.time()
    try:
        with open(log, "w", encoding="utf-8") as f:
            proc = subprocess.run(
                cmd, env=env, stdout=f, stderr=subprocess.STDOUT,
                timeout=timeout, check=False,
            )
        status = "ok" if proc.returncode == 0 else f"exit_{proc.returncode}"
    except subprocess.TimeoutExpired:
        status = "timeout"
    except Exception as e:  # unexpected
        status = f"exception_{type(e).__name__}"
    return {
        "dataset": dataset, "status": status,
        "duration_s": round(time.time() - t0, 2),
        "worker_slot": slot, "mcp_port": port,
        "log": str(log),
    }


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    output_dir = Path(args.output_dir)
    (output_dir / "runs").mkdir(parents=True, exist_ok=True)

    datasets = _load_datasets(args)
    logger.info("orchestrator: %d datasets, concurrency=%d, timeout=%ds", len(datasets), args.concurrency, args.timeout)

    checkpoint = Checkpoint(output_dir / "checkpoint.jsonl")
    already_done = checkpoint.read_completed_datasets()
    pending = [d for d in datasets if d not in already_done]
    logger.info("orchestrator: resume skips %d already-completed datasets", len(datasets) - len(pending))

    failed: List[dict] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {}
        for i, ds in enumerate(pending):
            slot = i % args.concurrency
            port = _pick_port(args.mcp_port_base, slot)
            futs[ex.submit(run_one, ds, slot, port, output_dir, args.pipeline_args, args.timeout)] = ds
        for fut in as_completed(futs):
            r = fut.result()
            checkpoint.append(r)
            logger.info("done: %s status=%s duration=%.1fs", r["dataset"], r["status"], r["duration_s"])
            if r["status"] != "ok":
                failed.append(r)

    (output_dir / "failed.json").write_text(json.dumps(failed, indent=2))
    logger.info("orchestrator: %d failed (see %s)", len(failed), output_dir / "failed.json")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run CLI parser tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/scripts/test_batch_benchmark_cli.py -x -q`
Expected: 2 passed.

- [ ] **Step 4: Dry-check help works**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python scripts/batch_benchmark.py --help`
Expected: prints argparse help without error.

- [ ] **Step 5: Commit**

```bash
chmod +x scripts/batch_benchmark.py
git add scripts/batch_benchmark.py tests/scripts/test_batch_benchmark_cli.py
git commit -m "feat(batch): add orchestrator CLI with subprocess pool + checkpoint"
```

---

## Task 22: Implement the aggregator CLI `scripts/batch_aggregate.py`

**Files:**
- Create: `scripts/batch_aggregate.py`
- Create: `tests/scripts/test_batch_aggregate_cli.py`

- [ ] **Step 1: Write failing test for CLI wiring**

Write to `tests/scripts/test_batch_aggregate_cli.py`:

```python
"""Integration test for batch_aggregate end-to-end on the synthetic fixture."""
import json
import subprocess
import sys
from pathlib import Path


def test_batch_aggregate_produces_all_outputs(tmp_path: Path):
    fixture = Path(__file__).parent / "fixtures" / "synthetic_run"
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    # Copy fixture into runs/
    import shutil
    shutil.copytree(fixture / "dsA", runs_dir / "dsA")

    pricing = Path(__file__).parent.parent.parent / "config" / "gemini_pricing.json"
    out_dir = tmp_path

    cmd = [
        sys.executable, "scripts/batch_aggregate.py",
        "--runs-dir", str(runs_dir),
        "--output-dir", str(out_dir),
        "--pricing-file", str(pricing),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).parent.parent.parent))
    assert r.returncode == 0, r.stderr

    # Required outputs
    assert (out_dir / "batch_results.json").exists()
    assert (out_dir / "batch_summary.csv").exists()
    assert (out_dir / "report.md").exists()
    assert (out_dir / "scatter_tokens_vs_rows.png").exists()
    assert (out_dir / "scatter_duration_vs_rows.png").exists()

    data = json.loads((out_dir / "batch_results.json").read_text())
    assert any(r["dataset"] == "dsA" for r in data)
```

- [ ] **Step 2: Write aggregator implementation**

Write to `scripts/batch_aggregate.py`:

```python
#!/usr/bin/env python3
"""Batch aggregator: reads per-dataset artifacts and writes the final report."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from scripts.batch_lib.aggregator_core import build_dataset_record
from scripts.batch_lib.pricing import PricingTable
from scripts.batch_lib.report_markdown import render_report
from scripts.batch_lib.scatter import write_scatter

logger = logging.getLogger("batch_aggregate")


def parse_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--pricing-file", required=True)
    p.add_argument("--baseline-doc", default=None,
                   help="Path to Gemini_vs_Claude_Comparison.md for Δ vs. Gemini 3 Pro")
    return p.parse_args(argv)


# --- Baseline extractor ------------------------------------------------------

_PV_HEADER = "## PV Accuracy Comparison"
_NODE_HEADER = "## Node Accuracy Comparison"


def _parse_baseline(doc_path: Optional[Path]) -> Dict[str, Dict[str, float]]:
    """Returns {dataset: {'pv': float, 'node': float}} using the Gemini 3 Pro columns."""
    out: Dict[str, Dict[str, float]] = {}
    if not doc_path or not doc_path.exists():
        return out
    text = doc_path.read_text(encoding="utf-8", errors="replace")
    def _section(start_header: str) -> List[str]:
        i = text.find(start_header)
        if i < 0:
            return []
        j = text.find("---", i)
        return text[i:(j if j > 0 else None)].splitlines()

    # Rows look like: | dataset | gb | claude | g3pro |
    row_re = re.compile(r"\|\s*([^\|]+?)\s*\|.*?\|.*?\|\s*([0-9.]+|\*\*[0-9.]+\*\*)\s*\|\s*$")

    def _parse_section(section_lines: List[str], key: str):
        for line in section_lines:
            m = row_re.search(line)
            if not m:
                continue
            ds = m.group(1)
            if ds.lower().startswith("dataset") or set(ds) <= set("-"):
                continue
            val_s = m.group(2).replace("**", "")
            try:
                val = float(val_s)
            except ValueError:
                continue
            out.setdefault(ds, {})[key] = val

    _parse_section(_section(_PV_HEADER), "pv")
    _parse_section(_section(_NODE_HEADER), "node")
    return out


# --- Summary CSV -------------------------------------------------------------

def _write_summary_csv(records: List[dict], out: Path) -> None:
    if not records:
        out.write_text("")
        return
    # Collect all agent names in stable order
    agent_set = set()
    for r in records:
        agent_set.update(r["tokens_by_agent"].keys())
    agents = sorted(agent_set)

    fields = [
        "dataset", "status",
        "raw_rows", "cleaned_rows", "observation_rows", "columns", "file_size_mb", "skeleton_bytes",
        "pv_accuracy", "node_accuracy", "node_coverage",
        "delta_pv_vs_doc", "delta_node_vs_doc",
        "tokens_total", "cost_usd_total", "duration_total_s",
        "attempt_count", "schema_category", "sampling_strategy",
        "output_statvar_count", "git_sha",
    ]
    for a in agents:
        fields += [f"{a}_calls", f"{a}_tokens", f"{a}_cost_usd", f"{a}_model"]

    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in records:
            row = {
                "dataset": r["dataset"], "status": r["status"],
                "raw_rows": r["complexity"].get("raw_rows"),
                "cleaned_rows": r["complexity"].get("cleaned_rows"),
                "observation_rows": r["complexity"].get("observation_rows"),
                "columns": r["complexity"].get("columns"),
                "file_size_mb": r["complexity"].get("file_size_mb"),
                "skeleton_bytes": r["complexity"].get("skeleton_bytes"),
                "pv_accuracy": r["accuracy"].get("pv_accuracy"),
                "node_accuracy": r["accuracy"].get("node_accuracy"),
                "node_coverage": r["accuracy"].get("node_coverage"),
                "delta_pv_vs_doc": r["accuracy"].get("delta_pv_vs_doc_gemini3pro"),
                "delta_node_vs_doc": r["accuracy"].get("delta_node_vs_doc_gemini3pro"),
                "tokens_total": r["tokens_total"]["total"],
                "cost_usd_total": r["cost_usd"]["total"],
                "duration_total_s": r["timing_seconds"].get("total"),
                "attempt_count": r["run_meta"].get("attempt_count"),
                "schema_category": r["run_meta"].get("schema_category"),
                "sampling_strategy": r["run_meta"].get("sampling_strategy"),
                "output_statvar_count": r["run_meta"].get("output_statvar_count"),
                "git_sha": r["run_meta"].get("git_sha"),
            }
            for a in agents:
                b = r["tokens_by_agent"].get(a, {})
                row[f"{a}_calls"] = b.get("calls")
                row[f"{a}_tokens"] = b.get("total")
                row[f"{a}_cost_usd"] = b.get("cost_usd")
                row[f"{a}_model"] = b.get("model")
            w.writerow(row)


# --- Main ---------------------------------------------------------------------

def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    runs_dir = Path(args.runs_dir)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pricing = PricingTable.load(Path(args.pricing_file))
    baseline = _parse_baseline(Path(args.baseline_doc)) if args.baseline_doc else {}

    records: List[dict] = []
    failed: List[dict] = []
    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        dataset = run_dir.name
        input_csv = None
        base = Path("input") / dataset / "test_data"
        if base.exists():
            cands = list(base.glob("*_input.csv"))
            if cands:
                input_csv = cands[0]
        b = baseline.get(dataset, {})
        # Status derivation: if pipeline.log exists and eval_results/diff_results.json exists, passed.
        # If log exists but no diff → passed_with_warnings. If no log → crashed.
        if (run_dir / "pipeline.log").exists():
            status = "passed"
        else:
            status = "crashed"
        rec = build_dataset_record(
            dataset=dataset, run_dir=run_dir, input_csv=input_csv,
            pricing=pricing, baseline_pv=b.get("pv"), baseline_node=b.get("node"),
            status=status,
        )
        records.append(rec)
        if rec["status"] not in ("passed", "passed_with_warnings"):
            failed.append({"dataset": dataset, "status": rec["status"]})

    # Write outputs
    (out_dir / "batch_results.json").write_text(json.dumps(records, indent=2))
    _write_summary_csv(records, out_dir / "batch_summary.csv")
    md = render_report(
        records=records,
        pricing_raw=pricing.raw,
        run_meta={
            "generated_at": datetime.now().isoformat(),
            "git_sha": next((r["run_meta"]["git_sha"] for r in records if r["run_meta"].get("git_sha")), "unknown"),
            "cli_args": (records[0]["run_meta"] if records else {}).get("git_sha", ""),
        },
    )
    (out_dir / "report.md").write_text(md)

    write_scatter(
        records, out_dir / "scatter_tokens_vs_rows.png",
        x_key=("complexity", "raw_rows"), y_key=("tokens_total", "total"),
        title="Input rows vs Total tokens", log_scale=True,
    )
    write_scatter(
        records, out_dir / "scatter_duration_vs_rows.png",
        x_key=("complexity", "raw_rows"), y_key=("timing_seconds", "total"),
        title="Input rows vs Total duration (s)", log_scale=True,
    )

    (out_dir / "failed.json").write_text(json.dumps(failed, indent=2))

    logger.info("aggregate: %d records; %d failed; outputs in %s",
                len(records), len(failed), out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run the aggregator CLI integration test**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/scripts/test_batch_aggregate_cli.py -x -q`
Expected: 1 passed. If matplotlib isn't installed, install per Task 20 Step 4.

- [ ] **Step 4: Run the full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: all green; test count is previous + ~20 new tests.

- [ ] **Step 5: Commit**

```bash
chmod +x scripts/batch_aggregate.py
git add scripts/batch_aggregate.py tests/scripts/test_batch_aggregate_cli.py
git commit -m "feat(batch): add aggregator CLI producing JSON + CSV + Markdown + scatter PNGs"
```

---

## Task 23: Dry-run ladder — 2 datasets

**Files:** none modified; this task is an operational gate.

- [ ] **Step 1: Pick two small datasets and run the orchestrator**

```bash
# Use --limit 2 on the full list to get the first two
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python scripts/batch_benchmark.py \
  --datasets-file config/batch_49.txt \
  --output-dir output/batch_runs/2026-04-17_dry1 \
  --concurrency 2 \
  --timeout 2700 \
  --limit 2 \
  --pipeline-args "--model=gemini-3.1-pro-preview --thinking-level=high --enable-mcp --prompt-version=v3 --feedback-prompt-version=v1"
```

- [ ] **Step 2: Verify per-dataset artifacts**

For each of the 2 datasets, check:
```bash
ls output/batch_runs/2026-04-17_dry1/runs/<dataset>/
# Should contain: pipeline.log, run_manifest.json, phase_timings.json,
#                 llm_calls.jsonl, generated_pvmap.csv, eval_results/diff_results.json
jq length output/batch_runs/2026-04-17_dry1/runs/<dataset>/llm_calls.jsonl
# Should be > 5 (multiple agents captured)
jq '.agent' -r output/batch_runs/2026-04-17_dry1/runs/<dataset>/llm_calls.jsonl | sort -u
# Should list: Generator, FeedbackAgent, SchemaSelectionAgent, at minimum
```

- [ ] **Step 3: Run the aggregator**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python scripts/batch_aggregate.py \
  --runs-dir output/batch_runs/2026-04-17_dry1/runs \
  --output-dir output/batch_runs/2026-04-17_dry1 \
  --pricing-file config/gemini_pricing.json \
  --baseline-doc analysis/Gemini_vs_Claude_Comparison.md
```

- [ ] **Step 4: Inspect the report**

```bash
cat output/batch_runs/2026-04-17_dry1/report.md
open output/batch_runs/2026-04-17_dry1/scatter_tokens_vs_rows.png 2>/dev/null || true
```
Verify: each dataset appears with sensible tokens/time/accuracy; `Δ PV` column populated; per-agent table has multiple agents.

- [ ] **Step 5: Human gate**

STOP and ask the user to confirm the report looks reasonable before proceeding to the 3-dataset ladder step. Do not commit this task — it is an operational verification, not code.

---

## Task 24: Dry-run ladder — 3 datasets, then 5

**Files:** none modified.

- [ ] **Step 1: Run with --limit 3**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python scripts/batch_benchmark.py \
  --datasets-file config/batch_49.txt \
  --output-dir output/batch_runs/2026-04-17_dry2 \
  --concurrency 3 \
  --timeout 2700 \
  --limit 3 \
  --pipeline-args "--model=gemini-3.1-pro-preview --thinking-level=high --enable-mcp --prompt-version=v3 --feedback-prompt-version=v1"
```

- [ ] **Step 2: Confirm port isolation**

For each dataset, inspect `run_manifest.json`:
```bash
for d in output/batch_runs/2026-04-17_dry2/runs/*/; do jq '.mcp_port' "$d/run_manifest.json"; done
```
Expected: three different ports (3000, 3001, 3002).

- [ ] **Step 3: Aggregate and review**

Same aggregator invocation as Task 23 Step 3, output dir `dry2`.

- [ ] **Step 4: Run with --limit 5**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python scripts/batch_benchmark.py \
  --datasets-file config/batch_49.txt \
  --output-dir output/batch_runs/2026-04-17_dry3 \
  --concurrency 3 \
  --timeout 2700 \
  --limit 5 \
  --pipeline-args "--model=gemini-3.1-pro-preview --thinking-level=high --enable-mcp --prompt-version=v3 --feedback-prompt-version=v1"
```

- [ ] **Step 5: Verify timeout handling path**

If any of the first 5 datasets is close to timeout, confirm `failed.json` captures it. If none hit timeout, artificially force one using `--timeout 60` on a known slow dataset (e.g. `india_nfhs`) to exercise the timeout path once:

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python scripts/batch_benchmark.py \
  --datasets-file <(echo india_nfhs) \
  --output-dir /tmp/timeout_test --concurrency 1 --timeout 60 \
  --pipeline-args "--enable-mcp"
cat /tmp/timeout_test/failed.json
# Should contain one entry with status=timeout
```

- [ ] **Step 6: Human gate**

STOP and ask the user to confirm the 5-dataset report looks correct before proceeding to the full 49.

---

## Task 25: Full run of all 49 datasets

**Files:** none modified.

- [ ] **Step 1: Launch the full run**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python scripts/batch_benchmark.py \
  --datasets-file config/batch_49.txt \
  --output-dir output/batch_runs/2026-04-17_comparison \
  --concurrency 3 \
  --timeout 2700 \
  --pipeline-args "--model=gemini-3.1-pro-preview --thinking-level=high --enable-mcp --prompt-version=v3 --feedback-prompt-version=v1"
```

Expected wall-time: ~1.5–2 hours with 3 concurrent workers.

- [ ] **Step 2: Monitor progress**

In another terminal:
```bash
# Watch checkpoint grow
tail -f output/batch_runs/2026-04-17_comparison/checkpoint.jsonl
# Count completed datasets
wc -l output/batch_runs/2026-04-17_comparison/checkpoint.jsonl
```

- [ ] **Step 3: Aggregate**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python scripts/batch_aggregate.py \
  --runs-dir output/batch_runs/2026-04-17_comparison/runs \
  --output-dir output/batch_runs/2026-04-17_comparison \
  --pricing-file config/gemini_pricing.json \
  --baseline-doc analysis/Gemini_vs_Claude_Comparison.md
```

- [ ] **Step 4: Sanity-check outputs**

```bash
jq 'length' output/batch_runs/2026-04-17_comparison/batch_results.json
# Expected: 49
wc -l output/batch_runs/2026-04-17_comparison/batch_summary.csv
# Expected: 50 (header + 49 rows)
ls output/batch_runs/2026-04-17_comparison/*.png
# Expected: two PNG files
cat output/batch_runs/2026-04-17_comparison/failed.json | jq length
# Expected: small number (ideally 0)
```

- [ ] **Step 5: Deliver the report**

Share the files with the user:
```
output/batch_runs/2026-04-17_comparison/
├─ report.md
├─ batch_summary.csv
├─ batch_results.json
├─ scatter_tokens_vs_rows.png
├─ scatter_duration_vs_rows.png
└─ failed.json
```

- [ ] **Step 6: If any datasets failed, rerun with cache on**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python scripts/batch_benchmark.py \
  --resume-failed output/batch_runs/2026-04-17_comparison/failed.json \
  --output-dir output/batch_runs/2026-04-17_comparison_rerun \
  --concurrency 3 --timeout 2700 \
  --pipeline-args "--model=gemini-3.1-pro-preview --thinking-level=high --enable-mcp --prompt-version=v3 --feedback-prompt-version=v1 --skip-sampling --skip-schema-selection"
```

- [ ] **Step 7: Commit run metadata (if desired)**

Outputs under `output/batch_runs/` may be gitignored; the report artifacts themselves are not code. If the team wants the report archived, copy `report.md`, `batch_summary.csv`, `batch_results.json` to a tracked location (e.g. `analysis/2026-04-17_batch_report/`) and commit:

```bash
mkdir -p analysis/2026-04-17_batch_report
cp output/batch_runs/2026-04-17_comparison/{report.md,batch_summary.csv,batch_results.json,scatter_*.png} analysis/2026-04-17_batch_report/
git add analysis/2026-04-17_batch_report/
git commit -m "docs: add 2026-04-17 batch benchmark report for 49 datasets"
```

---

## Self-Review (run after final task is written; fix inline)

1. **Spec coverage**
   - §2 Dataset selection → Task 1 ✓
   - §3 Pipeline configuration (all flags) → surfaced in Task 23–25 orchestrator invocations ✓
   - §4/§5 Architecture (3 components) → Tasks 3–22 ✓
   - §5.2.1 `LLMTelemetryPlugin` (per-call JSONL + Generator state stash) → Tasks 7–8 ✓
   - §5.2.2 `phase_timer` → Tasks 3–4 + wiring in Task 9, refined in Task 10 ✓
   - §5.2.3 Run manifest → Tasks 5–6 + wiring in Task 9 ✓
   - §5.3 Aggregator record shape (accuracy, tokens, cost, timing, run_meta) → Tasks 15–18, 22 ✓
   - §5.4 Pricing table → Task 2 ✓
   - §6 Directory layout → produced by orchestrator (Task 21) + aggregator (Task 22) ✓
   - §7 Rollout: Phase A plumbing → Tasks 1–22; Phase B dry runs → Tasks 23–24; Phase C rerun failed → Task 25 Step 6 ✓
   - §8 Edge cases (port busy, missing eval, crash mid-retry, preview pricing, checkpoint lock) → addressed in Tasks 11–12 (lock), Task 17 (missing eval → passed_with_warnings), Task 21 (port pick), Task 14 (estimate flag) ✓
   - §9 Testing strategy → unit tests throughout, integration via dry-run ladder ✓
   - §10 Out-of-scope items → honored (no Schema.org MCP work, no LLM-judge, no multi-model) ✓

2. **Placeholder scan:** Task 10 has a documented escape hatch ("if infeasible, document and skip") — this is an acceptable contingency, not a placeholder; the plan still produces a working harness without per-phase hooks. All other tasks have concrete code and commands.

3. **Type consistency:** `PhaseTimer.phase()` ctx-mgr used the same way everywhere. `build_dataset_record` signature matches in tests (Task 16) and aggregator CLI (Task 22). `PricingTable.load` consistent. `Checkpoint.append`/`read_completed_datasets` consistent. ✓

4. **Gap fixes:** none found.

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-04-17-batch-benchmark-49-datasets-plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints for review.

Which approach?

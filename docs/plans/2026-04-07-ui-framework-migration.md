# UI Framework Migration: Streamlit → React + FastAPI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Streamlit UI (`src/ui/`) with a React + Vite + shadcn/ui frontend backed by a FastAPI API server, preserving all 12 existing features and enabling richer interactivity.

**Architecture:** Three-layer system — React SPA (frontend/) communicates via REST + WebSocket with a FastAPI backend (src/api/), which delegates to framework-agnostic services that call the unchanged pipeline (src/run_pipeline.py). In production, FastAPI serves the built React static files from a single Docker container.

**Tech Stack:** React 18 + TypeScript + Vite + shadcn/ui + Tailwind CSS + TanStack Table (frontend), FastAPI + WebSocket + uvicorn (backend), existing Python pipeline (unchanged)

**Spec:** `docs/specs/2026-04-07-ui-framework-migration-design.md`

---

## File Map

### New files — Backend (`src/api/`)

| File | Responsibility |
|------|---------------|
| `src/api/__init__.py` | Package marker |
| `src/api/main.py` | FastAPI app creation, CORS, router mounting, static file serving |
| `src/api/config.py` | Server config constants (ports, output dir, phase labels) |
| `src/api/routes/__init__.py` | Package marker |
| `src/api/routes/upload.py` | `POST /api/upload` — receive CSV files, create run directory |
| `src/api/routes/runs.py` | `POST /api/runs`, `GET /api/runs`, `GET /api/runs/{id}` |
| `src/api/routes/files.py` | `GET/PUT /api/runs/{id}/files/{name}`, `GET /api/runs/{id}/download` |
| `src/api/routes/feedback.py` | `POST /api/runs/{id}/feedback`, `POST /api/runs/{id}/dev-feedback` |
| `src/api/routes/revalidate.py` | `POST /api/runs/{id}/revalidate` |
| `src/api/ws/__init__.py` | Package marker |
| `src/api/ws/progress.py` | WebSocket `/ws/progress/{run_id}` — stream progress events |
| `src/api/services/__init__.py` | Package marker |
| `src/api/services/run_state.py` | `RunState` dataclass + in-memory store |
| `src/api/services/pipeline_runner.py` | Framework-agnostic `launch_pipeline()` (refactored from `src/ui/services/`) |
| `src/api/services/file_manager.py` | File ops without Streamlit imports (refactored) |
| `src/api/services/feedback_store.py` | Feedback JSON persistence (moved, unchanged) |
| `src/api/services/revalidation_service.py` | stat_var_processor runner (moved, unchanged) |
| `src/api/services/google_sheets_service.py` | Google Sheets integration (moved, unchanged) |
| `src/api/services/mcp_lifecycle.py` | MCP server management without st.session_state |
| `src/api/adapters/__init__.py` | Package marker |
| `src/api/adapters/progress_plugin.py` | ADK ProgressTrackingPlugin (moved, unchanged) |

### New files — Frontend (`frontend/`)

| File | Responsibility |
|------|---------------|
| `frontend/package.json` | Dependencies + scripts |
| `frontend/vite.config.ts` | Vite config with API proxy |
| `frontend/tsconfig.json` | TypeScript config |
| `frontend/tsconfig.app.json` | App-specific TS config |
| `frontend/tsconfig.node.json` | Node-specific TS config |
| `frontend/tailwind.config.ts` | Tailwind CSS config |
| `frontend/postcss.config.js` | PostCSS config for Tailwind |
| `frontend/components.json` | shadcn/ui config |
| `frontend/index.html` | HTML entry point |
| `frontend/src/main.tsx` | React entry point |
| `frontend/src/App.tsx` | Root component with React Router |
| `frontend/src/index.css` | Tailwind imports + global styles |
| `frontend/src/lib/utils.ts` | Utility functions (cn(), etc.) |
| `frontend/src/lib/api.ts` | API client (typed fetch wrapper) |
| `frontend/src/types/index.ts` | Shared TypeScript types |
| `frontend/src/hooks/useWebSocket.ts` | WebSocket hook with auto-reconnect |
| `frontend/src/hooks/useApi.ts` | API query hooks |
| `frontend/src/components/Sidebar.tsx` | Persistent sidebar (nav, history, config) |
| `frontend/src/components/WizardStepper.tsx` | Step indicator |
| `frontend/src/components/FileUploader.tsx` | Drag-and-drop CSV upload |
| `frontend/src/components/DataPreview.tsx` | Read-only CSV preview table |
| `frontend/src/components/ProgressTracker.tsx` | Phase checklist + progress bar |
| `frontend/src/components/OutputViewer.tsx` | Tabbed file viewer |
| `frontend/src/components/CsvEditor.tsx` | Editable spreadsheet |
| `frontend/src/components/CodeViewer.tsx` | Syntax-highlighted text |
| `frontend/src/components/FeedbackForm.tsx` | Feedback + re-run trigger |
| `frontend/src/components/DownloadButton.tsx` | ZIP download |
| `frontend/src/pages/UploadPage.tsx` | Wizard step 1 |
| `frontend/src/pages/ConfigurePage.tsx` | Wizard step 2 |
| `frontend/src/pages/ProgressPage.tsx` | Wizard step 3 |
| `frontend/src/pages/ResultsPage.tsx` | Wizard step 4 |
| `frontend/src/pages/HistoryPage.tsx` | Browse past runs |

### New files — Tests

| File | Responsibility |
|------|---------------|
| `tests/api/test_upload.py` | Upload endpoint tests |
| `tests/api/test_runs.py` | Runs endpoint tests |
| `tests/api/test_files.py` | Files endpoint tests |
| `tests/api/test_feedback.py` | Feedback endpoint tests |
| `tests/api/test_revalidate.py` | Revalidation endpoint tests |
| `tests/api/test_ws_progress.py` | WebSocket progress tests |
| `tests/api/test_run_state.py` | RunState service tests |
| `tests/api/test_file_manager.py` | Refactored file_manager tests |
| `tests/api/test_pipeline_runner.py` | Pipeline runner service tests |

### Modified files

| File | Change |
|------|--------|
| `pyproject.toml` | Add `fastapi`, `uvicorn`, `python-multipart`, `websockets`; remove `streamlit` |
| `.gitignore` | Add `frontend/node_modules/`, `frontend/dist/` |
| `CLAUDE.md` | Update launch commands, add frontend dev workflow |

### Deleted files (final task)

| File | Reason |
|------|--------|
| `src/ui/` (entire directory) | Replaced by `src/api/` + `frontend/` |

---

## Task 1: Project Setup — Dependencies and Configuration

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Create: `src/api/__init__.py`
- Create: `src/api/config.py`

- [ ] **Step 1: Add FastAPI dependencies to pyproject.toml**

In `pyproject.toml`, replace the `streamlit` line in `dependencies`:

```python
    # UI — replaced: was "streamlit>=1.44.0"
    # API Server
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "python-multipart>=0.0.18",
    "websockets>=14.0",
```

- [ ] **Step 2: Update .gitignore for frontend artifacts**

Add these lines at the end of `.gitignore`:

```
# Frontend (React + Vite)
frontend/node_modules/
frontend/dist/
```

- [ ] **Step 3: Install new dependencies**

Run:
```bash
cd /Users/nehilsood/work/poc-auto-schematization
uv sync --all-extras
```

Expected: dependencies install successfully, no conflicts.

- [ ] **Step 4: Create src/api/__init__.py**

```python
"""FastAPI backend for PVMAP Generation Pipeline."""
```

- [ ] **Step 5: Create src/api/config.py**

```python
"""API server configuration constants."""
import os
from pathlib import Path

# Server settings
API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8000"))

# Output directory for UI runs (matches old Streamlit config)
UI_OUTPUT_DIR = Path(os.environ.get("UI_OUTPUT_DIR", "ui_output"))

# Default pipeline settings
DEFAULT_MODEL = "gemini-3.1-pro-preview"
DEFAULT_MAX_RETRIES = 1
MIN_PIPELINE_ATTEMPTS = 2

# MCP settings
MCP_DEFAULT_PORT = 3000

# Cloud Run detection
CLOUD_RUN = os.environ.get("K_SERVICE", "") != ""
GCS_BUCKET = os.environ.get("GCS_BUCKET", "")

# Supported upload types
SUPPORTED_EXTENSIONS = {".csv"}

# Pipeline phases for progress display
PHASE_LABELS = {
    "StatePrep": "Preparing state",
    "Sampling": "Sampling data",
    "SchemaSelectionAgent": "Selecting schema",
    "StatVarDiscovery": "Discovering StatVars (MCP)",
    "Generator": "Generating PVMAP",
    "MetadataGenerator": "Generating metadata config",
    "Validator": "Validating PVMAP",
    "MCPSpotCheck": "Spot-checking mappings (MCP)",
    "MCPErrorResolver": "Resolving errors (MCP)",
    "QualityEvaluator": "Evaluating quality",
    "UnifiedFeedback": "Generating feedback",
    "MaxRetriesCheck": "Checking retry status",
    "Evaluation": "Running evaluation",
}
```

- [ ] **Step 6: Commit**

```bash
git add src/api/__init__.py src/api/config.py pyproject.toml .gitignore
git commit -m "chore: add FastAPI deps, create api config, update gitignore for frontend"
```

---

## Task 2: RunState Service — In-Memory Run Tracking

**Files:**
- Create: `src/api/services/__init__.py`
- Create: `src/api/services/run_state.py`
- Create: `tests/api/__init__.py`
- Create: `tests/api/test_run_state.py`

- [ ] **Step 1: Create package markers**

`src/api/services/__init__.py`:
```python
"""Framework-agnostic services for the API layer."""
```

`tests/api/__init__.py`:
```python
"""API backend tests."""
```

- [ ] **Step 2: Write failing tests for RunState**

`tests/api/test_run_state.py`:
```python
"""Tests for in-memory run state management."""
import queue

import pytest

from src.api.services.run_state import RunState, create_run, get_run, list_runs, delete_run


class TestRunState:
    def setup_method(self):
        """Clear global state between tests."""
        from src.api.services import run_state
        run_state._runs.clear()

    def test_create_run(self):
        run = create_run(
            run_id="abc123",
            dataset_name="test_dataset",
            run_dir="/tmp/test",
            config={"model": "gemini-3.1-pro-preview"},
        )
        assert run.run_id == "abc123"
        assert run.status == "pending"
        assert run.dataset_name == "test_dataset"
        assert isinstance(run.progress_queue, queue.Queue)

    def test_get_run_exists(self):
        create_run(run_id="abc123", dataset_name="test", run_dir="/tmp/test", config={})
        run = get_run("abc123")
        assert run is not None
        assert run.run_id == "abc123"

    def test_get_run_missing(self):
        assert get_run("nonexistent") is None

    def test_list_runs(self):
        create_run(run_id="run1", dataset_name="ds1", run_dir="/tmp/r1", config={})
        create_run(run_id="run2", dataset_name="ds2", run_dir="/tmp/r2", config={})
        runs = list_runs()
        assert len(runs) == 2
        ids = {r.run_id for r in runs}
        assert ids == {"run1", "run2"}

    def test_delete_run(self):
        create_run(run_id="run1", dataset_name="ds1", run_dir="/tmp/r1", config={})
        deleted = delete_run("run1")
        assert deleted is True
        assert get_run("run1") is None

    def test_delete_run_missing(self):
        assert delete_run("nonexistent") is False

    def test_run_state_defaults(self):
        run = create_run(run_id="r1", dataset_name="ds", run_dir="/tmp", config={})
        assert run.result == {}
        assert run.error is None
        assert run.thread is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_run_state.py -x -q`

Expected: FAIL — `ModuleNotFoundError: No module named 'src.api.services.run_state'`

- [ ] **Step 4: Implement RunState**

`src/api/services/run_state.py`:
```python
"""In-memory run state management.

Tracks active pipeline runs. Completed run data lives on disk (output dirs,
manifests, feedback JSONs). This module only tracks in-flight state for
WebSocket broadcasting and API responses.
"""
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_runs: dict[str, "RunState"] = {}


@dataclass
class RunState:
    """State for a single pipeline run."""

    run_id: str
    dataset_name: str
    run_dir: str
    config: dict
    status: str = "pending"  # pending | running | complete | error
    result: dict = field(default_factory=dict)
    error: Optional[str] = None
    progress_queue: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=200))
    thread: Optional[threading.Thread] = None
    created_at: float = field(default_factory=time.time)


def create_run(
    run_id: str,
    dataset_name: str,
    run_dir: str,
    config: dict,
) -> RunState:
    """Create and register a new run."""
    run = RunState(
        run_id=run_id,
        dataset_name=dataset_name,
        run_dir=run_dir,
        config=config,
    )
    _runs[run_id] = run
    return run


def get_run(run_id: str) -> Optional[RunState]:
    """Get a run by ID, or None if not found."""
    return _runs.get(run_id)


def list_runs() -> list[RunState]:
    """List all tracked runs."""
    return list(_runs.values())


def delete_run(run_id: str) -> bool:
    """Remove a run from tracking. Returns True if it existed."""
    return _runs.pop(run_id, None) is not None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_run_state.py -x -q`

Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add src/api/services/__init__.py src/api/services/run_state.py tests/api/__init__.py tests/api/test_run_state.py
git commit -m "feat(api): add RunState service for in-memory run tracking"
```

---

## Task 3: Refactor Services — Framework-Agnostic

**Files:**
- Create: `src/api/services/file_manager.py`
- Create: `src/api/services/pipeline_runner.py`
- Copy: `src/api/services/feedback_store.py` (from `src/ui/services/`)
- Copy: `src/api/services/revalidation_service.py` (from `src/ui/services/`)
- Copy: `src/api/services/google_sheets_service.py` (from `src/ui/services/`)
- Create: `src/api/services/mcp_lifecycle.py`
- Create: `src/api/adapters/__init__.py`
- Copy: `src/api/adapters/progress_plugin.py` (from `src/ui/adapters/`)
- Create: `tests/api/test_file_manager.py`
- Create: `tests/api/test_pipeline_runner.py`

- [ ] **Step 1: Write failing tests for refactored file_manager**

`tests/api/test_file_manager.py`:
```python
"""Tests for framework-agnostic file manager."""
import json
import tempfile
from pathlib import Path

import pytest

from src.api.services.file_manager import (
    create_run_directory,
    save_uploaded_bytes,
    get_output_files,
    snapshot_version,
    get_latest_version,
    discover_historical_runs,
)


class TestFileManager:
    def test_create_run_directory(self, tmp_path):
        run_dir = create_run_directory("test123", base_dir=tmp_path)
        assert (run_dir / "input").is_dir()
        assert (run_dir / "output").is_dir()

    def test_save_uploaded_bytes(self, tmp_path):
        target_dir = tmp_path / "input"
        path = save_uploaded_bytes(b"col1,col2\na,b\n", target_dir, "data.csv")
        assert path.exists()
        assert path.read_bytes() == b"col1,col2\na,b\n"

    def test_get_output_files(self, tmp_path):
        (tmp_path / "generated_pvmap.csv").write_text("a,b\n1,2")
        (tmp_path / "generation_notes.md").write_text("# Notes")
        (tmp_path / "random_file.txt").write_text("ignored")
        files = get_output_files(tmp_path)
        assert "generated_pvmap.csv" in files
        assert "generation_notes.md" in files
        assert "random_file.txt" not in files

    def test_snapshot_version(self, tmp_path):
        (tmp_path / "generated_pvmap.csv").write_text("a,b")
        version_dir = snapshot_version(tmp_path, 1)
        assert (version_dir / "generated_pvmap.csv").read_text() == "a,b"

    def test_get_latest_version_empty(self, tmp_path):
        assert get_latest_version(tmp_path) == 0

    def test_get_latest_version_with_versions(self, tmp_path):
        (tmp_path / "v1").mkdir()
        (tmp_path / "v3").mkdir()
        assert get_latest_version(tmp_path) == 3

    def test_discover_historical_runs_empty(self, tmp_path):
        assert discover_historical_runs(base_dir=tmp_path) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_file_manager.py -x -q`

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement file_manager.py (refactored from src/ui/services/file_manager.py)**

`src/api/services/file_manager.py`:
```python
"""File management for pipeline runs — no framework dependencies.

Refactored from src/ui/services/file_manager.py to remove Streamlit imports.
Key change: save_uploaded_bytes() accepts raw bytes instead of Streamlit UploadedFile.
"""
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from src.api.config import UI_OUTPUT_DIR

logger = logging.getLogger(__name__)

# Known output files that the pipeline produces
_KNOWN_OUTPUT_FILES = [
    "generated_pvmap.csv",
    "output_metadata.csv",
    "processed.csv",
    "processed.mcf",
    "processed.tmcf",
    "processed_stat_vars.mcf",
    "generation_notes.md",
    "processed_counters.txt",
    "statvar_processor_raw_logs.txt",
]


def create_run_directory(run_id: str, base_dir: Optional[Path] = None) -> Path:
    """Create directory structure for a pipeline run."""
    base = base_dir or UI_OUTPUT_DIR
    run_dir = base / run_id
    (run_dir / "input").mkdir(parents=True, exist_ok=True)
    (run_dir / "output").mkdir(parents=True, exist_ok=True)
    logger.info("Created run directory: %s", run_dir)
    return run_dir


def save_uploaded_bytes(data: bytes, target_dir: Path, filename: str) -> Path:
    """Save uploaded file bytes to disk.

    Unlike the Streamlit version, this accepts raw bytes — the API layer
    handles extracting bytes from the multipart upload.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    target_path.write_bytes(data)
    logger.info("Saved uploaded file: %s (%d bytes)", target_path, len(data))
    return target_path


def get_output_files(output_dir: Path) -> Dict[str, Path]:
    """Map known output filenames to paths (only files that exist)."""
    result = {}
    for fname in _KNOWN_OUTPUT_FILES:
        fpath = output_dir / fname
        if fpath.exists():
            result[fname] = fpath
    return result


def snapshot_version(output_dir: Path, version: int) -> Path:
    """Copy current output files to a versioned snapshot directory."""
    version_dir = output_dir / f"v{version}"
    version_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for item in output_dir.iterdir():
        if item.is_file():
            shutil.copy2(item, version_dir / item.name)
            copied += 1
        elif item.is_dir() and item.name == "generated_response":
            shutil.copytree(item, version_dir / item.name, dirs_exist_ok=True)
            copied += 1

    logger.info("Snapshot v%d: copied %d items to %s", version, copied, version_dir)
    return version_dir


def save_run_manifest(
    output_dir: Path,
    version: int,
    config: dict,
    result: dict,
) -> Path:
    """Write run_manifest.json for a version snapshot."""
    version_dir = output_dir / f"v{version}"
    version_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": config.get("run_id", ""),
        "version": version,
        "timestamp": datetime.now().isoformat(),
        "dataset_name": config.get("dataset_name", ""),
        "model": config.get("model", ""),
        "attempts": result.get("retry_count", 0) + 1,
        "exit_reason": result.get("exit_reason", ""),
        "validation_passed": result.get("validation_passed", False),
    }

    manifest_path = version_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info("Saved run manifest v%d", version)
    return manifest_path


def save_edited_files(
    output_dir: Path,
    version: int,
    edited_pvmap_df: Optional[pd.DataFrame] = None,
    edited_metadata_df: Optional[pd.DataFrame] = None,
) -> Path:
    """Save user-edited files to the version's feedback directory."""
    feedback_dir = output_dir / f"v{version}" / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)

    if edited_pvmap_df is not None:
        edited_pvmap_df.to_csv(feedback_dir / "edited_pvmap.csv", index=False)
    if edited_metadata_df is not None:
        edited_metadata_df.to_csv(feedback_dir / "edited_metadata.csv", index=False)

    return feedback_dir


def get_latest_version(output_dir: Path) -> int:
    """Scan v{N} directories and return highest version number."""
    max_v = 0
    if output_dir.exists():
        for item in output_dir.iterdir():
            if item.is_dir() and item.name.startswith("v"):
                try:
                    v = int(item.name[1:])
                    max_v = max(max_v, v)
                except ValueError:
                    pass
    return max_v


def discover_historical_runs(base_dir: Optional[Path] = None) -> list[dict]:
    """Scan output directory for past runs and return summary metadata."""
    base = base_dir or UI_OUTPUT_DIR
    if not base.exists():
        return []

    runs = []
    for run_dir in base.iterdir():
        if not run_dir.is_dir():
            continue

        run_id = run_dir.name
        output_dir = run_dir / "output"
        if not output_dir.exists():
            continue

        # Find the dataset subdirectory
        dataset_name = None
        dataset_dir = None
        for item in output_dir.iterdir():
            if item.is_dir() and item.name != "logs":
                dataset_name = item.name
                dataset_dir = item
                break

        if not dataset_name or not dataset_dir:
            continue

        # Read attempt JSONs for metadata
        response_dir = dataset_dir / "generated_response"
        attempts = []
        if response_dir.exists():
            for attempt_file in sorted(response_dir.glob("attempt_*.json")):
                try:
                    data = json.loads(attempt_file.read_text())
                    attempts.append(data)
                except (json.JSONDecodeError, OSError):
                    pass

        model = attempts[0].get("model", "") if attempts else ""
        timestamp = attempts[0].get("start_time", "") if attempts else ""
        if not timestamp:
            timestamp = datetime.fromtimestamp(run_dir.stat().st_mtime).isoformat()

        last_attempt = attempts[-1] if attempts else {}
        validation_passed = last_attempt.get("validation_success", False)

        runs.append({
            "run_id": run_id,
            "dataset_name": dataset_name,
            "timestamp": timestamp,
            "model": model,
            "attempts": len(attempts),
            "has_pvmap": (dataset_dir / "generated_pvmap.csv").exists(),
            "run_dir": str(run_dir),
            "validation_passed": validation_passed,
        })

    runs.sort(key=lambda r: r["timestamp"], reverse=True)
    return runs
```

- [ ] **Step 4: Run file_manager tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_file_manager.py -x -q`

Expected: 7 passed

- [ ] **Step 5: Write failing test for pipeline_runner**

`tests/api/test_pipeline_runner.py`:
```python
"""Tests for framework-agnostic pipeline runner."""
import queue

import pytest

from src.api.services.pipeline_runner import PipelineConfig


class TestPipelineConfig:
    def test_defaults(self):
        config = PipelineConfig(
            run_id="test123",
            dataset_name="test_ds",
            input_dir="/tmp/input",
            output_dir="/tmp/output",
        )
        assert config.model == "gemini-3.1-pro-preview"
        assert config.enable_mcp is True
        assert config.skip_evaluation is True
        assert config.max_retries == 1

    def test_custom_values(self):
        config = PipelineConfig(
            run_id="r1",
            dataset_name="ds",
            input_dir="/tmp/in",
            output_dir="/tmp/out",
            model="gemini-2.0-flash",
            enable_mcp=False,
            max_retries=5,
        )
        assert config.model == "gemini-2.0-flash"
        assert config.enable_mcp is False
        assert config.max_retries == 5
```

- [ ] **Step 6: Implement pipeline_runner.py**

`src/api/services/pipeline_runner.py`:
```python
"""Async bridge: runs the ADK pipeline in a background thread.

Refactored from src/ui/services/pipeline_runner.py — no Streamlit imports.
"""
import logging
import queue
import threading
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.api.adapters.progress_plugin import ProgressEvent, ProgressTrackingPlugin
from src.api.config import MIN_PIPELINE_ATTEMPTS

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for a pipeline run."""

    run_id: str
    dataset_name: str
    input_dir: str
    output_dir: str
    input_file: Optional[str] = None
    model: str = "gemini-3.1-pro-preview"
    enable_mcp: bool = True
    mcp_url: Optional[str] = None
    skip_sampling: bool = False
    force_resample: bool = False
    skip_schema_selection: bool = False
    skip_evaluation: bool = True
    use_metadata: bool = False
    metadata_file_path: Optional[str] = None
    human_feedback: Optional[str] = None
    min_attempts: int = MIN_PIPELINE_ATTEMPTS
    max_retries: int = 1
    use_schema_examples: bool = True
    thinking_level: Optional[str] = None


def launch_pipeline(
    config: PipelineConfig,
    progress_queue: queue.Queue,
) -> threading.Thread:
    """Launch pipeline in a daemon thread. Returns the thread handle."""
    logger.info(
        "Launching pipeline thread: run_id=%s, dataset=%s, model=%s",
        config.run_id, config.dataset_name, config.model,
    )
    thread = threading.Thread(
        target=_run_in_thread,
        args=(config, progress_queue),
        daemon=True,
        name=f"pipeline-{config.run_id}",
    )
    thread.start()
    return thread


def _run_in_thread(config: PipelineConfig, progress_queue: queue.Queue):
    """Execute the pipeline and push result/error to the queue."""
    try:
        logger.info("Pipeline thread started: run_id=%s", config.run_id)

        from src.pipeline.validation.log_filter import apply_log_noise_filters
        apply_log_noise_filters()

        from src.run_pipeline import run_dataset_pipeline

        progress_plugin = ProgressTrackingPlugin(progress_queue)

        result = run_dataset_pipeline(
            dataset_name=config.dataset_name,
            input_dir=Path(config.input_dir),
            output_dir=Path(config.output_dir),
            model=config.model,
            enable_mcp=config.enable_mcp,
            mcp_url=config.mcp_url,
            skip_sampling=config.skip_sampling,
            force_resample=config.force_resample,
            skip_schema_selection=config.skip_schema_selection,
            skip_evaluation=config.skip_evaluation,
            input_file=config.input_file,
            use_metadata=config.use_metadata,
            metadata_file_path=config.metadata_file_path,
            human_feedback=config.human_feedback,
            min_attempts=config.min_attempts,
            max_retries=config.max_retries,
            extra_plugins=[progress_plugin],
            use_schema_examples=config.use_schema_examples,
            thinking_level=config.thinking_level,
        )

        logger.info("Pipeline completed: run_id=%s", config.run_id)
        progress_queue.put(ProgressEvent(
            agent_name="Pipeline",
            message="Pipeline completed successfully",
            is_terminal=True,
            metadata={"result": result},
        ))

    except Exception as e:
        logger.error("Pipeline failed: run_id=%s, error=%s", config.run_id, e)
        progress_queue.put(ProgressEvent(
            agent_name="Pipeline",
            message=f"Pipeline failed: {str(e)}",
            is_terminal=True,
            is_error=True,
            metadata={"error": str(e), "traceback": traceback.format_exc()},
        ))
```

- [ ] **Step 7: Copy unchanged services and adapter**

```bash
# Create adapter package
mkdir -p src/api/adapters
cat > src/api/adapters/__init__.py << 'PYEOF'
"""Adapters bridging pipeline internals to the API layer."""
PYEOF

# Copy files that need no changes
cp src/ui/adapters/progress_plugin.py src/api/adapters/progress_plugin.py
cp src/ui/services/feedback_store.py src/api/services/feedback_store.py
cp src/ui/services/revalidation_service.py src/api/services/revalidation_service.py
cp src/ui/services/google_sheets_service.py src/api/services/google_sheets_service.py
```

- [ ] **Step 8: Create mcp_lifecycle.py (refactored — no Streamlit)**

`src/api/services/mcp_lifecycle.py`:
```python
"""MCP server lifecycle management — no framework dependencies.

Refactored from src/ui/services/mcp_lifecycle.py to remove st.session_state.
Uses module-level state instead.
"""
import atexit
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_mcp_manager: Optional[object] = None
_mcp_url: Optional[str] = None


def get_or_start_mcp(port: int = 3000) -> Optional[object]:
    """Get existing or start new MCP server."""
    global _mcp_manager, _mcp_url

    if _mcp_manager is not None:
        return _mcp_manager

    try:
        from src.data_commons.api.mcp_server_manager import MCPServerManager

        manager = MCPServerManager(port=port)
        if manager.start(timeout=30):
            _mcp_manager = manager
            _mcp_url = manager.mcp_url
            atexit.register(stop_mcp)
            logger.info("MCP server started at %s", _mcp_url)
            return manager
        else:
            logger.warning("MCP server failed to start")
            return None
    except ImportError:
        logger.warning("datacommons-mcp not installed")
        return None
    except Exception as e:
        logger.warning("MCP start failed: %s", e)
        return None


def stop_mcp() -> None:
    """Stop the MCP server."""
    global _mcp_manager, _mcp_url
    if _mcp_manager:
        try:
            _mcp_manager.stop()
            logger.info("MCP server stopped")
        except Exception as e:
            logger.warning("Error stopping MCP server: %s", e)
    _mcp_manager = None
    _mcp_url = None


def get_mcp_url() -> Optional[str]:
    """Return MCP URL if server is running."""
    return _mcp_url
```

- [ ] **Step 9: Run all tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/ -x -q`

Expected: 9 passed (7 run_state + 2 pipeline_config)

- [ ] **Step 10: Commit**

```bash
git add src/api/services/ src/api/adapters/ tests/api/
git commit -m "feat(api): add refactored services layer — file_manager, pipeline_runner, mcp_lifecycle"
```

---

## Task 4: FastAPI App Skeleton + Upload Route

**Files:**
- Create: `src/api/main.py`
- Create: `src/api/routes/__init__.py`
- Create: `src/api/routes/upload.py`
- Create: `tests/api/test_upload.py`

- [ ] **Step 1: Write failing tests for upload**

`tests/api/test_upload.py`:
```python
"""Tests for file upload endpoint."""
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(output_dir=tmp_path)
    return TestClient(app)


class TestUpload:
    def test_upload_csv(self, client, tmp_path):
        csv_content = b"col1,col2\nval1,val2\n"
        response = client.post(
            "/api/upload",
            files={"input_csv": ("test_data.csv", csv_content, "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert data["dataset_name"] == "test_data"
        assert data["rows"] == 1
        assert data["columns"] == 2

    def test_upload_csv_with_metadata(self, client, tmp_path):
        csv_content = b"col1,col2\nval1,val2\n"
        meta_content = b"key,value\nname,test\n"
        response = client.post(
            "/api/upload",
            files={
                "input_csv": ("data.csv", csv_content, "text/csv"),
                "metadata_csv": ("meta.csv", meta_content, "text/csv"),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["metadata_path"] is not None

    def test_upload_no_file(self, client):
        response = client.post("/api/upload")
        assert response.status_code == 422  # FastAPI validation error

    def test_upload_empty_csv(self, client):
        csv_content = b"col1,col2\n"  # headers only, no data rows
        response = client.post(
            "/api/upload",
            files={"input_csv": ("empty.csv", csv_content, "text/csv")},
        )
        assert response.status_code == 400
        assert "no data rows" in response.json()["detail"].lower()

    def test_upload_custom_dataset_name(self, client):
        csv_content = b"a,b\n1,2\n"
        response = client.post(
            "/api/upload",
            data={"dataset_name": "custom_name"},
            files={"input_csv": ("data.csv", csv_content, "text/csv")},
        )
        assert response.status_code == 200
        assert response.json()["dataset_name"] == "custom_name"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_upload.py -x -q`

Expected: FAIL — `ModuleNotFoundError: No module named 'src.api.main'`

- [ ] **Step 3: Implement FastAPI app skeleton**

`src/api/routes/__init__.py`:
```python
"""FastAPI route modules."""
```

`src/api/main.py`:
```python
"""FastAPI application for PVMAP Generation Pipeline.

In development: run with `uvicorn src.api.main:app --reload --port 8000`
In production: FastAPI serves React static files from frontend/dist/
"""
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.config import UI_OUTPUT_DIR

logger = logging.getLogger(__name__)


def create_app(output_dir: Optional[Path] = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        output_dir: Override output directory (used in tests).
    """
    app = FastAPI(
        title="Agent B: Auto Schematization",
        description="PVMAP Generation Pipeline API",
        version="1.0.0",
    )

    # Store output_dir in app state for dependency injection
    app.state.output_dir = output_dir or UI_OUTPUT_DIR

    # CORS — allow Vite dev server in development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routes
    from src.api.routes.upload import router as upload_router
    app.include_router(upload_router, prefix="/api")

    # Serve React static files in production (if built)
    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True))
        logger.info("Serving frontend from %s", frontend_dist)

    return app


# Default app instance for `uvicorn src.api.main:app`
app = create_app()
```

- [ ] **Step 4: Implement upload route**

`src/api/routes/upload.py`:
```python
"""File upload endpoint."""
import io
import logging
import uuid

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from src.api.services.file_manager import create_run_directory, save_uploaded_bytes

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload")
async def upload_files(
    request: Request,
    input_csv: UploadFile = File(...),
    metadata_csv: UploadFile | None = File(None),
    dataset_name: str | None = Form(None),
):
    """Upload CSV files and create a run directory.

    Returns run_id, dataset_name, file paths, and data preview info.
    """
    output_dir = request.app.state.output_dir

    # Read and validate CSV
    content = await input_csv.read()
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV: {e}")

    if len(df) == 0:
        raise HTTPException(status_code=400, detail="CSV has no data rows")

    # Derive dataset name from filename if not provided
    if not dataset_name:
        dataset_name = input_csv.filename.replace(".csv", "").replace(" ", "_")

    # Create run directory
    run_id = uuid.uuid4().hex[:12]
    run_dir = create_run_directory(run_id, base_dir=output_dir)

    # Save input file
    input_path = save_uploaded_bytes(content, run_dir / "input", "input.csv")

    # Save metadata if provided
    metadata_path = None
    if metadata_csv is not None:
        meta_content = await metadata_csv.read()
        metadata_path = save_uploaded_bytes(
            meta_content, run_dir / "input", "input_metadata.csv"
        )

    logger.info("Upload complete: run_id=%s, dataset=%s, rows=%d, cols=%d",
                run_id, dataset_name, len(df), len(df.columns))

    return {
        "run_id": run_id,
        "dataset_name": dataset_name,
        "run_dir": str(run_dir),
        "input_path": str(input_path),
        "metadata_path": str(metadata_path) if metadata_path else None,
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": list(df.columns),
        "preview": df.head(10).to_dict(orient="records"),
    }
```

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_upload.py -x -q`

Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add src/api/main.py src/api/routes/__init__.py src/api/routes/upload.py tests/api/test_upload.py
git commit -m "feat(api): add FastAPI app skeleton and file upload endpoint"
```

---

## Task 5: Runs Route — Start, List, Get

**Files:**
- Create: `src/api/routes/runs.py`
- Create: `tests/api/test_runs.py`

- [ ] **Step 1: Write failing tests**

`tests/api/test_runs.py`:
```python
"""Tests for pipeline runs endpoints."""
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.services import run_state


@pytest.fixture
def client(tmp_path):
    app = create_app(output_dir=tmp_path)
    yield TestClient(app)
    run_state._runs.clear()


class TestListRuns:
    def test_list_empty(self, client):
        response = client.get("/api/runs")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_with_active_run(self, client):
        run_state.create_run("r1", "ds1", "/tmp/r1", {"model": "test"})
        response = client.get("/api/runs")
        data = response.json()
        assert len(data) >= 1
        assert any(r["run_id"] == "r1" for r in data)


class TestGetRun:
    def test_get_existing_run(self, client):
        run_state.create_run("r1", "ds1", "/tmp/r1", {"model": "test"})
        response = client.get("/api/runs/r1")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "r1"
        assert data["status"] == "pending"

    def test_get_missing_run(self, client):
        response = client.get("/api/runs/nonexistent")
        assert response.status_code == 404


class TestStartRun:
    def test_start_run_missing_run_id(self, client):
        """Cannot start a run that doesn't exist in state."""
        response = client.post("/api/runs", json={
            "run_id": "nonexistent",
            "dataset_name": "test",
        })
        assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_runs.py -x -q`

Expected: FAIL

- [ ] **Step 3: Implement runs route**

`src/api/routes/runs.py`:
```python
"""Pipeline run management endpoints."""
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from src.api.services.run_state import create_run, get_run, list_runs
from src.api.services.file_manager import discover_historical_runs
from src.api.services.pipeline_runner import PipelineConfig, launch_pipeline
from src.api.services.mcp_lifecycle import get_or_start_mcp, get_mcp_url
from src.api.config import MCP_DEFAULT_PORT, MIN_PIPELINE_ATTEMPTS

logger = logging.getLogger(__name__)
router = APIRouter()


class StartRunRequest(BaseModel):
    run_id: str
    dataset_name: str
    model: str = "gemini-3.1-pro-preview"
    max_retries: int = 1
    enable_mcp: bool = False
    use_schema_examples: bool = True
    skip_sampling: bool = False
    use_metadata: bool = False
    human_feedback: Optional[str] = None
    thinking_level: Optional[str] = "high"


@router.get("/runs")
async def list_all_runs(request: Request):
    """List active runs + historical runs from disk."""
    output_dir = request.app.state.output_dir

    # Active runs from memory
    active = [
        {
            "run_id": r.run_id,
            "dataset_name": r.dataset_name,
            "status": r.status,
            "timestamp": "",
            "validation_passed": r.result.get("validation_passed", False),
        }
        for r in list_runs()
    ]

    # Historical runs from disk
    historical = discover_historical_runs(base_dir=output_dir)

    # Merge: active runs first, then historical (skip duplicates)
    active_ids = {r["run_id"] for r in active}
    combined = active + [h for h in historical if h["run_id"] not in active_ids]

    return combined


@router.get("/runs/{run_id}")
async def get_run_status(run_id: str):
    """Get current status and result of a run."""
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return {
        "run_id": run.run_id,
        "dataset_name": run.dataset_name,
        "status": run.status,
        "result": run.result,
        "error": run.error,
        "config": run.config,
    }


@router.post("/runs")
async def start_run(req: StartRunRequest, request: Request):
    """Start the pipeline for an uploaded dataset.

    The run must already exist (created by POST /api/upload via create_run).
    """
    run = get_run(req.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {req.run_id} not found")

    # Handle MCP
    mcp_url = None
    if req.enable_mcp:
        get_or_start_mcp(MCP_DEFAULT_PORT)
        mcp_url = get_mcp_url()

    from pathlib import Path
    run_dir = Path(run.run_dir)

    config = PipelineConfig(
        run_id=req.run_id,
        dataset_name=req.dataset_name,
        input_dir=str(run_dir / "input"),
        output_dir=str(run_dir / "output"),
        model=req.model,
        enable_mcp=req.enable_mcp,
        mcp_url=mcp_url,
        use_schema_examples=req.use_schema_examples,
        skip_sampling=req.skip_sampling,
        use_metadata=req.use_metadata,
        human_feedback=req.human_feedback,
        min_attempts=MIN_PIPELINE_ATTEMPTS,
        max_retries=req.max_retries,
        thinking_level=req.thinking_level,
    )

    run.config = config.__dict__
    run.status = "running"

    thread = launch_pipeline(config, run.progress_queue)
    run.thread = thread

    logger.info("Pipeline started: run_id=%s, dataset=%s", req.run_id, req.dataset_name)

    return {"run_id": req.run_id, "status": "running"}
```

- [ ] **Step 4: Register runs router in main.py**

Add to `src/api/main.py` in `create_app()`, after the upload router line:

```python
    from src.api.routes.runs import router as runs_router
    app.include_router(runs_router, prefix="/api")
```

- [ ] **Step 5: Also register run in upload route**

Add to the end of `upload_files()` in `src/api/routes/upload.py`, before the return:

```python
    # Register run in state for subsequent start
    from src.api.services.run_state import create_run
    create_run(
        run_id=run_id,
        dataset_name=dataset_name,
        run_dir=str(run_dir),
        config={},
    )
```

- [ ] **Step 6: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_runs.py tests/api/test_upload.py -x -q`

Expected: 8 passed

- [ ] **Step 7: Commit**

```bash
git add src/api/routes/runs.py src/api/routes/upload.py src/api/main.py tests/api/test_runs.py
git commit -m "feat(api): add runs route — start, list, get pipeline runs"
```

---

## Task 6: Files Route — Read, Edit, Download

**Files:**
- Create: `src/api/routes/files.py`
- Create: `tests/api/test_files.py`

- [ ] **Step 1: Write failing tests**

`tests/api/test_files.py`:
```python
"""Tests for file serving and editing endpoints."""
import json
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.services import run_state


@pytest.fixture
def client_with_run(tmp_path):
    app = create_app(output_dir=tmp_path)
    client = TestClient(app)

    # Create a fake run with output files
    run_dir = tmp_path / "run1"
    output_dir = run_dir / "output" / "test_ds"
    output_dir.mkdir(parents=True)
    (output_dir / "generated_pvmap.csv").write_text("col1,col2\nA,B\nC,D\n")
    (output_dir / "generation_notes.md").write_text("# Notes\nSome notes here.")
    (output_dir / "processed.mcf").write_text("Node: E:test\ntypeOf: schema:Thing")

    run = run_state.create_run("run1", "test_ds", str(run_dir), {})
    run.status = "complete"

    yield client
    run_state._runs.clear()


class TestListFiles:
    def test_list_files(self, client_with_run):
        response = client_with_run.get("/api/runs/run1/files")
        assert response.status_code == 200
        data = response.json()
        assert "generated_pvmap.csv" in data["files"]
        assert "generation_notes.md" in data["files"]

    def test_list_files_missing_run(self, client_with_run):
        response = client_with_run.get("/api/runs/nonexistent/files")
        assert response.status_code == 404


class TestGetFile:
    def test_get_csv_file(self, client_with_run):
        response = client_with_run.get("/api/runs/run1/files/generated_pvmap.csv")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "csv"
        assert len(data["rows"]) == 2
        assert data["rows"][0]["col1"] == "A"

    def test_get_text_file(self, client_with_run):
        response = client_with_run.get("/api/runs/run1/files/generation_notes.md")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "text"
        assert "# Notes" in data["content"]

    def test_get_missing_file(self, client_with_run):
        response = client_with_run.get("/api/runs/run1/files/nonexistent.csv")
        assert response.status_code == 404


class TestUpdateFile:
    def test_update_csv(self, client_with_run):
        response = client_with_run.put(
            "/api/runs/run1/files/generated_pvmap.csv",
            json={"rows": [{"col1": "X", "col2": "Y"}]},
        )
        assert response.status_code == 200
        assert response.json()["saved"] is True

        # Verify it was actually saved
        get_response = client_with_run.get("/api/runs/run1/files/generated_pvmap.csv")
        assert get_response.json()["rows"][0]["col1"] == "X"

    def test_update_text(self, client_with_run):
        response = client_with_run.put(
            "/api/runs/run1/files/processed.mcf",
            json={"content": "Node: E:updated\ntypeOf: schema:NewThing"},
        )
        assert response.status_code == 200


class TestDownload:
    def test_download_zip(self, client_with_run):
        response = client_with_run.get("/api/runs/run1/download")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert len(response.content) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_files.py -x -q`

Expected: FAIL

- [ ] **Step 3: Implement files route**

`src/api/routes/files.py`:
```python
"""File serving, editing, and download endpoints."""
import io
import logging
import zipfile
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from src.api.services.run_state import get_run
from src.api.services.file_manager import get_output_files

logger = logging.getLogger(__name__)
router = APIRouter()


class CsvUpdate(BaseModel):
    rows: list[dict]


class TextUpdate(BaseModel):
    content: str


def _resolve_output_dir(run_id: str) -> Path:
    """Get the output directory for a run, or raise 404."""
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    output_dir = Path(run.run_dir) / "output" / run.dataset_name
    return output_dir


@router.get("/runs/{run_id}/files")
async def list_files(run_id: str):
    """List available output files for a run."""
    output_dir = _resolve_output_dir(run_id)
    files = get_output_files(output_dir)
    return {"files": list(files.keys())}


@router.get("/runs/{run_id}/files/{filename}")
async def get_file(run_id: str, filename: str):
    """Read a specific output file. CSVs are returned as JSON rows, others as text."""
    output_dir = _resolve_output_dir(run_id)
    fpath = output_dir / filename

    if not fpath.exists():
        raise HTTPException(status_code=404, detail=f"File {filename} not found")

    if filename.endswith(".csv"):
        try:
            df = pd.read_csv(fpath)
            return {
                "type": "csv",
                "filename": filename,
                "rows": df.to_dict(orient="records"),
                "columns": list(df.columns),
                "row_count": len(df),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to parse CSV: {e}")
    else:
        try:
            content = fpath.read_text(encoding="utf-8")
            return {
                "type": "text",
                "filename": filename,
                "content": content,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")


@router.put("/runs/{run_id}/files/{filename}")
async def update_file(run_id: str, filename: str, csv_update: Optional[CsvUpdate] = None, text_update: Optional[TextUpdate] = None):
    """Save an edited file back to disk."""
    output_dir = _resolve_output_dir(run_id)
    fpath = output_dir / filename

    if not fpath.exists():
        raise HTTPException(status_code=404, detail=f"File {filename} not found")

    if filename.endswith(".csv") and csv_update:
        df = pd.DataFrame(csv_update.rows)
        df.to_csv(fpath, index=False)
        logger.info("Saved edited CSV: %s", fpath)
    elif text_update:
        fpath.write_text(text_update.content, encoding="utf-8")
        logger.info("Saved edited text: %s", fpath)
    else:
        raise HTTPException(status_code=400, detail="Provide 'rows' for CSV or 'content' for text")

    return {"saved": True, "filename": filename}


@router.get("/runs/{run_id}/download")
async def download_zip(run_id: str):
    """Download all output files as a ZIP archive."""
    output_dir = _resolve_output_dir(run_id)

    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Output directory not found")

    buffer = io.BytesIO()
    file_count = 0
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fpath in sorted(output_dir.rglob("*")):
            if fpath.is_file():
                arcname = fpath.relative_to(output_dir)
                zf.write(fpath, arcname)
                file_count += 1

    logger.info("Created zip for run %s: %d files", run_id, file_count)

    run = get_run(run_id)
    zip_filename = f"{run.dataset_name}_outputs.zip" if run else f"{run_id}_outputs.zip"

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )
```

- [ ] **Step 4: Fix the PUT endpoint to accept either body type**

The PUT endpoint needs to accept a generic JSON body since FastAPI can't have two optional Body params easily. Replace the `update_file` function:

```python
@router.put("/runs/{run_id}/files/{filename}")
async def update_file(run_id: str, filename: str, body: dict):
    """Save an edited file back to disk.

    For CSV files: body = {"rows": [{"col1": "val1", ...}, ...]}
    For text files: body = {"content": "text content"}
    """
    output_dir = _resolve_output_dir(run_id)
    fpath = output_dir / filename

    if not fpath.exists():
        raise HTTPException(status_code=404, detail=f"File {filename} not found")

    if "rows" in body and filename.endswith(".csv"):
        df = pd.DataFrame(body["rows"])
        df.to_csv(fpath, index=False)
        logger.info("Saved edited CSV: %s", fpath)
    elif "content" in body:
        fpath.write_text(body["content"], encoding="utf-8")
        logger.info("Saved edited text: %s", fpath)
    else:
        raise HTTPException(status_code=400, detail="Provide 'rows' for CSV or 'content' for text")

    return {"saved": True, "filename": filename}
```

Remove the `CsvUpdate` and `TextUpdate` Pydantic models (no longer needed).

- [ ] **Step 5: Register files router in main.py**

Add to `create_app()`:

```python
    from src.api.routes.files import router as files_router
    app.include_router(files_router, prefix="/api")
```

- [ ] **Step 6: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_files.py -x -q`

Expected: 7 passed

- [ ] **Step 7: Commit**

```bash
git add src/api/routes/files.py src/api/main.py tests/api/test_files.py
git commit -m "feat(api): add files route — read, edit, download output files"
```

---

## Task 7: Feedback + Revalidation Routes

**Files:**
- Create: `src/api/routes/feedback.py`
- Create: `src/api/routes/revalidate.py`
- Create: `tests/api/test_feedback.py`
- Create: `tests/api/test_revalidate.py`

- [ ] **Step 1: Write failing tests for feedback**

`tests/api/test_feedback.py`:
```python
"""Tests for feedback endpoints."""
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.services import run_state


@pytest.fixture
def client_with_run(tmp_path):
    app = create_app(output_dir=tmp_path)
    client = TestClient(app)

    run_dir = tmp_path / "run1"
    output_dir = run_dir / "output" / "test_ds"
    output_dir.mkdir(parents=True)
    (output_dir / "generated_pvmap.csv").write_text("col1,col2\nA,B\n")

    run = run_state.create_run("run1", "test_ds", str(run_dir), {})
    run.status = "complete"
    run.result = {"retry_count": 0, "exit_reason": "quality_pass", "quality_metrics": {"heuristic_score": 75.0}}

    yield client
    run_state._runs.clear()


class TestFeedback:
    def test_submit_feedback(self, client_with_run):
        response = client_with_run.post(
            "/api/runs/run1/feedback",
            json={"text": "Fix column mapping", "category": "Column mapping", "severity": 4},
        )
        assert response.status_code == 200
        data = response.json()
        assert "new_run_id" in data

    def test_submit_feedback_missing_run(self, client_with_run):
        response = client_with_run.post(
            "/api/runs/nonexistent/feedback",
            json={"text": "Fix it", "category": "Other", "severity": 3},
        )
        assert response.status_code == 404


class TestDevFeedback:
    def test_submit_dev_feedback(self, client_with_run):
        response = client_with_run.post(
            "/api/runs/run1/dev-feedback",
            json={"text": "Progress bar stuck at 60%", "category": "Bug Report"},
        )
        assert response.status_code == 200
        assert response.json()["saved"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_feedback.py -x -q`

Expected: FAIL

- [ ] **Step 3: Implement feedback route**

`src/api/routes/feedback.py`:
```python
"""Feedback and re-run endpoints."""
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.services.run_state import get_run, create_run
from src.api.services.file_manager import (
    get_latest_version,
    snapshot_version,
    save_run_manifest,
)
from src.api.services.feedback_store import save_feedback
from src.api.services.google_sheets_service import (
    append_feedback_to_sheet,
    is_sheets_configured,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class FeedbackRequest(BaseModel):
    text: str
    category: str
    severity: int = 3


class DevFeedbackRequest(BaseModel):
    text: str
    category: str


@router.post("/runs/{run_id}/feedback")
async def submit_feedback(run_id: str, req: FeedbackRequest):
    """Submit feedback and prepare for re-run.

    Creates a version snapshot, saves feedback, and returns a new run_id
    that the frontend can use to start a re-run via POST /api/runs.
    """
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    output_dir = Path(run.run_dir) / "output" / run.dataset_name

    # Snapshot current output
    current_version = get_latest_version(output_dir)
    if current_version == 0:
        current_version = 1
    next_version = current_version + 1

    snapshot_version(output_dir, current_version)
    save_run_manifest(output_dir, current_version, run.config, run.result)

    # Build human feedback string
    human_feedback = (
        f"USER FEEDBACK: {req.text}\n"
        f"CATEGORY: {req.category}\n"
        f"SEVERITY: {req.severity}\n\n"
        f"Previous run: {run.result.get('retry_count', 0) + 1} attempts, "
        f"exit reason: {run.result.get('exit_reason', 'unknown')}"
    )

    # Save feedback JSON
    feedback_entry = {
        "run_id": run_id,
        "text": req.text,
        "category": req.category,
        "severity": req.severity,
        "dataset_name": run.dataset_name,
    }
    next_feedback_dir = output_dir / f"v{next_version}"
    next_feedback_dir.mkdir(parents=True, exist_ok=True)
    save_feedback(feedback_entry, next_feedback_dir)

    # Create new run for re-run (reuses same run_dir)
    new_run_id = uuid.uuid4().hex[:12]
    new_run = create_run(
        run_id=new_run_id,
        dataset_name=run.dataset_name,
        run_dir=run.run_dir,
        config={**run.config, "human_feedback": human_feedback, "skip_sampling": True},
    )

    logger.info("Feedback submitted for run %s, new run %s created", run_id, new_run_id)

    return {
        "new_run_id": new_run_id,
        "version": next_version,
        "human_feedback_length": len(human_feedback),
    }


@router.post("/runs/{run_id}/dev-feedback")
async def submit_dev_feedback(run_id: str, req: DevFeedbackRequest):
    """Submit developer feedback (bug reports, suggestions)."""
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    entry = {
        "type": "developer_feedback",
        "run_id": run_id,
        "dataset_name": run.dataset_name,
        "text": req.text,
        "category": req.category,
    }

    # Save locally
    output_dir = Path(run.run_dir) / "output" / run.dataset_name
    if output_dir.exists():
        save_feedback(entry, output_dir)

    # Send to Google Sheets if configured
    if is_sheets_configured():
        append_feedback_to_sheet(
            run_id=run_id,
            dataset_name=run.dataset_name,
            feedback_text=req.text,
            category=req.category,
            pipeline_status=run.status,
        )

    return {"saved": True}
```

- [ ] **Step 4: Implement revalidate route**

`tests/api/test_revalidate.py`:
```python
"""Tests for revalidation endpoint."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.services import run_state


@pytest.fixture
def client_with_run(tmp_path):
    app = create_app(output_dir=tmp_path)
    client = TestClient(app)

    run_dir = tmp_path / "run1"
    input_dir = run_dir / "input"
    output_dir = run_dir / "output" / "test_ds"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    (input_dir / "input.csv").write_text("col1,col2\nA,B\n")
    (output_dir / "generated_pvmap.csv").write_text("col1,col2\nA,B\n")

    run = run_state.create_run("run1", "test_ds", str(run_dir), {})
    run.status = "complete"

    yield client
    run_state._runs.clear()


class TestRevalidate:
    @patch("src.api.routes.revalidate.revalidate_pvmap")
    def test_revalidate_success(self, mock_reval, client_with_run):
        mock_reval.return_value = {"success": True, "data_rows": 42}
        response = client_with_run.post("/api/runs/run1/revalidate")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_revalidate_missing_run(self, client_with_run):
        response = client_with_run.post("/api/runs/nonexistent/revalidate")
        assert response.status_code == 404
```

`src/api/routes/revalidate.py`:
```python
"""Revalidation endpoint — run stat_var_processor on edited PVMAP."""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from src.api.services.run_state import get_run
from src.api.services.revalidation_service import revalidate as revalidate_pvmap

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/runs/{run_id}/revalidate")
async def revalidate(run_id: str):
    """Run stat_var_processor validation on the current PVMAP."""
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run_dir = Path(run.run_dir)
    output_dir = run_dir / "output" / run.dataset_name
    input_data = run_dir / "input" / "input.csv"
    pvmap_path = output_dir / "generated_pvmap.csv"

    if not input_data.exists():
        raise HTTPException(status_code=400, detail="Input data not found")
    if not pvmap_path.exists():
        raise HTTPException(status_code=400, detail="PVMAP not found")

    metadata_path = output_dir / "output_metadata.csv"

    result = revalidate_pvmap(
        input_data=input_data,
        pvmap_path=pvmap_path,
        metadata_path=metadata_path if metadata_path.exists() else None,
        output_dir=output_dir,
    )

    return result
```

- [ ] **Step 5: Register routes in main.py**

Add to `create_app()`:

```python
    from src.api.routes.feedback import router as feedback_router
    from src.api.routes.revalidate import router as revalidate_router
    app.include_router(feedback_router, prefix="/api")
    app.include_router(revalidate_router, prefix="/api")
```

- [ ] **Step 6: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_feedback.py tests/api/test_revalidate.py -x -q`

Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add src/api/routes/feedback.py src/api/routes/revalidate.py src/api/main.py tests/api/test_feedback.py tests/api/test_revalidate.py
git commit -m "feat(api): add feedback and revalidation routes"
```

---

## Task 8: WebSocket Progress Endpoint

**Files:**
- Create: `src/api/ws/__init__.py`
- Create: `src/api/ws/progress.py`
- Create: `tests/api/test_ws_progress.py`

- [ ] **Step 1: Write failing test**

`tests/api/test_ws_progress.py`:
```python
"""Tests for WebSocket progress endpoint."""
import queue
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.services import run_state
from src.api.adapters.progress_plugin import ProgressEvent


@pytest.fixture
def client_with_running(tmp_path):
    app = create_app(output_dir=tmp_path)
    client = TestClient(app)

    run = run_state.create_run("run1", "test_ds", str(tmp_path / "run1"), {})
    run.status = "running"

    yield client, run
    run_state._runs.clear()


class TestWebSocketProgress:
    def test_connect_to_running(self, client_with_running):
        client, run = client_with_running

        # Push a progress event
        run.progress_queue.put(ProgressEvent(
            agent_name="Sampling",
            message="Sampling completed",
        ))
        # Push terminal event so the WS loop ends
        run.progress_queue.put(ProgressEvent(
            agent_name="Pipeline",
            message="Done",
            is_terminal=True,
            metadata={"result": {"validation_passed": True}},
        ))

        with client.websocket_connect("/ws/progress/run1") as ws:
            msg1 = ws.receive_json()
            assert msg1["agent"] == "Sampling"

            msg2 = ws.receive_json()
            assert msg2["type"] == "complete"

    def test_connect_to_nonexistent_run(self, client_with_running):
        client, _ = client_with_running
        with pytest.raises(Exception):
            with client.websocket_connect("/ws/progress/nonexistent") as ws:
                ws.receive_json()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_ws_progress.py -x -q`

Expected: FAIL

- [ ] **Step 3: Implement WebSocket endpoint**

`src/api/ws/__init__.py`:
```python
"""WebSocket endpoints."""
```

`src/api/ws/progress.py`:
```python
"""WebSocket endpoint for real-time pipeline progress.

Replaces Streamlit's @st.fragment(run_every=2) polling pattern with
push-based streaming over WebSocket.
"""
import asyncio
import logging
import queue

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.services.run_state import get_run

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/progress/{run_id}")
async def progress_stream(websocket: WebSocket, run_id: str):
    """Stream pipeline progress events for a run.

    Drains the run's progress_queue every 500ms and sends events as JSON.
    Closes when a terminal event is received or the client disconnects.
    """
    run = get_run(run_id)
    if run is None:
        await websocket.close(code=4004, reason=f"Run {run_id} not found")
        return

    await websocket.accept()
    logger.info("WebSocket connected: run_id=%s", run_id)

    try:
        while True:
            # Drain all available events from the queue
            events_sent = 0
            while True:
                try:
                    event = run.progress_queue.get_nowait()

                    if event.is_terminal:
                        if event.is_error:
                            run.status = "error"
                            run.error = event.metadata.get("error", "Unknown error")
                            await websocket.send_json({
                                "type": "error",
                                "agent": event.agent_name,
                                "message": event.message,
                                "traceback": event.metadata.get("traceback", ""),
                            })
                        else:
                            run.status = "complete"
                            run.result = event.metadata.get("result", {})
                            await websocket.send_json({
                                "type": "complete",
                                "agent": event.agent_name,
                                "message": event.message,
                                "result": run.result,
                            })
                        # Terminal — close connection
                        await websocket.close()
                        return
                    else:
                        await websocket.send_json({
                            "type": "progress",
                            "agent": event.agent_name,
                            "message": event.message,
                            "timestamp": event.timestamp,
                            "attempt": event.metadata.get("attempt", 0),
                        })
                        events_sent += 1

                except queue.Empty:
                    break

            # Wait before polling again
            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: run_id=%s", run_id)
    except Exception as e:
        logger.error("WebSocket error for run %s: %s", run_id, e)
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass
```

- [ ] **Step 4: Register WebSocket router in main.py**

Add to `create_app()`:

```python
    from src.api.ws.progress import router as ws_router
    app.include_router(ws_router)
```

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_ws_progress.py -x -q`

Expected: 2 passed

- [ ] **Step 6: Run ALL backend tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/ -x -q`

Expected: All tests pass (should be ~23 tests)

- [ ] **Step 7: Commit**

```bash
git add src/api/ws/ tests/api/test_ws_progress.py src/api/main.py
git commit -m "feat(api): add WebSocket progress endpoint for real-time pipeline updates"
```

---

## Task 9: React Project Scaffolding

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.app.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/src/vite-env.d.ts`

- [ ] **Step 1: Initialize React project with Vite**

```bash
cd /Users/nehilsood/work/poc-auto-schematization
npm create vite@latest frontend -- --template react-ts
```

When prompted, select React and TypeScript.

- [ ] **Step 2: Install dependencies**

```bash
cd frontend
npm install
npm install -D tailwindcss @tailwindcss/vite
npm install react-router-dom
npm install @tanstack/react-table
```

- [ ] **Step 3: Initialize shadcn/ui**

```bash
cd /Users/nehilsood/work/poc-auto-schematization/frontend
npx shadcn@latest init
```

When prompted:
- Style: Default
- Base color: Neutral
- CSS variables: Yes

- [ ] **Step 4: Add commonly needed shadcn/ui components**

```bash
cd /Users/nehilsood/work/poc-auto-schematization/frontend
npx shadcn@latest add button card input label tabs textarea select slider toggle badge progress separator sheet scroll-area table dropdown-menu dialog alert toast
```

- [ ] **Step 5: Configure Vite proxy for API**

Replace `frontend/vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Proxy API and WebSocket calls to FastAPI backend
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
    },
  },
});
```

- [ ] **Step 6: Set up Tailwind CSS**

Replace `frontend/src/index.css`:
```css
@import "tailwindcss";
```

- [ ] **Step 7: Verify the dev server starts**

```bash
cd /Users/nehilsood/work/poc-auto-schematization/frontend
npm run dev -- --host 2>&1 | head -5
```

Expected: Output showing `Local: http://localhost:5173/`

Kill the dev server (Ctrl+C).

- [ ] **Step 8: Commit**

```bash
cd /Users/nehilsood/work/poc-auto-schematization
git add frontend/
git commit -m "chore: scaffold React + Vite + shadcn/ui + Tailwind frontend"
```

---

## Task 10: TypeScript Types + API Client

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/lib/api.ts`

- [ ] **Step 1: Define shared TypeScript types**

`frontend/src/types/index.ts`:
```typescript
/**
 * Shared TypeScript types for the PVMAP Pipeline UI.
 *
 * These mirror the Python Pydantic models / API response shapes.
 * In TypeScript, `interface` defines the shape of an object —
 * like a Python TypedDict or dataclass, but checked at compile time.
 */

/** Response from POST /api/upload */
export interface UploadResponse {
  run_id: string;
  dataset_name: string;
  run_dir: string;
  input_path: string;
  metadata_path: string | null;
  rows: number;
  columns: number;
  column_names: string[];
  preview: Record<string, unknown>[];
}

/** Request body for POST /api/runs */
export interface StartRunRequest {
  run_id: string;
  dataset_name: string;
  model?: string;
  max_retries?: number;
  enable_mcp?: boolean;
  use_schema_examples?: boolean;
  skip_sampling?: boolean;
  use_metadata?: boolean;
  human_feedback?: string | null;
  thinking_level?: string;
}

/** A pipeline run (from GET /api/runs or GET /api/runs/{id}) */
export interface Run {
  run_id: string;
  dataset_name: string;
  status: "pending" | "running" | "complete" | "error";
  timestamp?: string;
  validation_passed?: boolean;
  result?: PipelineResult;
  error?: string | null;
  config?: Record<string, unknown>;
}

/** Pipeline result embedded in a Run */
export interface PipelineResult {
  validation_passed?: boolean;
  exit_reason?: string;
  retry_count?: number;
  quality_metrics?: {
    heuristic_score?: number;
  };
}

/** WebSocket progress message from the server */
export interface ProgressEvent {
  type: "progress" | "complete" | "error";
  agent: string;
  message: string;
  timestamp?: number;
  attempt?: number;
  result?: PipelineResult;
  traceback?: string;
}

/** Response from GET /api/runs/{id}/files/{name} for CSV files */
export interface CsvFileResponse {
  type: "csv";
  filename: string;
  rows: Record<string, unknown>[];
  columns: string[];
  row_count: number;
}

/** Response from GET /api/runs/{id}/files/{name} for text files */
export interface TextFileResponse {
  type: "text";
  filename: string;
  content: string;
}

export type FileResponse = CsvFileResponse | TextFileResponse;

/** Feedback submission */
export interface FeedbackRequest {
  text: string;
  category: string;
  severity: number;
}

/** Pipeline configuration (stored in React state across wizard steps) */
export interface PipelineConfig {
  dataset_name: string;
  model: string;
  max_retries: number;
  enable_mcp: boolean;
  use_schema_examples: boolean;
  human_feedback: string | null;
}

/** Pipeline phases for progress display */
export const PIPELINE_PHASES = [
  "StatePrep",
  "Sampling",
  "SchemaSelectionAgent",
  "Generator",
  "MetadataGenerator",
  "Validator",
  "QualityEvaluator",
  "UnifiedFeedback",
  "MaxRetriesCheck",
] as const;

export const PHASE_LABELS: Record<string, string> = {
  StatePrep: "Preparing state",
  Sampling: "Sampling data",
  SchemaSelectionAgent: "Selecting schema",
  StatVarDiscovery: "Discovering StatVars (MCP)",
  Generator: "Generating PVMAP",
  MetadataGenerator: "Generating metadata config",
  Validator: "Validating PVMAP",
  MCPSpotCheck: "Spot-checking mappings (MCP)",
  MCPErrorResolver: "Resolving errors (MCP)",
  QualityEvaluator: "Evaluating quality",
  UnifiedFeedback: "Generating feedback",
  MaxRetriesCheck: "Checking retry status",
  Evaluation: "Running evaluation",
};
```

- [ ] **Step 2: Create API client**

`frontend/src/lib/api.ts`:
```typescript
/**
 * Typed API client for the FastAPI backend.
 *
 * This is a thin wrapper around `fetch()` that:
 * - Prepends `/api` to all paths
 * - Handles JSON serialization/deserialization
 * - Throws on non-2xx responses with the error detail
 *
 * In Python terms, this is like a `requests.Session()` with a base URL.
 */

import type {
  UploadResponse,
  StartRunRequest,
  Run,
  FileResponse,
  FeedbackRequest,
} from "@/types";

const BASE = "/api";

/** Generic fetch wrapper with error handling. */
async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `Request failed: ${response.status}`);
  }

  return response.json();
}

// ── Upload ─────────────────────────────────────────────

export async function uploadFiles(
  inputCsv: File,
  metadataCsv?: File,
  datasetName?: string
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("input_csv", inputCsv);
  if (metadataCsv) formData.append("metadata_csv", metadataCsv);
  if (datasetName) formData.append("dataset_name", datasetName);

  const response = await fetch(`${BASE}/upload`, {
    method: "POST",
    body: formData,
    // Don't set Content-Type — browser sets it with boundary for multipart
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || "Upload failed");
  }

  return response.json();
}

// ── Runs ───────────────────────────────────────────────

export async function startRun(req: StartRunRequest): Promise<{ run_id: string; status: string }> {
  return request("/runs", { method: "POST", body: JSON.stringify(req) });
}

export async function listRuns(): Promise<Run[]> {
  return request("/runs");
}

export async function getRun(runId: string): Promise<Run> {
  return request(`/runs/${runId}`);
}

// ── Files ──────────────────────────────────────────────

export async function listFiles(runId: string): Promise<{ files: string[] }> {
  return request(`/runs/${runId}/files`);
}

export async function getFile(runId: string, filename: string): Promise<FileResponse> {
  return request(`/runs/${runId}/files/${filename}`);
}

export async function updateFile(
  runId: string,
  filename: string,
  body: { rows?: Record<string, unknown>[] } | { content?: string }
): Promise<{ saved: boolean }> {
  return request(`/runs/${runId}/files/${filename}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function downloadZip(runId: string): Promise<Blob> {
  const response = await fetch(`${BASE}/runs/${runId}/download`);
  if (!response.ok) throw new Error("Download failed");
  return response.blob();
}

// ── Feedback ───────────────────────────────────────────

export async function submitFeedback(
  runId: string,
  feedback: FeedbackRequest
): Promise<{ new_run_id: string }> {
  return request(`/runs/${runId}/feedback`, {
    method: "POST",
    body: JSON.stringify(feedback),
  });
}

export async function submitDevFeedback(
  runId: string,
  text: string,
  category: string
): Promise<{ saved: boolean }> {
  return request(`/runs/${runId}/dev-feedback`, {
    method: "POST",
    body: JSON.stringify({ text, category }),
  });
}

// ── Revalidation ───────────────────────────────────────

export async function revalidate(
  runId: string
): Promise<{ success: boolean; data_rows?: number; error?: string }> {
  return request(`/runs/${runId}/revalidate`, { method: "POST" });
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/nehilsood/work/poc-auto-schematization
git add frontend/src/types/index.ts frontend/src/lib/api.ts
git commit -m "feat(frontend): add TypeScript types and API client"
```

---

## Task 11: WebSocket Hook + App Shell

**Files:**
- Create: `frontend/src/hooks/useWebSocket.ts`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/components/Sidebar.tsx`
- Create: `frontend/src/components/WizardStepper.tsx`

- [ ] **Step 1: Create WebSocket hook**

`frontend/src/hooks/useWebSocket.ts`:
```typescript
/**
 * Custom React hook for WebSocket connections with auto-reconnect.
 *
 * REACT CONCEPT: A "hook" is a function that lets you use React features
 * (like state, side effects) inside a component. Hooks start with "use".
 * This one manages a WebSocket connection lifecycle.
 *
 * useEffect = "run this code when the component mounts or when dependencies change"
 * useState = "this variable re-renders the component when it changes"
 * useCallback = "memoize this function so it doesn't change on every render"
 */
import { useEffect, useRef, useState, useCallback } from "react";
import type { ProgressEvent } from "@/types";

interface UseWebSocketOptions {
  runId: string | null;
  onEvent?: (event: ProgressEvent) => void;
  onComplete?: (event: ProgressEvent) => void;
  onError?: (event: ProgressEvent) => void;
}

export function useWebSocket({ runId, onEvent, onComplete, onError }: UseWebSocketOptions) {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (!runId) return;

    // Build WebSocket URL relative to current host
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws/progress/${runId}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onmessage = (messageEvent) => {
      const event: ProgressEvent = JSON.parse(messageEvent.data);
      setEvents((prev) => [...prev, event]);
      onEvent?.(event);

      if (event.type === "complete") {
        onComplete?.(event);
      } else if (event.type === "error") {
        onError?.(event);
      }
    };

    ws.onclose = () => {
      setConnected(false);
    };

    ws.onerror = () => {
      setConnected(false);
    };
  }, [runId, onEvent, onComplete, onError]);

  // Connect when runId changes
  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { connected, events, clearEvents };
}
```

- [ ] **Step 2: Create WizardStepper component**

`frontend/src/components/WizardStepper.tsx`:
```tsx
/**
 * Visual step indicator for the wizard flow.
 *
 * REACT CONCEPT: This is a "component" — a reusable piece of UI.
 * Components are functions that return JSX (HTML-like syntax).
 * Props are like function arguments — they're how parent components
 * pass data down.
 */

interface Step {
  label: string;
  path: string;
}

const STEPS: Step[] = [
  { label: "Upload", path: "/" },
  { label: "Configure", path: "/configure" },
  { label: "Running", path: "/progress" },
  { label: "Results", path: "/results" },
];

interface WizardStepperProps {
  currentStep: number; // 0-indexed
}

export function WizardStepper({ currentStep }: WizardStepperProps) {
  return (
    <div className="flex items-center gap-2 mb-6">
      {STEPS.map((step, i) => (
        <div key={step.path} className="flex items-center">
          {/* Step circle */}
          <div
            className={`
              flex items-center justify-center w-8 h-8 rounded-full text-sm font-medium
              ${i < currentStep
                ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                : i === currentStep
                  ? "bg-blue-600 text-white"
                  : "bg-muted text-muted-foreground"
              }
            `}
          >
            {i < currentStep ? "✓" : i + 1}
          </div>
          {/* Step label */}
          <span
            className={`ml-2 text-sm ${
              i === currentStep ? "font-medium" : "text-muted-foreground"
            }`}
          >
            {step.label}
          </span>
          {/* Connector line */}
          {i < STEPS.length - 1 && (
            <div
              className={`mx-3 h-px w-8 ${
                i < currentStep ? "bg-green-400" : "bg-border"
              }`}
            />
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Create Sidebar component**

`frontend/src/components/Sidebar.tsx`:
```tsx
/**
 * Persistent sidebar with navigation, history, and status.
 *
 * REACT CONCEPT: `useState` creates a piece of state that, when changed,
 * causes the component to re-render. Think of it as a reactive variable.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { listRuns } from "@/lib/api";
import type { Run } from "@/types";

interface SidebarProps {
  currentRunId: string | null;
  status: string;
  onNewRun: () => void;
}

export function Sidebar({ currentRunId, status, onNewRun }: SidebarProps) {
  const navigate = useNavigate();
  const [history, setHistory] = useState<Run[]>([]);

  // Fetch run history on mount
  useEffect(() => {
    listRuns()
      .then(setHistory)
      .catch(() => setHistory([]));
  }, [status]); // Re-fetch when status changes (new run completed)

  const statusVariant = {
    pending: "secondary",
    running: "default",
    complete: "default",
    error: "destructive",
  }[status] as "secondary" | "default" | "destructive" | undefined;

  return (
    <aside className="w-64 border-r bg-muted/30 flex flex-col h-screen">
      {/* Header */}
      <div className="p-4">
        <h2 className="text-lg font-bold">Agent B</h2>
        <p className="text-xs text-muted-foreground">Auto Schematization</p>
        {status !== "pending" && (
          <Badge variant={statusVariant} className="mt-2">
            {status}
          </Badge>
        )}
        {currentRunId && (
          <p className="text-xs text-muted-foreground mt-1 font-mono">
            {currentRunId.slice(0, 12)}
          </p>
        )}
      </div>

      <Separator />

      {/* Actions */}
      <div className="p-4">
        {(status === "complete" || status === "error") && (
          <Button onClick={onNewRun} variant="outline" className="w-full">
            New Run
          </Button>
        )}
      </div>

      <Separator />

      {/* History */}
      <div className="p-4 flex-1 min-h-0">
        <h3 className="text-sm font-medium mb-2">History</h3>
        <ScrollArea className="h-full">
          {history.length === 0 ? (
            <p className="text-xs text-muted-foreground">No previous runs.</p>
          ) : (
            <div className="space-y-1">
              {history.slice(0, 15).map((run) => (
                <button
                  key={run.run_id}
                  onClick={() => navigate(`/runs/${run.run_id}/results`)}
                  className={`
                    w-full text-left px-2 py-1.5 rounded text-xs hover:bg-accent
                    ${run.run_id === currentRunId ? "bg-accent" : ""}
                  `}
                >
                  <span className="mr-1">
                    {run.validation_passed ? "✓" : "✗"}
                  </span>
                  {run.dataset_name}
                </button>
              ))}
            </div>
          )}
        </ScrollArea>
      </div>
    </aside>
  );
}
```

- [ ] **Step 4: Set up App.tsx with React Router**

Replace `frontend/src/App.tsx`:
```tsx
/**
 * Root application component with routing.
 *
 * REACT CONCEPT: React Router maps URL paths to components ("pages").
 * When the URL changes, only the matching page component renders —
 * the Sidebar stays mounted (persistent). This is called a "layout route".
 */
import { useState, useCallback } from "react";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import { Sidebar } from "@/components/Sidebar";
import type { UploadResponse, PipelineConfig } from "@/types";

// Page components — will be implemented in subsequent tasks
function UploadPage() {
  return <div className="p-8"><h1 className="text-2xl font-bold">Upload Data</h1><p className="text-muted-foreground mt-2">Coming soon...</p></div>;
}
function ConfigurePage() {
  return <div className="p-8"><h1 className="text-2xl font-bold">Configure</h1><p className="text-muted-foreground mt-2">Coming soon...</p></div>;
}
function ProgressPage() {
  return <div className="p-8"><h1 className="text-2xl font-bold">Running</h1><p className="text-muted-foreground mt-2">Coming soon...</p></div>;
}
function ResultsPage() {
  return <div className="p-8"><h1 className="text-2xl font-bold">Results</h1><p className="text-muted-foreground mt-2">Coming soon...</p></div>;
}
function HistoryPage() {
  return <div className="p-8"><h1 className="text-2xl font-bold">History</h1><p className="text-muted-foreground mt-2">Coming soon...</p></div>;
}

function AppLayout() {
  const navigate = useNavigate();
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [status, setStatus] = useState("pending");

  const handleNewRun = useCallback(() => {
    setCurrentRunId(null);
    setStatus("pending");
    navigate("/");
  }, [navigate]);

  return (
    <div className="flex h-screen bg-background text-foreground">
      <Sidebar
        currentRunId={currentRunId}
        status={status}
        onNewRun={handleNewRun}
      />
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/configure" element={<ConfigurePage />} />
          <Route path="/runs/:runId" element={<ProgressPage />} />
          <Route path="/runs/:runId/results" element={<ResultsPage />} />
          <Route path="/history" element={<HistoryPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  );
}
```

- [ ] **Step 5: Verify it builds**

```bash
cd /Users/nehilsood/work/poc-auto-schematization/frontend
npm run build 2>&1 | tail -5
```

Expected: Build succeeds.

- [ ] **Step 6: Commit**

```bash
cd /Users/nehilsood/work/poc-auto-schematization
git add frontend/src/
git commit -m "feat(frontend): add App shell with router, sidebar, wizard stepper, WebSocket hook"
```

---

## Task 12: Upload Page

**Files:**
- Create: `frontend/src/components/FileUploader.tsx`
- Create: `frontend/src/components/DataPreview.tsx`
- Modify: `frontend/src/pages/UploadPage.tsx` (replace placeholder from App.tsx)

- [ ] **Step 1: Create FileUploader component**

`frontend/src/components/FileUploader.tsx`:
```tsx
/**
 * Drag-and-drop file upload component.
 *
 * REACT CONCEPT: `useRef` creates a mutable reference that persists across
 * renders without causing re-renders when changed. Here it holds a reference
 * to the hidden <input> element so we can trigger the file picker programmatically.
 *
 * `DragEvent` handlers implement the browser's drag-and-drop API.
 */
import { useCallback, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

interface FileUploaderProps {
  label: string;
  accept?: string;
  required?: boolean;
  onFileSelect: (file: File) => void;
  selectedFile: File | null;
}

export function FileUploader({
  label,
  accept = ".csv",
  required = false,
  onFileSelect,
  selectedFile,
}: FileUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) onFileSelect(file);
    },
    [onFileSelect]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => setIsDragging(false), []);

  return (
    <Card
      className={`
        p-6 border-2 border-dashed cursor-pointer transition-colors text-center
        ${isDragging ? "border-blue-500 bg-blue-50 dark:bg-blue-950" : "border-border hover:border-muted-foreground"}
      `}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFileSelect(file);
        }}
      />

      {selectedFile ? (
        <div>
          <p className="font-medium">{selectedFile.name}</p>
          <p className="text-sm text-muted-foreground">
            {(selectedFile.size / 1024).toFixed(1)} KB
          </p>
        </div>
      ) : (
        <div>
          <p className="text-muted-foreground">
            Drop {label} here or click to browse
          </p>
          {required && (
            <p className="text-xs text-muted-foreground mt-1">Required</p>
          )}
        </div>
      )}
    </Card>
  );
}
```

- [ ] **Step 2: Create DataPreview component**

`frontend/src/components/DataPreview.tsx`:
```tsx
/**
 * Read-only table preview of uploaded CSV data.
 */
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface DataPreviewProps {
  columns: string[];
  rows: Record<string, unknown>[];
  totalRows: number;
  totalColumns: number;
}

export function DataPreview({ columns, rows, totalRows, totalColumns }: DataPreviewProps) {
  return (
    <div className="rounded-md border">
      <div className="p-2 bg-muted/50 text-xs text-muted-foreground">
        {totalRows} rows x {totalColumns} columns (showing first {rows.length})
      </div>
      <div className="overflow-auto max-h-64">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((col) => (
                <TableHead key={col} className="text-xs whitespace-nowrap">
                  {col}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, i) => (
              <TableRow key={i}>
                {columns.map((col) => (
                  <TableCell key={col} className="text-xs py-1">
                    {String(row[col] ?? "")}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create UploadPage**

Create `frontend/src/pages/UploadPage.tsx`:
```tsx
/**
 * Wizard Step 1: Upload CSV data files.
 *
 * REACT CONCEPT: `useState` creates reactive variables. When you call
 * the setter (e.g., setInputFile), React re-renders this component
 * with the new value. This is how React handles "reactivity" —
 * unlike Streamlit which re-runs the entire script.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { WizardStepper } from "@/components/WizardStepper";
import { FileUploader } from "@/components/FileUploader";
import { DataPreview } from "@/components/DataPreview";
import { uploadFiles } from "@/lib/api";
import type { UploadResponse } from "@/types";

interface UploadPageProps {
  onUploadComplete: (response: UploadResponse) => void;
}

export function UploadPage({ onUploadComplete }: UploadPageProps) {
  const navigate = useNavigate();
  const [inputFile, setInputFile] = useState<File | null>(null);
  const [metadataFile, setMetadataFile] = useState<File | null>(null);
  const [datasetName, setDatasetName] = useState("");
  const [preview, setPreview] = useState<UploadResponse | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // When a CSV is selected, upload immediately to get preview
  const handleInputSelect = async (file: File) => {
    setInputFile(file);
    setError(null);

    // Auto-fill dataset name from filename
    const name = file.name.replace(".csv", "").replace(/\s+/g, "_");
    if (!datasetName) setDatasetName(name);

    // Upload to get preview
    try {
      setUploading(true);
      const response = await uploadFiles(file, metadataFile ?? undefined, name || undefined);
      setPreview(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleNext = () => {
    if (preview) {
      onUploadComplete(preview);
      navigate("/configure");
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <WizardStepper currentStep={0} />

      <h1 className="text-2xl font-bold mb-6">Upload Data</h1>

      <div className="grid grid-cols-2 gap-6 mb-6">
        <div>
          <Label className="mb-2 block">Input CSV (required)</Label>
          <FileUploader
            label="CSV file"
            required
            onFileSelect={handleInputSelect}
            selectedFile={inputFile}
          />
        </div>
        <div>
          <Label className="mb-2 block">Metadata CSV (optional)</Label>
          <FileUploader
            label="metadata CSV"
            onFileSelect={setMetadataFile}
            selectedFile={metadataFile}
          />
        </div>
      </div>

      {/* Dataset name */}
      <div className="mb-6">
        <Label htmlFor="dataset-name" className="mb-2 block">
          Dataset Name
        </Label>
        <Input
          id="dataset-name"
          value={datasetName}
          onChange={(e) => setDatasetName(e.target.value)}
          placeholder="e.g., census_income_data"
        />
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 p-3 bg-destructive/10 text-destructive rounded-md text-sm">
          {error}
        </div>
      )}

      {/* Data preview */}
      {preview && (
        <div className="mb-6">
          <Label className="mb-2 block">Data Preview</Label>
          <DataPreview
            columns={preview.column_names}
            rows={preview.preview}
            totalRows={preview.rows}
            totalColumns={preview.columns}
          />
        </div>
      )}

      {/* Next button */}
      <div className="flex justify-end">
        <Button
          onClick={handleNext}
          disabled={!preview || uploading}
          size="lg"
        >
          {uploading ? "Uploading..." : "Next: Configure"}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Update App.tsx to wire UploadPage**

In `App.tsx`, replace the placeholder `UploadPage` function and update the route to pass props. The full App.tsx will be updated in the final wiring task — for now, just replace the placeholder function body:

```tsx
// Replace the placeholder UploadPage import with the real one:
import { UploadPage } from "@/pages/UploadPage";
```

And update the route:
```tsx
<Route path="/" element={<UploadPage onUploadComplete={(resp) => {
  setCurrentRunId(resp.run_id);
  // Store upload response for configure page
}} />} />
```

- [ ] **Step 5: Verify build**

```bash
cd /Users/nehilsood/work/poc-auto-schematization/frontend && npm run build 2>&1 | tail -5
```

Expected: Build succeeds.

- [ ] **Step 6: Commit**

```bash
cd /Users/nehilsood/work/poc-auto-schematization
git add frontend/src/
git commit -m "feat(frontend): add Upload page with drag-and-drop file uploader and data preview"
```

---

## Task 13: Configure + Progress + Results Pages

This task builds the remaining three wizard pages. Each follows the same pattern as UploadPage — React components that call the API client.

**Files:**
- Create: `frontend/src/pages/ConfigurePage.tsx`
- Create: `frontend/src/pages/ProgressPage.tsx`
- Create: `frontend/src/pages/ResultsPage.tsx`
- Create: `frontend/src/components/ProgressTracker.tsx`
- Create: `frontend/src/components/OutputViewer.tsx`
- Create: `frontend/src/components/CsvEditor.tsx`
- Create: `frontend/src/components/CodeViewer.tsx`
- Create: `frontend/src/components/FeedbackForm.tsx`
- Create: `frontend/src/components/DownloadButton.tsx`

Due to the size of this task, each page is a sub-step. The implementation follows the same patterns established in Task 12 — React components calling the API client via the typed functions in `api.ts`.

- [ ] **Step 1: Create ConfigurePage**

`frontend/src/pages/ConfigurePage.tsx`:
```tsx
/**
 * Wizard Step 2: Configure pipeline settings before running.
 *
 * REACT CONCEPT: "Lifting state up" — the pipeline config is managed in
 * the parent (App.tsx) and passed down as props. When this page changes
 * a setting, it calls the parent's setter. This way multiple pages can
 * share the same config state.
 */
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { WizardStepper } from "@/components/WizardStepper";
import { startRun } from "@/lib/api";
import type { PipelineConfig } from "@/types";

interface ConfigurePageProps {
  runId: string;
  datasetName: string;
  config: PipelineConfig;
  onConfigChange: (config: PipelineConfig) => void;
  onRunStarted: () => void;
}

export function ConfigurePage({
  runId,
  datasetName,
  config,
  onConfigChange,
  onRunStarted,
}: ConfigurePageProps) {
  const navigate = useNavigate();

  const handleStart = async () => {
    try {
      await startRun({
        run_id: runId,
        dataset_name: datasetName,
        model: config.model,
        max_retries: config.max_retries,
        enable_mcp: config.enable_mcp,
        use_schema_examples: config.use_schema_examples,
        human_feedback: config.human_feedback,
      });
      onRunStarted();
      navigate(`/runs/${runId}`);
    } catch (err) {
      console.error("Failed to start run:", err);
    }
  };

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <WizardStepper currentStep={1} />

      <h1 className="text-2xl font-bold mb-6">Configure Pipeline</h1>
      <p className="text-muted-foreground mb-6">
        Dataset: <span className="font-mono font-medium">{datasetName}</span>
      </p>

      <div className="space-y-6">
        {/* Max Retries */}
        <div>
          <Label className="mb-2 block">Max Retries: {config.max_retries}</Label>
          <Slider
            value={[config.max_retries]}
            onValueChange={([v]) => onConfigChange({ ...config, max_retries: v })}
            min={0}
            max={10}
            step={1}
          />
        </div>

        {/* Toggles */}
        <div className="flex gap-8">
          <div className="flex items-center gap-2">
            <Switch
              checked={config.enable_mcp}
              onCheckedChange={(v) => onConfigChange({ ...config, enable_mcp: v })}
            />
            <Label>MCP Discovery</Label>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              checked={config.use_schema_examples}
              onCheckedChange={(v) => onConfigChange({ ...config, use_schema_examples: v })}
            />
            <Label>Schema Examples</Label>
          </div>
        </div>

        {/* Model */}
        <div>
          <Label className="mb-2 block">Model</Label>
          <Input
            value={config.model}
            onChange={(e) => onConfigChange({ ...config, model: e.target.value })}
          />
        </div>

        {/* Human Feedback */}
        <div>
          <Label className="mb-2 block">Initial Feedback (optional)</Label>
          <Textarea
            value={config.human_feedback || ""}
            onChange={(e) =>
              onConfigChange({ ...config, human_feedback: e.target.value || null })
            }
            placeholder="Pre-seed the pipeline with guidance..."
            rows={3}
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex justify-between mt-8">
        <Button variant="outline" onClick={() => navigate("/")}>
          Back
        </Button>
        <Button onClick={handleStart} size="lg">
          Generate PVMAP
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create ProgressTracker component**

`frontend/src/components/ProgressTracker.tsx`:
```tsx
/**
 * Real-time pipeline progress display.
 *
 * Shows a phase checklist with status icons, progress bar, and elapsed time.
 * Receives progress events from the useWebSocket hook.
 */
import { useEffect, useState } from "react";
import { Progress } from "@/components/ui/progress";
import { PIPELINE_PHASES, PHASE_LABELS, type ProgressEvent } from "@/types";

interface ProgressTrackerProps {
  events: ProgressEvent[];
  startTime: number;
}

export function ProgressTracker({ events, startTime }: ProgressTrackerProps) {
  const [elapsed, setElapsed] = useState(0);

  // Update elapsed time every second
  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [startTime]);

  // Track completed agents and current attempt
  const completedAgents = new Set(events.map((e) => e.agent));
  const currentAttempt = Math.max(0, ...events.map((e) => e.attempt ?? 0));

  // Calculate progress
  const allPhases = [...PIPELINE_PHASES];
  const completedCount = allPhases.filter((p) => completedAgents.has(p)).length;
  const progressPct = (completedCount / allPhases.length) * 100;

  // Format elapsed time
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const elapsedStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">
          {currentAttempt > 0 ? `Attempt ${currentAttempt + 1}` : "Pipeline running..."}
        </h2>
        <span className="text-sm text-muted-foreground">Elapsed: {elapsedStr}</span>
      </div>

      {/* Progress bar */}
      <Progress value={progressPct} />
      <p className="text-xs text-muted-foreground">
        {completedCount}/{allPhases.length} phases
      </p>

      {/* Phase checklist */}
      <ul className="space-y-1">
        {allPhases.map((phase) => {
          const label = PHASE_LABELS[phase] || phase;
          const isCompleted = completedAgents.has(phase);
          const isNext =
            !isCompleted &&
            completedCount > 0 &&
            allPhases.indexOf(phase) ===
              allPhases.findIndex((p) => !completedAgents.has(p));

          return (
            <li key={phase} className="flex items-center gap-2 text-sm">
              {isCompleted ? (
                <span className="text-green-600">✓</span>
              ) : isNext ? (
                <span className="text-blue-500 animate-pulse">⟳</span>
              ) : (
                <span className="text-muted-foreground">○</span>
              )}
              <span
                className={
                  isCompleted
                    ? "text-foreground"
                    : isNext
                      ? "text-blue-600 font-medium"
                      : "text-muted-foreground"
                }
              >
                {label}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
```

- [ ] **Step 3: Create ProgressPage**

`frontend/src/pages/ProgressPage.tsx`:
```tsx
/**
 * Wizard Step 3: Real-time pipeline progress.
 */
import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { WizardStepper } from "@/components/WizardStepper";
import { ProgressTracker } from "@/components/ProgressTracker";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { ProgressEvent } from "@/types";

interface ProgressPageProps {
  startTime: number;
  onComplete: (result: ProgressEvent) => void;
  onError: (event: ProgressEvent) => void;
}

export function ProgressPage({ startTime, onComplete, onError }: ProgressPageProps) {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const { events } = useWebSocket({
    runId: runId ?? null,
    onComplete: (event) => {
      onComplete(event);
      navigate(`/runs/${runId}/results`);
    },
    onError,
  });

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <WizardStepper currentStep={2} />
      <ProgressTracker events={events} startTime={startTime} />
    </div>
  );
}
```

- [ ] **Step 4: Create CsvEditor, CodeViewer, FeedbackForm, DownloadButton, OutputViewer**

These components follow the same patterns. Due to length, each file is listed with its core implementation.

`frontend/src/components/CsvEditor.tsx`:
```tsx
/**
 * Editable CSV table using shadcn Table components.
 *
 * REACT CONCEPT: This component receives data as props and reports changes
 * via an onChange callback. It doesn't save to the server itself — that's
 * the parent's responsibility. This pattern is called "controlled component".
 */
import { useState } from "react";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";

interface CsvEditorProps {
  columns: string[];
  rows: Record<string, unknown>[];
  editable?: boolean;
  onChange?: (rows: Record<string, unknown>[]) => void;
}

export function CsvEditor({ columns, rows, editable = false, onChange }: CsvEditorProps) {
  const [editingCell, setEditingCell] = useState<{ row: number; col: string } | null>(null);

  const handleCellChange = (rowIdx: number, col: string, value: string) => {
    if (!onChange) return;
    const newRows = [...rows];
    newRows[rowIdx] = { ...newRows[rowIdx], [col]: value };
    onChange(newRows);
  };

  return (
    <div className="rounded-md border overflow-auto max-h-[500px]">
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((col) => (
              <TableHead key={col} className="text-xs whitespace-nowrap">{col}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, i) => (
            <TableRow key={i}>
              {columns.map((col) => (
                <TableCell key={col} className="py-0.5 px-1">
                  {editable && editingCell?.row === i && editingCell?.col === col ? (
                    <Input
                      className="h-7 text-xs"
                      value={String(row[col] ?? "")}
                      onChange={(e) => handleCellChange(i, col, e.target.value)}
                      onBlur={() => setEditingCell(null)}
                      autoFocus
                    />
                  ) : (
                    <span
                      className="text-xs cursor-default block px-1"
                      onDoubleClick={() => editable && setEditingCell({ row: i, col })}
                    >
                      {String(row[col] ?? "")}
                    </span>
                  )}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
```

`frontend/src/components/CodeViewer.tsx`:
```tsx
/**
 * Read-only code/text viewer with copy button.
 */
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

interface CodeViewerProps {
  content: string;
  language?: string;
}

export function CodeViewer({ content }: CodeViewerProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative rounded-md border bg-muted/30">
      <Button
        variant="ghost"
        size="sm"
        onClick={handleCopy}
        className="absolute top-2 right-2 text-xs"
      >
        {copied ? "Copied" : "Copy"}
      </Button>
      <ScrollArea className="h-[500px]">
        <pre className="p-4 text-xs font-mono whitespace-pre-wrap">{content}</pre>
      </ScrollArea>
    </div>
  );
}
```

`frontend/src/components/FeedbackForm.tsx`:
```tsx
/**
 * Feedback submission form with category and severity.
 */
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";
import { submitFeedback } from "@/lib/api";

const CATEGORIES = [
  "Column mapping", "Property names", "Value formatting",
  "Missing mappings", "Incorrect mappings", "Structural issue", "Other",
];

interface FeedbackFormProps {
  runId: string;
  onRerunStarted: (newRunId: string) => void;
}

export function FeedbackForm({ runId, onRerunStarted }: FeedbackFormProps) {
  const [text, setText] = useState("");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [severity, setSeverity] = useState(3);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!text.trim()) return;
    setSubmitting(true);
    try {
      const resp = await submitFeedback(runId, { text, category, severity });
      onRerunStarted(resp.new_run_id);
    } catch (err) {
      console.error("Feedback submission failed:", err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-medium">Feedback & Re-run</h3>
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Describe what needs to be fixed or improved..."
        rows={4}
      />
      <div className="flex items-center gap-4">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="text-sm border rounded px-2 py-1"
        >
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <div className="flex items-center gap-2 flex-1">
          <Label className="text-sm">Severity: {severity}</Label>
          <Slider
            value={[severity]}
            onValueChange={([v]) => setSeverity(v)}
            min={1} max={5} step={1}
            className="w-32"
          />
        </div>
        <Button onClick={handleSubmit} disabled={!text.trim() || submitting}>
          {submitting ? "Submitting..." : "Re-run with Feedback"}
        </Button>
      </div>
    </div>
  );
}
```

`frontend/src/components/DownloadButton.tsx`:
```tsx
/**
 * ZIP download button for pipeline outputs.
 */
import { Button } from "@/components/ui/button";
import { downloadZip } from "@/lib/api";

interface DownloadButtonProps {
  runId: string;
  datasetName: string;
}

export function DownloadButton({ runId, datasetName }: DownloadButtonProps) {
  const handleDownload = async () => {
    const blob = await downloadZip(runId);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${datasetName}_outputs.zip`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Button variant="outline" onClick={handleDownload}>
      Download ZIP
    </Button>
  );
}
```

`frontend/src/components/OutputViewer.tsx`:
```tsx
/**
 * Tabbed output file viewer. Renders CSVs in CsvEditor, text in CodeViewer.
 */
import { useEffect, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CsvEditor } from "./CsvEditor";
import { CodeViewer } from "./CodeViewer";
import { listFiles, getFile, updateFile, revalidate } from "@/lib/api";
import type { FileResponse, PipelineResult } from "@/types";

const TAB_ORDER = [
  { key: "generated_pvmap.csv", label: "PVMAP" },
  { key: "output_metadata.csv", label: "Metadata Config" },
  { key: "processed.csv", label: "Processed Data" },
  { key: "processed.mcf", label: "MCF" },
  { key: "processed.tmcf", label: "TMCF" },
  { key: "processed_stat_vars.mcf", label: "StatVars" },
  { key: "generation_notes.md", label: "Notes" },
  { key: "processed_counters.txt", label: "Metrics" },
];

interface OutputViewerProps {
  runId: string;
  result?: PipelineResult;
}

export function OutputViewer({ runId, result }: OutputViewerProps) {
  const [availableFiles, setAvailableFiles] = useState<string[]>([]);
  const [fileData, setFileData] = useState<Record<string, FileResponse>>({});
  const [editedRows, setEditedRows] = useState<Record<string, unknown>[] | null>(null);
  const [revalidating, setRevalidating] = useState(false);

  useEffect(() => {
    listFiles(runId).then((resp) => setAvailableFiles(resp.files));
  }, [runId]);

  const loadFile = async (filename: string) => {
    if (fileData[filename]) return;
    const data = await getFile(runId, filename);
    setFileData((prev) => ({ ...prev, [filename]: data }));
  };

  const tabs = TAB_ORDER.filter((t) => availableFiles.includes(t.key));

  const handleSaveAndRevalidate = async () => {
    if (editedRows) {
      await updateFile(runId, "generated_pvmap.csv", { rows: editedRows });
    }
    setRevalidating(true);
    try {
      const result = await revalidate(runId);
      if (result.success) {
        alert(`Validation passed: ${result.data_rows} data rows`);
      } else {
        alert(`Validation failed: ${result.error}`);
      }
    } finally {
      setRevalidating(false);
    }
  };

  return (
    <div>
      {/* Result banner */}
      {result && (
        <div className={`mb-4 p-3 rounded-md text-sm ${result.validation_passed ? "bg-green-50 text-green-800 dark:bg-green-950 dark:text-green-200" : "bg-red-50 text-red-800 dark:bg-red-950 dark:text-red-200"}`}>
          <strong>{(result.retry_count ?? 0) + 1} attempt(s)</strong> — {result.exit_reason}
          {result.quality_metrics?.heuristic_score != null && (
            <Badge variant="outline" className="ml-2">
              Score: {result.quality_metrics.heuristic_score.toFixed(1)}/100
            </Badge>
          )}
        </div>
      )}

      <Tabs defaultValue={tabs[0]?.key} onValueChange={(v) => loadFile(v)}>
        <TabsList>
          {tabs.map((tab) => (
            <TabsTrigger key={tab.key} value={tab.key}>{tab.label}</TabsTrigger>
          ))}
        </TabsList>

        {tabs.map((tab) => (
          <TabsContent key={tab.key} value={tab.key}>
            {fileData[tab.key] ? (
              fileData[tab.key].type === "csv" ? (
                <CsvEditor
                  columns={fileData[tab.key].columns}
                  rows={editedRows && tab.key === "generated_pvmap.csv" ? editedRows : fileData[tab.key].rows}
                  editable={tab.key === "generated_pvmap.csv"}
                  onChange={tab.key === "generated_pvmap.csv" ? setEditedRows : undefined}
                />
              ) : tab.key.endsWith(".md") ? (
                <div className="prose dark:prose-invert max-w-none p-4" dangerouslySetInnerHTML={{ __html: fileData[tab.key].content }} />
              ) : (
                <CodeViewer content={fileData[tab.key].content} />
              )
            ) : (
              <p className="text-sm text-muted-foreground p-4">Loading...</p>
            )}
          </TabsContent>
        ))}
      </Tabs>

      {/* Actions */}
      {availableFiles.includes("generated_pvmap.csv") && (
        <div className="flex justify-center mt-4">
          <Button onClick={handleSaveAndRevalidate} disabled={revalidating}>
            {revalidating ? "Validating..." : "Save & Revalidate"}
          </Button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create ResultsPage**

`frontend/src/pages/ResultsPage.tsx`:
```tsx
/**
 * Wizard Step 4: View results, edit PVMAP, provide feedback.
 */
import { useParams } from "react-router-dom";
import { Separator } from "@/components/ui/separator";
import { WizardStepper } from "@/components/WizardStepper";
import { OutputViewer } from "@/components/OutputViewer";
import { FeedbackForm } from "@/components/FeedbackForm";
import { DownloadButton } from "@/components/DownloadButton";
import type { PipelineResult } from "@/types";

interface ResultsPageProps {
  datasetName: string;
  result?: PipelineResult;
  onRerunStarted: (newRunId: string) => void;
}

export function ResultsPage({ datasetName, result, onRerunStarted }: ResultsPageProps) {
  const { runId } = useParams<{ runId: string }>();

  if (!runId) return null;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <WizardStepper currentStep={3} />

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">
          Results: <span className="font-mono">{datasetName}</span>
        </h1>
        <DownloadButton runId={runId} datasetName={datasetName} />
      </div>

      <OutputViewer runId={runId} result={result} />

      <Separator className="my-6" />

      <FeedbackForm runId={runId} onRerunStarted={onRerunStarted} />
    </div>
  );
}
```

- [ ] **Step 6: Verify build**

```bash
cd /Users/nehilsood/work/poc-auto-schematization/frontend && npm run build 2>&1 | tail -5
```

Expected: Build succeeds (may have type warnings — fix as needed).

- [ ] **Step 7: Commit**

```bash
cd /Users/nehilsood/work/poc-auto-schematization
git add frontend/src/
git commit -m "feat(frontend): add Configure, Progress, Results pages and all UI components"
```

---

## Task 14: Final App.tsx Wiring + Full Integration Test

**Files:**
- Modify: `frontend/src/App.tsx` — wire all pages with shared state
- Modify: `frontend/src/pages/HistoryPage.tsx`

- [ ] **Step 1: Create HistoryPage**

`frontend/src/pages/HistoryPage.tsx`:
```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listRuns } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import type { Run } from "@/types";

export function HistoryPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    listRuns().then(setRuns);
  }, []);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Run History</h1>
      {runs.length === 0 ? (
        <p className="text-muted-foreground">No runs yet.</p>
      ) : (
        <div className="space-y-2">
          {runs.map((run) => (
            <button
              key={run.run_id}
              onClick={() => navigate(`/runs/${run.run_id}/results`)}
              className="w-full text-left p-3 border rounded-md hover:bg-accent flex items-center justify-between"
            >
              <div>
                <span className="font-medium">{run.dataset_name}</span>
                <span className="text-xs text-muted-foreground ml-2 font-mono">
                  {run.run_id.slice(0, 12)}
                </span>
              </div>
              <Badge variant={run.validation_passed ? "default" : "destructive"}>
                {run.validation_passed ? "Passed" : "Failed"}
              </Badge>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire final App.tsx with full state management**

Replace `frontend/src/App.tsx` with the complete version that wires all pages together with shared state. This connects UploadPage → ConfigurePage → ProgressPage → ResultsPage with proper prop passing.

The key state lifted to App level:
- `currentRunId` — set on upload, used by all pages
- `datasetName` — set on upload
- `config` — PipelineConfig, modified by ConfigurePage
- `status` — tracks wizard progress
- `result` — pipeline result from WebSocket terminal event
- `startTime` — for elapsed time tracking

- [ ] **Step 3: Full integration test — start both servers**

Terminal 1 (FastAPI):
```bash
cd /Users/nehilsood/work/poc-auto-schematization
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m uvicorn src.api.main:app --reload --port 8000
```

Terminal 2 (React dev server):
```bash
cd /Users/nehilsood/work/poc-auto-schematization/frontend
npm run dev
```

Open `http://localhost:5173` and verify:
1. Upload page loads with drag-and-drop zone
2. Uploading a CSV shows data preview
3. Configure page shows pipeline settings
4. (Optional) Start a run to test progress + results

- [ ] **Step 4: Build production bundle**

```bash
cd /Users/nehilsood/work/poc-auto-schematization/frontend && npm run build
```

Then test serving from FastAPI:
```bash
cd /Users/nehilsood/work/poc-auto-schematization
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m uvicorn src.api.main:app --port 8000
# Open http://localhost:8000 — should serve the React app
```

- [ ] **Step 5: Commit**

```bash
cd /Users/nehilsood/work/poc-auto-schematization
git add frontend/src/
git commit -m "feat(frontend): wire all pages with shared state, add HistoryPage, complete wizard flow"
```

---

## Task 15: Cleanup — Remove Streamlit, Update Docs

**Files:**
- Delete: `src/ui/` (entire directory)
- Modify: `pyproject.toml` — remove `streamlit` dependency
- Modify: `CLAUDE.md` — update launch commands
- Create: `docs/frontend-guide/01-react-basics.md`
- Create: `docs/frontend-guide/02-typescript-for-python-devs.md`
- Create: `docs/frontend-guide/03-project-structure.md`

- [ ] **Step 1: Remove Streamlit UI**

```bash
rm -rf src/ui/
```

- [ ] **Step 2: Remove streamlit from pyproject.toml**

Remove the line `"streamlit>=1.44.0",` from the `dependencies` list.

- [ ] **Step 3: Sync dependencies**

```bash
uv sync --all-extras
```

- [ ] **Step 4: Run existing tests to ensure nothing broke**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q --ignore=tests/api/
```

Expected: All existing tests pass (tests that imported from `src.ui` will fail — these should be identified and removed or updated).

- [ ] **Step 5: Run API tests**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/ -x -q
```

Expected: All API tests pass.

- [ ] **Step 6: Create learning docs**

Create `docs/frontend-guide/01-react-basics.md`, `02-typescript-for-python-devs.md`, `03-project-structure.md` with explanations of key concepts encountered during implementation. Include Python analogies for each React/TS concept.

- [ ] **Step 7: Update CLAUDE.md**

Update the "Launch Streamlit UI" section to:
```
# Launch UI (development mode — two terminals)
# Terminal 1: Backend
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m uvicorn src.api.main:app --reload --port 8000

# Terminal 2: Frontend (hot reload)
cd frontend && npm run dev

# Launch UI (production mode — single process)
cd frontend && npm run build && cd ..
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m uvicorn src.api.main:app --port 8000
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor: remove Streamlit UI, update docs for React + FastAPI stack"
```

---

## Summary

| Task | What it builds | Key files |
|------|---------------|-----------|
| 1 | Project setup + deps | `pyproject.toml`, `src/api/config.py` |
| 2 | RunState service | `src/api/services/run_state.py` |
| 3 | Refactored services | `src/api/services/*.py` |
| 4 | FastAPI app + upload | `src/api/main.py`, `src/api/routes/upload.py` |
| 5 | Runs route | `src/api/routes/runs.py` |
| 6 | Files route | `src/api/routes/files.py` |
| 7 | Feedback + revalidation | `src/api/routes/feedback.py`, `revalidate.py` |
| 8 | WebSocket progress | `src/api/ws/progress.py` |
| 9 | React scaffolding | `frontend/` project setup |
| 10 | Types + API client | `frontend/src/types/`, `frontend/src/lib/api.ts` |
| 11 | App shell + hooks | `frontend/src/App.tsx`, hooks, sidebar |
| 12 | Upload page | `UploadPage.tsx`, `FileUploader.tsx` |
| 13 | Configure + Progress + Results | All remaining pages and components |
| 14 | Final wiring + integration | `App.tsx` state management, E2E test |
| 15 | Cleanup | Remove `src/ui/`, update docs |

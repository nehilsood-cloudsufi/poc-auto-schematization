"""Pipeline run management endpoints."""
import logging
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

from src.api.services.run_state import (
    create_run,
    delete_run,
    get_run,
    get_or_load_run,
    list_runs,
    read_run_info,
    write_run_info,
)
from src.api.services.file_manager import delete_run_directory, discover_historical_runs
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


class UpdateRunRequest(BaseModel):
    display_name: Optional[str] = None
    notes: Optional[str] = None


@router.get("/runs")
async def list_all_runs(request: Request, include_archived: bool = False):
    """List active runs + historical runs from disk.

    Active (in-memory) runs are always included.  Historical runs on disk are
    enriched with run_info.json fields (display_name, notes, archived) and
    filtered unless include_archived=True.
    """
    output_dir = request.app.state.output_dir
    active = [
        {
            "run_id": r.run_id,
            "dataset_name": r.dataset_name,
            "status": r.status,
            "timestamp": "",
            "validation_passed": r.result.get("validation_passed", False) if r.result else False,
            "result": r.result or {},
        }
        for r in list_runs()
    ]
    historical = discover_historical_runs(base_dir=output_dir)

    # Enrich historical runs with run_info fields and apply archive filter
    active_ids = {r["run_id"] for r in active}
    enriched_historical = []
    for h in historical:
        if h["run_id"] in active_ids:
            continue
        run_dir = output_dir / h["run_id"]
        info = read_run_info(run_dir)
        archived = info.get("archived", False)
        if archived and not include_archived:
            continue
        h["display_name"] = info.get("display_name", h["dataset_name"])
        h["notes"] = info.get("notes", "")
        h["archived"] = archived
        enriched_historical.append(h)

    return active + enriched_historical


@router.get("/runs/{run_id}")
async def get_run_status(run_id: str, request: Request):
    """Get current status and result of a run."""
    output_dir = request.app.state.output_dir
    run = get_or_load_run(run_id, output_dir)
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


@router.patch("/runs/{run_id}")
async def update_run(run_id: str, req: UpdateRunRequest, request: Request):
    """Update display_name and/or notes for a run."""
    output_dir = request.app.state.output_dir
    run_dir = output_dir / run_id
    if not (run_dir / "run_info.json").exists():
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    updates = {}
    if req.display_name is not None:
        updates["display_name"] = req.display_name
    if req.notes is not None:
        updates["notes"] = req.notes

    updated = write_run_info(run_dir, updates)
    return updated


@router.post("/runs/{run_id}/archive")
async def toggle_archive_run(run_id: str, request: Request):
    """Toggle the archived flag for a run. Returns {"archived": bool}."""
    output_dir = request.app.state.output_dir
    run_dir = output_dir / run_id
    info = read_run_info(run_dir)
    if not info:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    new_archived = not info.get("archived", False)
    write_run_info(run_dir, {"archived": new_archived})
    return {"archived": new_archived}


@router.delete("/runs/{run_id}", status_code=204)
async def remove_run(
    run_id: str,
    request: Request,
    x_confirm_delete: Optional[str] = Header(None),
):
    """Permanently delete a run directory and remove it from tracking.

    Requires the X-Confirm-Delete: true header to prevent accidental deletions.
    """
    if x_confirm_delete != "true":
        raise HTTPException(
            status_code=400,
            detail="Missing or invalid X-Confirm-Delete header. Send 'true' to confirm.",
        )

    output_dir = request.app.state.output_dir
    run_dir = output_dir / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    delete_run_directory(str(run_dir))
    delete_run(run_id)
    return Response(status_code=204)


@router.post("/runs")
async def start_run(req: StartRunRequest, request: Request):
    """Start the pipeline for an uploaded dataset."""
    run = get_run(req.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {req.run_id} not found")

    mcp_url = None
    if req.enable_mcp:
        get_or_start_mcp(MCP_DEFAULT_PORT)
        mcp_url = get_mcp_url()

    run_dir = Path(run.run_dir)
    input_dir = run_dir / "input"

    # Check if uploaded file exists directly (UI uploads to input/input.csv,
    # not the test_data/ subfolder the pipeline expects). Use standalone mode
    # so discovery doesn't require the test_data/ directory structure.
    input_file = None
    candidate = input_dir / "input.csv"
    if candidate.exists() and not (input_dir / req.dataset_name / "test_data").exists():
        input_file = str(candidate)

    config = PipelineConfig(
        run_id=req.run_id,
        dataset_name=req.dataset_name,
        input_dir=str(input_dir),
        output_dir=str(run_dir / "output"),
        input_file=input_file,
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
        plan_only=True,
    )

    run.config = config.__dict__
    run.status = "running"

    thread = launch_pipeline(config, run.progress_queue, run_state=run)
    run.thread = thread

    return {"run_id": req.run_id, "status": "running"}

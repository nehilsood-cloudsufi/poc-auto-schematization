"""Pipeline run management endpoints."""
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from src.api.services.run_state import create_run, get_run, get_or_load_run, list_runs
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
    historical = discover_historical_runs(base_dir=output_dir)
    active_ids = {r["run_id"] for r in active}
    combined = active + [h for h in historical if h["run_id"] not in active_ids]
    return combined


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

    return {"run_id": req.run_id, "status": "running"}

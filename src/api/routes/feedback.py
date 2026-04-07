"""Feedback and re-run endpoints."""
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.api.services.run_state import get_or_load_run, create_run
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
async def submit_feedback(run_id: str, req: FeedbackRequest, request: Request):
    """Submit feedback and prepare for re-run.

    Creates a version snapshot, saves feedback, and returns a new run_id
    that the frontend can use to start a re-run via POST /api/runs.
    """
    run = get_or_load_run(run_id, request.app.state.output_dir)
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
async def submit_dev_feedback(run_id: str, req: DevFeedbackRequest, request: Request):
    """Submit developer feedback (bug reports, suggestions)."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
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

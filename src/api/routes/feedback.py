"""Feedback and re-run endpoints."""
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.api.models.feedback import (
    FeedbackType, FeedbackEntry, FeedbackLedger, FeedbackEntryInput,
)
from src.api.services.run_state import get_or_load_run, create_run
from src.api.services.file_manager import (
    get_latest_version,
    snapshot_version,
    save_run_manifest,
)
from src.api.services.feedback_store import (
    save_feedback, load_ledger_from_disk, save_ledger_to_disk,
)
from src.api.services.google_sheets_service import (
    append_feedback_to_sheet,
    is_sheets_configured,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class FeedbackRequest(BaseModel):
    # Legacy fields (backward compat)
    text: Optional[str] = None
    category: Optional[str] = None
    severity: int = 3
    # New structured fields
    entries: Optional[list[FeedbackEntryInput]] = None


class DevFeedbackRequest(BaseModel):
    text: str
    category: str


@router.post("/runs/{run_id}/feedback")
async def submit_feedback(run_id: str, req: FeedbackRequest, request: Request):
    """Submit feedback and prepare for re-run."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    output_dir = Path(run.run_dir) / "output" / run.dataset_name

    # Snapshot current output into the next version slot
    current_version = get_latest_version(output_dir)
    next_version = current_version + 1
    snapshot_version(output_dir, next_version)
    save_run_manifest(output_dir, current_version, run.config, run.result)

    # Load existing ledger (accumulate across rounds)
    ledger = load_ledger_from_disk(output_dir)
    ledger.clear_auto_entries()  # Fresh start for auto-analysis

    # Add new entries to ledger
    if req.entries:
        for ei in req.entries:
            ledger.add_entry(FeedbackEntry(
                type=ei.type,
                round=next_version,
                source="human",
                content=ei.content,
                target=ei.target,
            ))
    elif req.text:
        # Legacy: wrap text+category as a single entry
        entry_input = FeedbackEntryInput.from_legacy(
            category=req.category or "Other",
            content=req.text,
        )
        ledger.add_entry(FeedbackEntry(
            type=entry_input.type,
            round=next_version,
            source="human",
            content=req.text,
            target=entry_input.target,
        ))

    # Build human feedback string (for backward compat)
    if req.text:
        human_feedback = (
            f"USER FEEDBACK: {req.text}\n"
            f"CATEGORY: {req.category or 'Other'}\n"
            f"SEVERITY: {req.severity}\n\n"
            f"Previous run: {run.result.get('retry_count', 0) + 1} attempts, "
            f"exit reason: {run.result.get('exit_reason', 'unknown')}"
        )
    else:
        human_feedback = ""

    # Save feedback JSON + ledger
    feedback_entry = {
        "run_id": run_id,
        "text": req.text or "",
        "category": req.category or "Other",
        "severity": req.severity,
        "dataset_name": run.dataset_name,
    }
    next_feedback_dir = output_dir / f"v{next_version}"
    next_feedback_dir.mkdir(parents=True, exist_ok=True)
    save_feedback(feedback_entry, next_feedback_dir)
    save_ledger_to_disk(ledger, output_dir)

    # Create new run with ledger
    new_run_id = uuid.uuid4().hex[:12]
    new_run = create_run(
        run_id=new_run_id,
        dataset_name=run.dataset_name,
        run_dir=run.run_dir,
        config={
            **run.config,
            "human_feedback": human_feedback,
            "feedback_ledger_json": ledger.model_dump_json(),
            "skip_sampling": True,
        },
    )

    logger.info("Feedback submitted for run %s, new run %s created", run_id, new_run_id)

    return {
        "new_run_id": new_run_id,
        "version": next_version,
        "human_feedback_length": len(human_feedback),
    }


@router.get("/runs/{run_id}/feedback/ledger")
async def get_feedback_ledger(run_id: str, request: Request):
    """Return the full feedback ledger for a run."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    output_dir = Path(run.run_dir) / "output" / run.dataset_name
    ledger = load_ledger_from_disk(output_dir)
    return ledger.model_dump()


@router.delete("/runs/{run_id}/feedback/{entry_id}")
async def retract_feedback_entry(run_id: str, entry_id: str, request: Request):
    """Retract a specific feedback entry."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    output_dir = Path(run.run_dir) / "output" / run.dataset_name
    ledger = load_ledger_from_disk(output_dir)

    if not ledger.retract(entry_id):
        raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found")

    save_ledger_to_disk(ledger, output_dir)
    return {"retracted": True, "entry_id": entry_id}


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

    output_dir = Path(run.run_dir) / "output" / run.dataset_name
    if output_dir.exists():
        save_feedback(entry, output_dir)

    if is_sheets_configured():
        append_feedback_to_sheet(
            run_id=run_id,
            dataset_name=run.dataset_name,
            feedback_text=req.text,
            category=req.category,
            pipeline_status=run.status,
        )

    return {"saved": True}

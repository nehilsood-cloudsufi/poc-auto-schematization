"""Plan review, generate, stop, resume, and data preview endpoints."""
import json
import logging
import queue
import threading
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.api.models.plan import MappingPlan
from src.api.services.run_state import get_run, get_or_load_run

logger = logging.getLogger(__name__)
router = APIRouter()

_note_locks: dict[str, threading.Lock] = {}
_note_locks_lock = threading.Lock()

def _get_note_lock(run_id: str) -> threading.Lock:
    with _note_locks_lock:
        if run_id not in _note_locks:
            _note_locks[run_id] = threading.Lock()
        return _note_locks[run_id]


class GenerateRequest(BaseModel):
    plan: Optional[str] = None  # Edited plan text, or None to use plan from disk


class ApprovePlanRequest(BaseModel):
    plan: dict  # MappingPlan JSON with updated selected_index values


@router.get("/runs/{run_id}/plan")
async def get_plan(run_id: str, request: Request):
    """Return the structured mapping plan as JSON."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run_dir = Path(run.run_dir)
    dataset_name = run.dataset_name

    # Try structured JSON first
    json_path = run_dir / "output" / dataset_name / "mapping_plan.json"
    if json_path.exists():
        raw = json_path.read_text()
        plan_data = json.loads(raw)
        # Try EnrichedMappingPlan first, fall back to MappingPlan
        if "statvar_blueprint" in plan_data:
            from src.api.models.plan import EnrichedMappingPlan
            plan = EnrichedMappingPlan.model_validate(plan_data)
        else:
            plan = MappingPlan.model_validate(plan_data)
        return plan.model_dump()

    # Fall back: check phase1_state.json
    phase1_path = run_dir / "phase1_state.json"
    if phase1_path.exists():
        phase1 = json.loads(phase1_path.read_text())
        plan_json = phase1.get("mapping_plan_json", "")
        if plan_json:
            plan_data = json.loads(plan_json)
            if "statvar_blueprint" in plan_data:
                from src.api.models.plan import EnrichedMappingPlan
                plan = EnrichedMappingPlan.model_validate(plan_data)
            else:
                plan = MappingPlan.model_validate(plan_data)
            return plan.model_dump()

    raise HTTPException(status_code=404, detail="No structured plan found for this run")


@router.put("/runs/{run_id}/plan")
async def update_plan(run_id: str, body: dict, request: Request):
    """Accept full plan edit from user (JSON editor)."""
    from src.api.models.plan import EnrichedMappingPlan

    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Validate against the appropriate model
    try:
        if "statvar_blueprint" in body:
            plan = EnrichedMappingPlan.model_validate(body)
        else:
            plan = MappingPlan.model_validate(body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid plan JSON: {e}")

    # Save to disk
    run_dir = Path(run.run_dir)
    dataset_name = run.dataset_name
    output_dir = run_dir / "output" / dataset_name
    output_dir.mkdir(parents=True, exist_ok=True)

    plan_json_path = output_dir / "mapping_plan.json"
    plan_json_path.write_text(plan.model_dump_json(indent=2))

    # Also update phase1_state if it exists
    phase1_path = run_dir / "phase1_state.json"
    if phase1_path.exists():
        try:
            phase1 = json.loads(phase1_path.read_text())
            phase1["mapping_plan_json"] = plan.model_dump_json()
            phase1_path.write_text(json.dumps(phase1, indent=2))
        except Exception:
            logger.warning("Failed to update phase1_state.json with edited plan")

    return {"status": "ok", "message": "Plan updated"}


@router.post("/runs/{run_id}/plan/approve")
async def approve_plan(run_id: str, body: ApprovePlanRequest, request: Request):
    """Save the engineer's plan selections and prepare for Phase 2."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    plan = MappingPlan.model_validate(body.plan)

    run_dir = Path(run.run_dir)
    dataset_name = run.dataset_name
    output_dir = run_dir / "output" / dataset_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save approved plan JSON
    (output_dir / "approved_plan.json").write_text(plan.model_dump_json(indent=2))

    # Generate PVMAP skeleton from selections
    from src.pipeline.plan.skeleton_converter import plan_to_skeleton_csv
    skeleton_csv = plan_to_skeleton_csv(plan)
    (output_dir / "pvmap_skeleton.csv").write_text(skeleton_csv)

    return {"status": "approved", "skeleton_rows": skeleton_csv.count("\n")}


class RegeneratePlanRequest(BaseModel):
    feedback: str
    deep: bool = False


@router.post("/runs/{run_id}/plan/regenerate")
async def regenerate_plan(run_id: str, body: RegeneratePlanRequest, request: Request):
    """Regenerate the mapping plan with engineer feedback."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if run.status == "running":
        raise HTTPException(status_code=409, detail="Pipeline is already running")

    run_dir = Path(run.run_dir)

    # Read phase1 state
    phase1_path = run_dir / "phase1_state.json"
    if not phase1_path.exists():
        raise HTTPException(status_code=400, detail="Phase 1 not completed")

    phase1 = json.loads(phase1_path.read_text())
    dataset_name = phase1.get("dataset_name", run.dataset_name)

    # Preserve existing engineer_notes
    output_dir = run_dir / "output" / dataset_name
    existing_notes = []
    plan_json_path = output_dir / "mapping_plan.json"
    if plan_json_path.exists():
        try:
            existing_plan = MappingPlan.model_validate_json(plan_json_path.read_text())
            existing_notes = existing_plan.engineer_notes
        except Exception:
            pass

    # Reset run state
    run.cancel_event = threading.Event()
    run.progress_queue = queue.Queue(maxsize=200)
    run.status = "running"
    run.error = None

    from src.api.services.pipeline_runner import PipelineConfig, launch_pipeline

    config = PipelineConfig(
        run_id=run_id,
        dataset_name=dataset_name,
        input_dir=str(run_dir / "input"),
        output_dir=str(run_dir / "output"),
        input_file=run.config.get("input_file") if run.config else None,
        model=run.config.get("model", "gemini-3.1-pro-preview") if run.config else "gemini-3.1-pro-preview",
        skip_sampling=True,
        skip_schema_selection=True,
        plan_only=True,
    )

    # Build extra_state for regeneration
    extra_state = {
        "skeleton_summary": phase1.get("skeleton_summary", ""),
        "schema_category": phase1.get("schema_category", ""),
        "schema_vocab_content": phase1.get("schema_vocab_content", ""),
        "sampled_data_path": phase1.get("sampled_data_path", ""),
        "data_context": phase1.get("data_context", {}),
        "schemaorg_column_mappings": phase1.get("schemaorg_column_mappings", ""),
        "engineer_feedback": body.feedback,
        "engineer_notes_carry": json.dumps(existing_notes),
    }

    if not body.deep:
        # Quick regenerate: reuse existing candidate pool
        extra_state["candidate_pool"] = phase1.get("candidate_pool", "")

    config.extra_state = extra_state

    thread = launch_pipeline(config, run.progress_queue, run_state=run)
    run.thread = thread

    return {"status": "regenerating"}


class AddNoteRequest(BaseModel):
    note: str


@router.post("/runs/{run_id}/plan/notes")
async def add_plan_note(run_id: str, body: AddNoteRequest, request: Request):
    """Append a note to the plan's engineer_notes."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run_dir = Path(run.run_dir)
    dataset_name = run.dataset_name
    output_dir = run_dir / "output" / dataset_name

    lock = _get_note_lock(run_id)
    with lock:
        # Load current plan
        plan_json_path = output_dir / "mapping_plan.json"
        if not plan_json_path.exists():
            raise HTTPException(status_code=400, detail="No plan found")

        plan = MappingPlan.model_validate_json(plan_json_path.read_text())
        plan.engineer_notes.append(body.note)

        # Save updated plan
        plan_json_path.write_text(plan.model_dump_json(indent=2))

        # Also update phase1_state
        phase1_path = run_dir / "phase1_state.json"
        if phase1_path.exists():
            phase1 = json.loads(phase1_path.read_text())
            phase1["mapping_plan_json"] = plan.model_dump_json()
            phase1_path.write_text(json.dumps(phase1, indent=2))

        return {"notes": plan.engineer_notes}


@router.post("/runs/{run_id}/generate")
async def generate_pvmap(run_id: str, body: GenerateRequest, request: Request):
    """Start Phase 2: generate PVMAP from approved plan."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if run.status == "running":
        raise HTTPException(status_code=409, detail="Pipeline is already running")

    run_dir = Path(run.run_dir)

    # Read phase1 state
    phase1_path = run_dir / "phase1_state.json"
    if not phase1_path.exists():
        raise HTTPException(status_code=400, detail="Phase 1 not completed — no phase1_state.json")

    phase1 = json.loads(phase1_path.read_text())
    dataset_name = phase1.get("dataset_name", run.dataset_name)

    # Save approved plan (edited or original)
    output_dir = run_dir / "output" / dataset_name
    output_dir.mkdir(parents=True, exist_ok=True)

    if body.plan:
        plan_path = output_dir / "approved_plan.md"
        plan_path.write_text(body.plan)
    else:
        # Use the plan generated by Phase 1
        plan_path = output_dir / "mapping_plan.md"
        if not plan_path.exists():
            raise HTTPException(status_code=400, detail="No mapping plan found")

    # Reset run state for Phase 2
    run.cancel_event = threading.Event()
    run.plan_approved_event = threading.Event()
    run.progress_queue = queue.Queue(maxsize=200)
    run.status = "running"
    run.error = None

    # Build Phase 2 config
    from src.api.services.pipeline_runner import PipelineConfig, launch_pipeline

    config = PipelineConfig(
        run_id=run_id,
        dataset_name=dataset_name,
        input_dir=str(run_dir / "input"),
        output_dir=str(run_dir / "output"),
        input_file=run.config.get("input_file") if run.config else None,
        model=run.config.get("model", "gemini-3.1-pro-preview") if run.config else "gemini-3.1-pro-preview",
        skip_sampling=True,
        skip_schema_selection=True,
        max_retries=run.config.get("max_retries", 1) if run.config else 1,
        use_schema_examples=run.config.get("use_schema_examples", True) if run.config else True,
        thinking_level=run.config.get("thinking_level") if run.config else None,
        human_feedback=run.config.get("human_feedback") if run.config else None,
    )

    # Add extra_state with plan path and Phase 1 state
    config.extra_state = {
        "from_plan": str(plan_path),
        "skeleton_summary": phase1.get("skeleton_summary", ""),
        "schema_category": phase1.get("schema_category", ""),
        "schema_vocab_content": phase1.get("schema_vocab_content", ""),
        "sampled_data_path": phase1.get("sampled_data_path", ""),
        "data_context": phase1.get("data_context", {}),
        "schemaorg_column_mappings": phase1.get("schemaorg_column_mappings", ""),
        "approved_plan_json": (output_dir / "approved_plan.json").read_text() if (output_dir / "approved_plan.json").exists() else "",
        "pvmap_skeleton": (output_dir / "pvmap_skeleton.csv").read_text() if (output_dir / "pvmap_skeleton.csv").exists() else "",
    }

    thread = launch_pipeline(config, run.progress_queue, run_state=run)
    run.thread = thread

    return {"status": "running"}


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str, request: Request):
    """Cancel a running pipeline."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if run.status != "running":
        raise HTTPException(status_code=409, detail=f"Run is not running (status: {run.status})")

    run.cancel_event.set()
    # Unblock plan approval wait in case pipeline is paused there
    run.plan_approved_event.set()
    run.status = "stopped"
    return {"status": "stopped"}


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str, request: Request):
    """Resume a stopped/completed run from its last checkpoint."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run_dir = Path(run.run_dir)
    checkpoint_path = run_dir / "checkpoint.json"
    if not checkpoint_path.exists():
        raise HTTPException(status_code=400, detail="No checkpoint found for this run")

    checkpoint = json.loads(checkpoint_path.read_text())
    # last_completed_agent is the ADK agent name saved by ProgressTrackingPlugin
    last_agent = checkpoint.get("last_completed_agent", checkpoint.get("last_completed_phase", ""))

    if not run.config:
        raise HTTPException(
            status_code=400,
            detail="Cannot resume: original run configuration is missing (historical run loaded from disk)",
        )

    # Reset events and queue for the new run
    run.cancel_event = threading.Event()
    run.progress_queue = queue.Queue(maxsize=200)
    run.status = "running"
    run.error = None

    # Determine skip flags based on completed phases
    from src.api.services.pipeline_runner import PipelineConfig, launch_pipeline

    # Map agent names to which phases can be skipped
    # Agents run sequentially: Sampling → SchemaSelectionAgent → SchemaOrgEnrichment
    # → MappingPlan → PlanGate → PVMAPRetryLoop (Generator/Validator/Feedback)
    _SAMPLING_DONE = {
        "Sampling", "SchemaSelectionAgent", "SchemaOrgEnrichment",
        "MappingPlan", "PlanGate", "PVMAPRetryLoop",
        "Generator", "Validator", "QualityEvaluator", "UnifiedFeedback", "MaxRetriesCheck",
    }
    _SCHEMA_DONE = {
        "SchemaSelectionAgent", "SchemaOrgEnrichment",
        "MappingPlan", "PlanGate", "PVMAPRetryLoop",
        "Generator", "Validator", "QualityEvaluator", "UnifiedFeedback", "MaxRetriesCheck",
    }

    config = PipelineConfig(
        run_id=run.run_id,
        dataset_name=run.dataset_name,
        input_dir=str(run_dir / "input"),
        output_dir=str(run_dir / "output"),
        skip_sampling=last_agent in _SAMPLING_DONE,
        skip_schema_selection=last_agent in _SCHEMA_DONE,
        **{k: v for k, v in run.config.items() if k in PipelineConfig.__dataclass_fields__ and k not in (
            "run_id", "dataset_name", "input_dir", "output_dir",
            "skip_sampling", "skip_schema_selection",
        )},
    )

    thread = launch_pipeline(config, run.progress_queue, run_state=run)
    run.thread = thread

    return {"status": "running", "resumed_from": last_agent}


@router.get("/runs/{run_id}/preview")
async def preview_data(run_id: str, request: Request, rows: int = 100):
    rows = min(max(rows, 1), 5000)  # Bound to prevent OOM
    """Return a preview of the uploaded CSV data."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    csv_path = Path(run.run_dir) / "input" / "input.csv"
    if not csv_path.exists():
        raise HTTPException(status_code=400, detail="Input CSV not found")

    df_preview = pd.read_csv(csv_path, nrows=rows)

    # Count total rows via pandas for accuracy (handles quoted newlines)
    # Use chunksize to avoid loading entire file into memory for large CSVs
    total_rows = sum(len(chunk) for chunk in pd.read_csv(csv_path, chunksize=10000))

    return {
        "total_rows": total_rows,
        "columns": len(df_preview.columns),
        "column_names": list(df_preview.columns),
        "showing": len(df_preview),
        "data": df_preview.fillna("").to_dict(orient="records"),
    }

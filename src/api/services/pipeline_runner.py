"""Async bridge: runs the ADK pipeline in a background thread (framework-agnostic)."""
from __future__ import annotations

import logging
import queue
import threading
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from src.api.adapters.progress_plugin import ProgressEvent, ProgressTrackingPlugin
from src.api.config import MIN_PIPELINE_ATTEMPTS

if TYPE_CHECKING:
    from src.api.services.run_state import RunState

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
    enable_mcp: bool = False
    mcp_url: Optional[str] = None
    skip_sampling: bool = False
    force_resample: bool = False
    skip_schema_selection: bool = False
    skip_evaluation: bool = True  # No ground truth in UI mode
    use_metadata: bool = False
    metadata_file_path: Optional[str] = None
    human_feedback: Optional[str] = None
    min_attempts: int = MIN_PIPELINE_ATTEMPTS
    max_retries: int = 1
    use_schema_examples: bool = True
    thinking_level: Optional[str] = None
    plan_only: bool = False
    extra_state: dict = field(default_factory=dict)


def launch_pipeline(
    config: PipelineConfig,
    progress_queue: queue.Queue,
    run_state: Optional["RunState"] = None,
) -> threading.Thread:
    """Launch pipeline in a daemon thread. Returns the thread handle."""
    logger.info(
        "Launching pipeline thread: run_id=%s, dataset=%s, model=%s",
        config.run_id, config.dataset_name, config.model,
    )
    thread = threading.Thread(
        target=_run_in_thread,
        args=(config, progress_queue, run_state),
        daemon=True,
        name=f"pipeline-{config.run_id}",
    )
    thread.start()
    return thread


def _run_in_thread(
    config: PipelineConfig,
    progress_queue: queue.Queue,
    run_state: Optional["RunState"] = None,
):
    """Execute the pipeline and push result/error to the queue."""
    try:
        logger.info("Pipeline thread started: run_id=%s", config.run_id)

        # Apply log noise filters in the UI thread context
        from src.pipeline.validation.log_filter import apply_log_noise_filters
        apply_log_noise_filters()

        # Import here to avoid circular imports and ensure .env is loaded
        from src.run_pipeline import run_dataset_pipeline

        # Create progress tracking plugin
        progress_plugin = ProgressTrackingPlugin(progress_queue, run_state=run_state)

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
            plan_only=config.plan_only,
            from_plan=config.extra_state.get("from_plan"),
            extra_initial_state={k: v for k, v in config.extra_state.items() if k != "from_plan"} if config.extra_state else None,
        )

        # Save phase1_state.json for plan_only runs
        if config.plan_only and isinstance(result, dict):
            import json as _json
            run_dir = Path(config.output_dir).parent
            phase1_state = {
                "dataset_name": config.dataset_name,
                "skeleton_summary": result.get("skeleton_summary", ""),
                "schema_category": result.get("schema_category", ""),
                "schema_vocab_content": result.get("schema_vocab_content", ""),
                "mapping_plan": result.get("mapping_plan", ""),
                "mapping_plan_json": result.get("mapping_plan_json", ""),
                "sampled_data_path": result.get("sampled_data_path", ""),
                "data_context": result.get("data_context", {}),
                "schemaorg_column_mappings": result.get("schemaorg_column_mappings", ""),
                "candidate_pool": result.get("candidate_pool", ""),
                "column_analysis": result.get("column_analysis", ""),
            }
            (run_dir / "phase1_state.json").write_text(_json.dumps(phase1_state, indent=2))
            logger.info("Phase 1 state saved to %s", run_dir / "phase1_state.json")

            # Also save mapping_plan.md to output dir so the files endpoint can serve it
            mapping_plan = result.get("mapping_plan", "")
            if mapping_plan:
                dataset_output_dir = Path(config.output_dir) / config.dataset_name
                dataset_output_dir.mkdir(parents=True, exist_ok=True)
                (dataset_output_dir / "mapping_plan.md").write_text(mapping_plan)

            mapping_plan_json = result.get("mapping_plan_json", "")
            if mapping_plan_json:
                dataset_output_dir = Path(config.output_dir) / config.dataset_name
                dataset_output_dir.mkdir(parents=True, exist_ok=True)
                (dataset_output_dir / "mapping_plan.json").write_text(mapping_plan_json)

            # Tag result so frontend can detect plan_only completion
            result["phase"] = "plan"

        logger.info(
            "Pipeline completed: run_id=%s, validation_passed=%s, exit_reason=%s",
            config.run_id,
            result.get("validation_passed") if isinstance(result, dict) else "n/a",
            result.get("exit_reason") if isinstance(result, dict) else "n/a",
        )

        progress_queue.put(ProgressEvent(
            agent_name="Pipeline",
            message="Pipeline completed successfully",
            is_terminal=True,
            metadata={"result": result},
        ))

    except SystemExit as e:
        # Graceful abort (cancel or plan-approval timeout) — not an error.
        # The ProgressTrackingPlugin may have already pushed a terminal event
        # before raising SystemExit, so this is a safety-net event only.
        logger.info("Pipeline aborted gracefully: run_id=%s, reason=%s", config.run_id, e)
        progress_queue.put(ProgressEvent(
            agent_name="Pipeline",
            message=f"Pipeline stopped: {e}",
            is_terminal=True,
            is_error=False,
            metadata={"exit_reason": "user_cancelled"},
        ))

    except Exception as e:
        logger.error(
            "Pipeline failed: run_id=%s, error=%s\n%s",
            config.run_id, e, traceback.format_exc(),
        )
        progress_queue.put(ProgressEvent(
            agent_name="Pipeline",
            message=f"Pipeline failed: {str(e)}",
            is_terminal=True,
            is_error=True,
            metadata={"error": str(e), "traceback": traceback.format_exc()},
        ))

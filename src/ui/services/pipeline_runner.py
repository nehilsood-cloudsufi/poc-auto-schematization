"""Async bridge: runs the ADK pipeline in a background thread."""
import logging
import queue
import threading
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.ui.adapters.progress_plugin import ProgressEvent, ProgressTrackingPlugin
from src.ui.config import MIN_PIPELINE_ATTEMPTS

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for a pipeline run."""
    run_id: str
    dataset_name: str
    input_dir: Path
    output_dir: Path
    input_file: Optional[str] = None
    model: str = "gemini-3-pro-preview"
    enable_mcp: bool = True
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
    prompt_version: str = "v2"
    use_schema_examples: bool = True
    thinking_level: Optional[str] = None
    extra_state: dict = field(default_factory=dict)


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

        # Apply log noise filters in the UI thread context
        from src.pipeline.validation.log_filter import apply_log_noise_filters
        apply_log_noise_filters()

        # Import here to avoid circular imports and ensure .env is loaded
        from src.run_pipeline import run_dataset_pipeline

        # Create progress tracking plugin
        progress_plugin = ProgressTrackingPlugin(progress_queue)

        result = run_dataset_pipeline(
            dataset_name=config.dataset_name,
            input_dir=config.input_dir,
            output_dir=config.output_dir,
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
            prompt_version=config.prompt_version,
            use_schema_examples=config.use_schema_examples,
            thinking_level=config.thinking_level,
        )

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

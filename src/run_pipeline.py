"""ADK pipeline runner with comprehensive logging.

Supports optional MCP integration for enhanced StatVar discovery.

Usage:
    # Without MCP
    python src/run_pipeline.py --dataset=my_dataset

    # With MCP (starts/stops server automatically)
    python src/run_pipeline.py --dataset=my_dataset --enable-mcp
"""
import sys
import os
from pathlib import Path

# Setup project root FIRST
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Load .env file BEFORE any other imports (critical for API keys)
from dotenv import load_dotenv
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"Loaded environment from {env_path}")

# Setup sys.path before any other imports
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))
sys.path.insert(0, str(PROJECT_ROOT / "util"))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from google.adk import Runner
from google.adk.agents import SequentialAgent
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types
from src.utils.logging_config import setup_adk_logging, setup_python_logging
from src.utils.artifact_plugin import ArtifactLoggingPlugin
from src.agents.discovery_agent import DiscoveryAgent
from src.agents.sampling_agent import ProgrammaticSamplingAgent
from src.agents.schema_selection_agent import create_schema_selection_agent
from src.agents.pvmap_retry_loop import create_pvmap_retry_loop
from src.agents.evaluation_agent import EvaluationAgent
from src.agents.llm_judge_agent import LLMJudgeAgent
from typing import Optional, Dict, Any
import uuid
import logging
import asyncio

logger = logging.getLogger(__name__)

# Per-attempt timeout (seconds). The total pipeline timeout is calculated as
# (max_retries + 1) * PER_ATTEMPT_TIMEOUT. This scales with retry count —
# a 3-retry run gets 45 min, a 2-retry run gets 30 min, a 1-retry run gets 15 min.
PER_ATTEMPT_TIMEOUT = int(os.getenv("PER_ATTEMPT_TIMEOUT", "900"))  # 15 min default


async def _run_pipeline_async(runner, user_id, session_id, user_message, events_out, pipeline_logger=None):
    """Run the ADK pipeline using async API with proper MCP cleanup and stall detection.

    Uses manual __anext__() instead of `async for` to control cleanup order:
    1. Consume all events (with 300s stall detection)
    2. Call runner.close() to tear down MCP connections (10s/toolset)
    3. Close the generator (fast — MCP already gone)

    A separate heartbeat task logs progress every 120s so logs are never
    silent for long. The main event loop uses a 300s per-event timeout that
    BREAKS on timeout (never continues) — this is critical because
    asyncio.wait_for cancels the underlying coroutine, which corrupts the
    async generator if reused.

    Args:
        events_out: Mutable list — events are appended here so they survive
                    cancellation/timeout (the caller retains the reference).
        pipeline_logger: Optional logger with per-dataset handlers. Falls back
                         to the module-level logger if not provided.
    """
    _log = pipeline_logger or logger
    gen = runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_message,
    )

    # Heartbeat task: logs progress every 120s so logs are never silent
    async def _heartbeat():
        while True:
            await asyncio.sleep(120)
            _log.info("Heartbeat: %d events collected so far.", len(events_out))

    heartbeat_task = asyncio.create_task(_heartbeat())
    try:
        while True:
            try:
                # 300s per-event timeout: detect genuine stalls.
                # IMPORTANT: Do NOT reduce this timeout or add `continue` after
                # TimeoutError — asyncio.wait_for cancels gen.__anext__() on
                # timeout, which corrupts the async generator's internal state.
                event = await asyncio.wait_for(gen.__anext__(), timeout=300)
                events_out.append(event)
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                _log.warning(
                    "No event received in 300s (%d events so far). "
                    "Pipeline may be stalled — breaking event loop.",
                    len(events_out),
                )
                break
            except Exception as e:
                _log.error(
                    "Unexpected error from event stream (%d events so far): %s",
                    len(events_out), e,
                )
                break

        _log.info("Event consumption done (%d total). Closing runner...", len(events_out))
        try:
            await asyncio.wait_for(runner.close(), timeout=30)
            _log.info("Runner closed successfully.")
        except (asyncio.TimeoutError, Exception) as e:
            _log.warning("Runner close failed (non-fatal): %s", e)
    finally:
        heartbeat_task.cancel()
        # Close the async generator. MCP connections are already torn down
        # by runner.close(), so this should complete quickly.
        try:
            await asyncio.wait_for(gen.aclose(), timeout=15)
        except (asyncio.TimeoutError, Exception) as e:
            _log.warning("Generator close error (non-fatal): %s", e)


# MCP integration (optional)
try:
    from src.data_commons.api.mcp_server_manager import MCPServerManager
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

# Suppress noisy third-party log messages
from src.pipeline.validation.log_filter import apply_log_noise_filters
apply_log_noise_filters()


def get_session_state_direct(
    session_service: InMemorySessionService,
    app_name: str,
    user_id: str,
    session_id: str
) -> Dict[str, Any]:
    """
    Get session state directly from internal storage.

    InMemorySessionService.get_session() returns a COPY of the session,
    which doesn't include state changes made by agents during execution.
    This function accesses the internal storage directly to get the
    actual persisted state.

    Args:
        session_service: The InMemorySessionService instance
        app_name: Application name
        user_id: User ID
        session_id: Session ID

    Returns:
        Dictionary of session state (empty dict if session not found)
    """
    try:
        # Access internal storage: sessions[app_name][user_id][session_id]
        stored_session = session_service.sessions.get(app_name, {}).get(user_id, {}).get(session_id)
        if stored_session and hasattr(stored_session, 'state'):
            return dict(stored_session.state)
        return {}
    except Exception:
        logger.exception("Failed to retrieve session state for session_id=%s", session_id)
        return {}


def create_runner(
    root_agent,
    output_dir: Path,
    dataset_name: Optional[str] = None,
    session_id: Optional[str] = None,
    extra_plugins: Optional[list] = None,
) -> Runner:
    """
    Create ADK runner with full logging setup.

    Args:
        root_agent: Root agent for pipeline
        output_dir: Output directory (e.g., src/output/)
        dataset_name: Current dataset name (optional, for artifact logging)
        session_id: Session identifier (optional, will generate if not provided)

    Returns:
        Configured Runner with logging plugins
    """
    # Generate session ID if not provided
    if session_id is None:
        session_id = str(uuid.uuid4())[:8]

    # Setup ADK logging plugins (Layer 1)
    base_plugins = setup_adk_logging(
        output_dir=output_dir,
        session_id=session_id,
        console_logging=True,
        debug_logging=True
    )

    # Add artifact logging plugin (Layer 2) if dataset specified
    if dataset_name:
        artifact_plugin = ArtifactLoggingPlugin(
            output_dir=output_dir,
            dataset_name=dataset_name
        )
        all_plugins = base_plugins + [artifact_plugin]
    else:
        all_plugins = base_plugins

    # Add extra plugins (e.g., progress tracking for UI)
    if extra_plugins:
        all_plugins = all_plugins + list(extra_plugins)

    # Create runner with auto_create_session
    runner = Runner(
        app_name="agents",
        agent=root_agent,
        session_service=InMemorySessionService(),
        plugins=all_plugins,
        auto_create_session=True
    )

    return runner


def run_discovery(
    input_dir: Path,
    output_dir: Path,
    use_metadata: bool = False,
    ground_truth_repo: Optional[str] = None,
) -> dict:
    """
    Run discovery phase with logging.

    Args:
        input_dir: Input directory containing datasets
        output_dir: Output directory for logs
        use_metadata: Whether to use metadata files
        ground_truth_repo: Path to ground truth repository

    Returns:
        Result dictionary with discovered datasets
    """
    session_id = f"discovery_{uuid.uuid4().hex[:8]}"

    # Create discovery agent
    discovery_agent = DiscoveryAgent(name="Discovery")

    # Create runner with logging
    runner = create_runner(
        root_agent=discovery_agent,
        output_dir=output_dir,
        session_id=session_id
    )

    # Use simpler approach: encode input_dir in the message for the agent to extract
    # OR set it directly in the session service after auto-creation

    # Step 1: First run with dummy message to force session auto-creation
    dummy_message = types.Content(parts=[types.Part(text="Initialize")])
    for _ in runner.run(user_id="pipeline_user", session_id=session_id, new_message=dummy_message):
        pass

    # Step 2: Get the session properly using async and modify its state
    async def set_session_state():
        session = await runner.session_service.get_session(
            session_id=session_id,
            user_id="pipeline_user",
            app_name="agents"
        )
        if session:
            session.state["input_dir"] = str(input_dir)
            session.state["use_metadata"] = use_metadata
            session.state["ground_truth_repo"] = ground_truth_repo
            return True
        return False

    asyncio.run(set_session_state())

    # Step 3: Run actual discovery
    user_message = types.Content(parts=[types.Part(text="Discover datasets")])
    events = []
    for event in runner.run(user_id="pipeline_user", session_id=session_id, new_message=user_message):
        events.append(event)

    # Get final state directly from internal storage
    return get_session_state_direct(
        session_service=runner.session_service,
        app_name="agents",
        user_id="pipeline_user",
        session_id=session_id
    )


def run_dataset_pipeline(
    dataset_name: str,
    input_dir: Path,
    output_dir: Path,
    schema_base_dir: Optional[Path] = None,
    model: str = "gemini-3.1-pro-preview",
    enable_mcp: bool = False,
    mcp_url: Optional[str] = None,
    skip_sampling: bool = False,
    force_resample: bool = False,
    skip_schema_selection: bool = False,
    force_schema_selection: bool = False,
    ground_truth_pvmap: Optional[str] = None,
    ground_truth_dir: Optional[str] = None,
    ground_truth_repo: Optional[str] = None,
    skip_evaluation: bool = False,
    input_file: Optional[str] = None,
    use_metadata: bool = False,
    metadata_file_path: Optional[str] = None,
    schema_file: Optional[str] = None,
    use_schema_examples: bool = True,
    human_feedback: Optional[str] = None,
    min_attempts: Optional[int] = None,
    max_retries: int = 2,
    extra_plugins: Optional[list] = None,
    thinking_level: Optional[str] = None,
    skip_column_discovery: bool = False,
    use_llm_judge: bool = False,
    prompt_version: str = "v3",
    feedback_prompt_version: str = "v1",
) -> dict:
    """
    Run full pipeline for a single dataset with comprehensive logging.

    Args:
        dataset_name: Dataset name
        input_dir: Input directory
        output_dir: Output directory
        schema_base_dir: Schema examples directory (optional)
        model: Gemini model to use for generation
        enable_mcp: Enable MCP integration for StatVar discovery
        mcp_url: MCP server URL (required if enable_mcp=True)
        skip_sampling: If True, skip agentic sampling phase
        force_resample: If True, force re-run sampling even if cached
        skip_schema_selection: If True, skip schema selection phase
        force_schema_selection: If True, force re-run schema selection
        ground_truth_pvmap: Explicit GT PVMAP file path (highest precedence)
        ground_truth_dir: Directory to search for GT PVMAPs
        ground_truth_repo: GT repository path (lowest precedence, default)
        skip_evaluation: If True, skip evaluation phase
        input_file: Standalone input file path (no dataset folder required)
        use_metadata: Whether to use metadata for prompt building
        metadata_file_path: Explicit metadata file path (auto-enables use_metadata)
        schema_file: Explicit schema file override
        use_schema_examples: If True (default), inject schema examples into PVMAP prompt
        human_feedback: Optional human feedback text to inject as initial error_feedback
        min_attempts: Minimum pipeline attempts before allowing quality exit
        max_retries: Max retry attempts after initial generation (default: 2, for 3 total)
        extra_plugins: Additional ADK plugins (e.g., progress tracking for UI)
    Returns:
        Final state dictionary
    """
    # Generate session ID early for logging
    session_id = f"{dataset_name}_{uuid.uuid4().hex[:8]}"

    # Setup Python logging for compatibility (Layer 3) - do this first so logger is available
    logger = setup_python_logging(
        output_dir=output_dir,
        session_id=session_id,
        level=logging.DEBUG
    )

    logger.info(f"Starting PVMAP pipeline for dataset: {dataset_name}")
    logger.info(
        "Pipeline config: model=%s, enable_mcp=%s, skip_sampling=%s, "
        "skip_schema=%s, skip_eval=%s, use_metadata=%s, max_retries=%d",
        model, enable_mcp, skip_sampling, skip_schema_selection,
        skip_evaluation, use_metadata, max_retries,
    )

    # Create Sampling agent (programmatic, code-orchestrated)
    sampling_agent = ProgrammaticSamplingAgent(
        name="Sampling",
        model=os.getenv("SAMPLING_AGENT_MODEL", "gemini-3.1-pro-preview"),
        enable_mcp=enable_mcp,
        mcp_url=mcp_url,
    )
    logger.info("Using ProgrammaticSamplingAgent (code-orchestrated)")

    # Create PVMAP retry loop (ADK LoopAgent-based)
    pvmap_agent = create_pvmap_retry_loop(
        model=model,
        max_retries=max_retries,
        name="PVMAPRetryLoop",
        enable_mcp=enable_mcp,
        mcp_url=mcp_url,
        min_attempts=min_attempts,
        thinking_level=thinking_level,
        feedback_prompt_version=feedback_prompt_version,
    )
    logger.info("Using ADK LoopAgent-based PVMAP retry loop")
    if enable_mcp and mcp_url:
        logger.info("MCP integration: INSIDE retry loop (loop-aware discovery + error resolution)")

    # Create evaluation agent and LLM judge
    evaluation_agent = EvaluationAgent(name="Evaluation")
    llm_judge_agent = LLMJudgeAgent(name="LLMJudge")

    # Build sub_agents list - Sampling first, then StatVar discovery, then generation, then evaluation
    sub_agents = [sampling_agent]
    logger.info("SamplingAgent added to pipeline")

    # Add SchemaSelectionAgent if not skipped (Phase 2.5)
    if not skip_schema_selection:
        schema_agent = create_schema_selection_agent(model=model)
        sub_agents.append(schema_agent)
        logger.info("SchemaSelectionAgent added to pipeline")
    else:
        logger.info("SchemaSelectionAgent skipped (--skip-schema-selection)")

    # Note: StatVarDiscoveryAgent is now INSIDE the retry loop (loop-aware).
    # It was previously here as a pre-pipeline agent. With MCP inside the loop,
    # discovery happens on every attempt with error-driven refinement.

    # Add generation, evaluation, and LLM judge
    sub_agents.extend([pvmap_agent, evaluation_agent, llm_judge_agent])

    # Create a sequential agent to run the pipeline
    # With MCP: StatVarDiscovery -> PVMAPGeneration -> Evaluation
    # Without MCP: PVMAPGeneration -> Evaluation
    pipeline_agent = SequentialAgent(
        name="GenerationAndEvaluation",
        sub_agents=sub_agents
    )

    # Create runner with dataset-specific artifact logging
    runner = create_runner(
        root_agent=pipeline_agent,
        output_dir=output_dir,
        dataset_name=dataset_name,
        session_id=session_id,
        extra_plugins=extra_plugins,
    )

    # Auto-enable use_metadata if metadata_file_path is provided
    if metadata_file_path:
        use_metadata = True

    # Discover dataset files using DiscoveryAgent helper
    discovery_agent = DiscoveryAgent(name="Discovery")

    if input_file:
        # Standalone mode
        current_dataset = discovery_agent._discover_standalone(
            input_file=Path(input_file),
            output_base_dir=output_dir,
            use_metadata=use_metadata,
            metadata_file=Path(metadata_file_path) if metadata_file_path else None,
            schema_file=Path(schema_file) if schema_file else None,
        )
    else:
        # Normal dataset folder mode
        dataset_path = input_dir / dataset_name
        current_dataset = discovery_agent._discover_single_dataset(
            dataset_path=dataset_path,
            dataset_name=dataset_name,
            use_metadata=use_metadata,
            metadata_file_override=Path(metadata_file_path) if metadata_file_path else None,
            schema_file_override=Path(schema_file) if schema_file else None,
            ground_truth_repo=Path(ground_truth_repo) if ground_truth_repo else None,
        )

    current_dataset.output_dir = output_dir / dataset_name

    logger.info(f"Discovered dataset: {current_dataset}")

    # Read sampled data content for session state (StatVarDiscoveryAgent needs this)
    sampled_data_content = ""
    sampled_data_path = None
    if current_dataset.sampled_data_files:
        sampled_data_path = current_dataset.sampled_data_files[0]

    if sampled_data_path and sampled_data_path.exists():
        with open(sampled_data_path, 'r') as f:
            sampled_data_content = f.read()

    # Read metadata content for session state (only if use_metadata flag is enabled)
    metadata_content = ""
    if current_dataset.use_metadata and current_dataset.metadata_files:
        metadata_path = current_dataset.metadata_files[0]
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata_content = f.read()

    # Initial state with DatasetInfo object
    # Use dataset-specific output_dir so EvaluationAgent saves results in correct location
    initial_state = {
        "input_dir": str(input_dir),
        "output_dir": str(current_dataset.output_dir),  # Dataset-specific output dir
        "dataset_name": dataset_name,
        "current_dataset": current_dataset,
        "model": model,  # LLM model name for artifact logging
        "sampled_data_content": sampled_data_content,  # For StatVar discovery
        "metadata_content": metadata_content,          # For StatVar discovery
        # Sampling agent flags
        "skip_sampling": skip_sampling,
        "force_resample": force_resample,
        # Schema selection agent flags
        "skip_schema_selection": skip_schema_selection,
        "force_schema_selection": force_schema_selection,
        # Ground truth configuration (precedence: pvmap > dir > repo)
        "ground_truth_pvmap": ground_truth_pvmap,
        "ground_truth_dir": ground_truth_dir,
        "ground_truth_repo": ground_truth_repo or str(PROJECT_ROOT / "ground_truth"),
        # Evaluation flags
        "skip_evaluation": skip_evaluation,
        "skip_llm_judge": not use_llm_judge,
        # Column discovery flag
        "skip_column_discovery": skip_column_discovery,
        # Default data_context (may be updated by SamplingAgent)
        "data_context": {},
        # New discovery flags
        "use_metadata": use_metadata,
        "input_file": input_file,
        "metadata_file_path": metadata_file_path,
        "schema_file": schema_file,
        # Schema examples control
        "use_schema_examples": use_schema_examples,
        "prompt_version": prompt_version,
        "feedback_prompt_version": feedback_prompt_version,
    }

    # Inject human feedback if provided (for UI re-runs)
    if human_feedback:
        initial_state["error_feedback"] = human_feedback
        initial_state["human_feedback_provided"] = True

    # Always set schema_base_dir in state (agents need it for tool calls)
    if schema_base_dir:
        initial_state["schema_base_dir"] = str(schema_base_dir)
    else:
        initial_state["schema_base_dir"] = str(PROJECT_ROOT / "src" / "resources" / "schema_examples")

    # Add MCP state if enabled
    if enable_mcp and mcp_url:
        initial_state["mcp_enabled"] = True
        initial_state["mcp_url"] = mcp_url
        logger.info(f"MCP enabled with URL: {mcp_url}")

    # Log sampling configuration
    if skip_sampling:
        logger.info("Agentic sampling: SKIPPED (using existing sampled files)")
    elif force_resample:
        logger.info("Agentic sampling: ENABLED (force resample)")
    else:
        logger.info("Agentic sampling: ENABLED (will use cache if available)")

    # Run pipeline
    try:
        # Use runner.run_async() instead of runner.run() to avoid the sync
        # wrapper's asyncio.run() shutdown hang when MCP connections are active.
        # See ADK docs: "Consider using run_async for production usage."
        import time
        MAX_PIPELINE_RETRIES = 2

        user_message = types.Content(parts=[types.Part(text=f"Generate PVMAP for {dataset_name}")])
        events = []  # Shared mutable list — survives timeout

        # Dynamic timeout: scales with retry count
        pipeline_timeout = (max_retries + 1) * PER_ATTEMPT_TIMEOUT
        logger.info("Pipeline timeout: %ds (%d attempts x %ds)",
                     pipeline_timeout, max_retries + 1, PER_ATTEMPT_TIMEOUT)

        async def _create_session_and_run():
            # Create session with initial state
            await runner.session_service.create_session(
                app_name="agents",
                user_id="pipeline_user",
                state=initial_state,
                session_id=session_id,
            )
            logger.info("Session created with initial state, current_dataset set")

            # Run pipeline with dynamic timeout (safety net).
            # On normal completion, runner.close() already ran inside
            # _run_pipeline_async. The finally block handles the timeout case.
            try:
                await asyncio.wait_for(
                    _run_pipeline_async(
                        runner, "pipeline_user", session_id, user_message, events,
                        pipeline_logger=logger,
                    ),
                    timeout=pipeline_timeout,
                )
            except asyncio.CancelledError:
                logger.warning("Pipeline task was cancelled (%d events collected).", len(events))
            finally:
                # Belt-and-suspenders: close runner for timeout case.
                # On normal completion, runner.close() already ran inside
                # _run_pipeline_async — calling it again is idempotent.
                # On timeout, this is the only cleanup that runs (the cancelled
                # task's runner.close() gets CancelledError).
                try:
                    await asyncio.wait_for(runner.close(), timeout=30)
                except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as e:
                    logger.warning("Runner cleanup in finally (non-fatal): %s", e)

        for pipeline_attempt in range(MAX_PIPELINE_RETRIES + 1):
            try:
                # Use explicit event loop instead of asyncio.run() to avoid
                # shutdown_asyncgens/shutdown_default_executor deadlocks when
                # MCP connections are open in daemon threads.
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(_create_session_and_run())
                finally:
                    # Cancel pending tasks but skip shutdown_asyncgens
                    # (which deadlocks when MCP connections are open).
                    try:
                        pending = asyncio.all_tasks(loop)
                        for task in pending:
                            task.cancel()
                        if pending:
                            loop.run_until_complete(
                                asyncio.gather(*pending, return_exceptions=True)
                            )
                    except Exception as e:
                        logger.warning("Event loop cleanup error (non-fatal): %s", e)
                    finally:
                        loop.close()
                break  # Success — exit retry loop
            except asyncio.TimeoutError:
                logger.error(
                    "Pipeline timed out after %ds (%d attempts x %ds). "
                    "Collected %d events before timeout.",
                    pipeline_timeout, max_retries + 1, PER_ATTEMPT_TIMEOUT,
                    len(events),
                )
                break  # Timeout = proceed to artifact check, don't retry
            except Exception as e:
                err_str = str(e)
                is_transient = any(s in err_str for s in [
                    "429", "RESOURCE_EXHAUSTED", "500", "502", "503", "504",
                    "Internal Server Error", "ServiceUnavailable",
                ])
                if is_transient and pipeline_attempt < MAX_PIPELINE_RETRIES:
                    logger.warning(
                        "Transient API error (attempt %d/%d): %s. Sleeping 60s...",
                        pipeline_attempt + 1, MAX_PIPELINE_RETRIES + 1, e
                    )
                    time.sleep(60)
                    events.clear()
                else:
                    raise

        # ADK's InMemorySessionService doesn't persist agent state changes back
        # to the stored session. Instead, determine success by checking artifacts.
        final_state = get_session_state_direct(
            session_service=runner.session_service,
            app_name="agents",
            user_id="pipeline_user",
            session_id=session_id
        )

        # Determine success by checking actual artifacts
        pvmap_path = current_dataset.output_dir / "generated_pvmap.csv"
        processed_path = current_dataset.output_dir / "processed.csv"

        # Check if PVMAP was generated
        pvmap_exists = pvmap_path.exists() and pvmap_path.stat().st_size > 0

        # Check if validation produced output with data rows
        validation_passed = False
        if processed_path.exists():
            with open(processed_path, 'r') as f:
                lines = [l for l in f.readlines() if l.strip()]
                validation_passed = len(lines) > 1  # More than just header

        generation_success = pvmap_exists and validation_passed

        # Check for evaluation results
        eval_results_dir = current_dataset.output_dir / "eval_results"
        eval_results_path = eval_results_dir / "diff_results.json"
        eval_results_exist = eval_results_path.exists()

        eval_metrics = None
        if eval_results_exist:
            try:
                import json
                with open(eval_results_path, 'r') as f:
                    eval_metrics = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load eval_results.json: {e}")

        # Update final state with artifact-based success determination
        final_state["generation_success"] = generation_success
        final_state["pvmap_path"] = str(pvmap_path) if pvmap_exists else None
        final_state["validation_passed"] = validation_passed
        final_state["eval_results_exist"] = eval_results_exist
        if eval_metrics:
            final_state["eval_metrics"] = eval_metrics

        exit_reason = final_state.get("exit_reason", "unknown")
        attempt_count = final_state.get("retry_count", "?")
        data_rows = final_state.get("validation_data_rows", 0)
        logger.info(f"Pipeline completed for {dataset_name}. Success: {generation_success}")
        logger.info(f"  Exit reason: {exit_reason}, Attempts: {attempt_count}, Data rows: {data_rows}")
        logger.info(f"  PVMAP exists: {pvmap_exists}, Validation passed: {validation_passed}")
        logger.info(f"  Eval results exist: {eval_results_exist}")
        if eval_metrics:
            nodes_matched = eval_metrics.get('nodes-matched', 0)
            nodes_gt = eval_metrics.get('nodes-ground-truth', 0)
            pvs_matched = eval_metrics.get('PVs-matched', 0)
            pvs_modified = eval_metrics.get('pvs-modified', 0)
            pvs_deleted = eval_metrics.get('pvs-deleted', 0)
            pvs_total = pvs_matched + pvs_modified + pvs_deleted
            node_acc = (nodes_matched / nodes_gt * 100) if nodes_gt > 0 else 0
            pv_acc = (pvs_matched / pvs_total * 100) if pvs_total > 0 else 0
            logger.info(f"  Node accuracy: {node_acc:.1f}% ({nodes_matched}/{nodes_gt})")
            logger.info(f"  PV accuracy: {pv_acc:.1f}%")
        logger.info(f"Received {len(events)} events from execution")

        return final_state

    except Exception as e:
        logger.error(f"Pipeline failed for {dataset_name}: {str(e)}", exc_info=True)
        raise


# Example usage
if __name__ == "__main__":
    import sys
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="ADK PVMAP Generation Pipeline")
    parser.add_argument("--dataset", "-d", type=str, default=None,
                        help="Dataset name to process")
    parser.add_argument("--output-dir", "-o", type=str, default=None,
                        help="Output directory (default: output/)")
    parser.add_argument("--input-dir", "-i", type=str, default=None,
                        help="Input directory (default: input/)")
    parser.add_argument("--model", "-m", type=str, default="gemini-3.1-pro-preview",
                        help="Gemini model to use (default: gemini-3.1-pro-preview)")
    parser.add_argument("--thinking-level", type=str,
                        choices=["low", "medium", "high", "minimal", "none"],
                        default="high",
                        help="Thinking level for Gemini models (default: high). Use 'none' to disable.")
    # MCP integration flags
    parser.add_argument("--enable-mcp", action="store_true",
                        help="Enable MCP integration for Data Commons StatVar discovery")
    parser.add_argument("--mcp-port", type=int, default=None,
                        help="MCP server port (default: from MCP_PORT env or 3000)")
    parser.add_argument("--no-mcp", action="store_true",
                        help="Explicitly disable MCP (overrides --enable-mcp)")
    # Sampling agent flags
    parser.add_argument("--skip-sampling", action="store_true",
                        help="Skip agentic sampling phase (use existing sampled files)")
    parser.add_argument("--force-resample", action="store_true",
                        help="Force re-run of agentic sampling even if cached context exists")
    # Schema selection flags
    parser.add_argument("--skip-schema-selection", action="store_true",
                        help="Skip schema selection phase (use existing schema files)")
    parser.add_argument("--force-schema-selection", action="store_true",
                        help="Force re-run schema selection even if files exist")
    # Ground truth flags (precedence: pvmap > dir > repo)
    parser.add_argument("--ground-truth-pvmap", type=str, default=None,
                        help="Path to explicit ground truth PVMAP file (highest priority)")
    parser.add_argument("--ground-truth-dir", type=str, default=None,
                        help="Path to directory with ground truth PVMAPs")
    parser.add_argument("--ground-truth-repo", type=str,
                        default=os.environ.get('GROUND_TRUTH_REPO', str(PROJECT_ROOT / 'ground_truth')),
                        help="Path to ground truth repository (default: ground_truth/)")
    # Evaluation flags
    parser.add_argument("--skip-evaluation", action="store_true",
                        help="Skip evaluation phase (no ground truth comparison)")
    # Standalone file mode
    parser.add_argument("--input-file", type=str, default=None,
                        help="Path to standalone input file (no dataset folder required)")
    # Metadata control
    parser.add_argument("--use-metadata", action="store_true",
                        help="Use metadata files for prompt building (default: off)")
    parser.add_argument("--metadata-file-path", type=str, default=None,
                        help="Path to explicit metadata file (auto-enables --use-metadata)")
    # Schema file override
    parser.add_argument("--schema-file", type=str, default=None,
                        help="Path to explicit schema file override")
    # Schema examples control
    parser.add_argument("--no-schema-examples", action="store_true",
                        help="Skip injecting schema examples into PVMAP generation prompt")
    parser.add_argument("--schema-base-dir", type=str, default=None,
                        help="Override schema examples base directory")
    # Column discovery flags
    parser.add_argument("--skip-column-discovery", action="store_true",
                        help="Skip PVMAP skeleton generation (disables column completeness checking)")
    # LLM judge
    parser.add_argument("--use-llm-judge", action="store_true",
                        help="Enable LLM-as-judge qualitative evaluation")
    # Dry run
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would be processed without executing")
    # Prompt version
    parser.add_argument("--prompt-version", choices=["v2", "v3"], default="v3",
                        help="PVMAP prompt version to use (default: v3)")
    parser.add_argument("--feedback-prompt-version", choices=["v1", "v2"], default="v1",
                        help="Feedback agent prompt version (default: v1)")
    args = parser.parse_args()

    # Validation: --input-file and --dataset are mutually exclusive
    if args.input_file and args.dataset:
        parser.error("--input-file and --dataset are mutually exclusive")

    # Validation: --metadata-file-path auto-enables use_metadata
    if args.metadata_file_path:
        args.use_metadata = True

    # Validation: verify explicit file paths exist
    if args.input_file and not Path(args.input_file).exists():
        parser.error(f"Input file not found: {args.input_file}")
    if args.metadata_file_path and not Path(args.metadata_file_path).exists():
        parser.error(f"Metadata file not found: {args.metadata_file_path}")
    if args.schema_file and not Path(args.schema_file).exists():
        parser.error(f"Schema file not found: {args.schema_file}")

    # Setup paths
    base_dir = Path(__file__).parent.parent
    input_dir = Path(args.input_dir) if args.input_dir else base_dir / "input"
    output_dir = Path(args.output_dir) if args.output_dir else base_dir / "output"

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine MCP settings
    enable_mcp = args.enable_mcp and not args.no_mcp
    mcp_port = args.mcp_port or int(os.getenv("MCP_PORT", "3000"))
    mcp_manager = None
    mcp_url = None

    # Get dataset name from command line, standalone file, or discovery
    if args.input_file:
        from src.pipeline.discovery.file_utils import derive_dataset_name
        dataset_name = derive_dataset_name(Path(args.input_file))
        print(f"Standalone mode: derived dataset name '{dataset_name}' from {args.input_file}")
    elif args.dataset:
        dataset_name = args.dataset
    else:
        # Run discovery to find datasets
        print("Running discovery...")
        discovery_result = run_discovery(
            input_dir, output_dir,
            use_metadata=args.use_metadata,
            ground_truth_repo=args.ground_truth_repo,
        )
        datasets = discovery_result.get("datasets", [])

        if not datasets:
            print("No datasets found!")
            sys.exit(1)

        # Use first dataset
        dataset_name = datasets[0].name
        print(f"No dataset specified, using first discovered: {dataset_name}")

    # Dry-run mode: preview what would be processed without executing
    if args.dry_run:
        print("\n" + "=" * 60)
        print("[DRY RUN] Preview - no changes will be made")
        print("=" * 60)
        print(f"Would process dataset: {dataset_name}")
        if args.input_file:
            print(f"  Input file: {args.input_file} (standalone mode)")
        else:
            print(f"  Input directory: {input_dir / dataset_name}")
        print(f"  Output directory: {output_dir / dataset_name}")
        print(f"  Model: {args.model}")
        print(f"  Use metadata: {args.use_metadata}")
        print(f"  Skip sampling: {args.skip_sampling}")
        print(f"  Skip schema selection: {args.skip_schema_selection}")
        print(f"  Skip evaluation: {args.skip_evaluation}")
        print(f"  Use LLM judge: {getattr(args, 'use_llm_judge', False)}")
        print(f"  Ground truth repo: {args.ground_truth_repo}")
        if args.ground_truth_pvmap:
            print(f"  Ground truth PVMAP: {args.ground_truth_pvmap}")
        if args.ground_truth_dir:
            print(f"  Ground truth directory: {args.ground_truth_dir}")
        if args.metadata_file_path:
            print(f"  Metadata file: {args.metadata_file_path}")
        if args.schema_file:
            print(f"  Schema file: {args.schema_file}")
        sys.exit(0)

    # Run pipeline for dataset
    print(f"\nRunning pipeline for: {dataset_name}")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Model: {args.model}")
    print(f"Generation mode: ADK LoopAgent")
    if enable_mcp:
        print(f"MCP integration: ENABLED (port {mcp_port})")
    else:
        print(f"MCP integration: disabled")
    print("-" * 60)

    try:
        # Start MCP server if enabled
        if enable_mcp:
            if not MCP_AVAILABLE:
                print("WARNING: MCP integration requested but datacommons-mcp not installed.")
                print("         Install with: pip install datacommons-mcp")
                print("         Continuing without MCP...")
                enable_mcp = False
            else:
                print("Starting MCP server...")
                mcp_manager = MCPServerManager(port=mcp_port)
                if mcp_manager.start(timeout=30):
                    mcp_url = mcp_manager.mcp_url
                    print(f"MCP server started at: {mcp_url}")
                else:
                    print("WARNING: MCP server failed to start. Continuing without MCP.")
                    enable_mcp = False
                    mcp_manager = None

        final_state = run_dataset_pipeline(
            dataset_name=dataset_name,
            input_dir=input_dir,
            output_dir=output_dir,
            model=args.model,
            enable_mcp=enable_mcp,
            mcp_url=mcp_url,
            skip_sampling=args.skip_sampling,
            force_resample=args.force_resample,
            skip_schema_selection=args.skip_schema_selection,
            force_schema_selection=args.force_schema_selection,
            ground_truth_pvmap=args.ground_truth_pvmap,
            ground_truth_dir=args.ground_truth_dir,
            ground_truth_repo=args.ground_truth_repo,
            skip_evaluation=args.skip_evaluation,
            input_file=args.input_file,
            use_metadata=args.use_metadata,
            metadata_file_path=args.metadata_file_path,
            schema_file=args.schema_file,
            use_schema_examples=not args.no_schema_examples,
            schema_base_dir=Path(args.schema_base_dir) if args.schema_base_dir else None,
            thinking_level=args.thinking_level,
            skip_column_discovery=getattr(args, 'skip_column_discovery', False),
            use_llm_judge=getattr(args, 'use_llm_judge', False),
            prompt_version=getattr(args, 'prompt_version', 'v3'),
            feedback_prompt_version=getattr(args, 'feedback_prompt_version', 'v1'),
        )

        print("\n" + "=" * 60)
        print("Pipeline Complete!")
        print("=" * 60)
        print(f"Generation success: {final_state.get('generation_success', False)}")
        print(f"Validation passed: {final_state.get('validation_passed', False)}")

        if final_state.get('error'):
            print(f"Error: {final_state['error']}")

        # Display evaluation metrics if available
        if final_state.get('eval_results_exist'):
            print("\nEvaluation Results:")
            eval_metrics = final_state.get('eval_metrics', {})
            # Compute accuracy from counters
            nodes_matched = eval_metrics.get('nodes-matched', 0)
            nodes_gt = eval_metrics.get('nodes-ground-truth', 0)
            pvs_matched = eval_metrics.get('PVs-matched', 0)
            pvs_modified = eval_metrics.get('pvs-modified', 0)
            pvs_deleted = eval_metrics.get('pvs-deleted', 0)
            pvs_total = pvs_matched + pvs_modified + pvs_deleted

            node_acc = (nodes_matched / nodes_gt * 100) if nodes_gt > 0 else 0
            pv_acc = (pvs_matched / pvs_total * 100) if pvs_total > 0 else 0

            print(f"  Node accuracy: {node_acc:.1f}%")
            print(f"  PV accuracy: {pv_acc:.1f}%")
            print(f"  Nodes matched: {nodes_matched}/{nodes_gt}")
            print(f"  Eval results: {output_dir}/{dataset_name}/eval_results/")
        else:
            print("\nEvaluation: No ground truth found or evaluation skipped")

        # Display LLM Judge results if available
        llm_judge = final_state.get('llm_judge_report', {})
        if llm_judge and not llm_judge.get('error'):
            struct = llm_judge.get('structural_quality', {}).get('score', '?')
            sem = llm_judge.get('semantic_accuracy', {}).get('score', '?')
            val = llm_judge.get('value_mapping_quality', {}).get('score', '?')
            overall = llm_judge.get('overall_score', '?')
            print(f"\nLLM Judge: Structural={struct}/5, Semantic={sem}/5, Values={val}/5 (Overall: {overall}/5)")
            top_issues = llm_judge.get('top_issues', [])
            if top_issues:
                print("  Top issues:")
                for issue in top_issues[:3]:
                    print(f"    - {issue}")

        print(f"\nLogs location: {output_dir}/logs/")
        print(f"Artifacts location: {output_dir}/{dataset_name}/")

        # Exit with non-zero if validation failed (distinct from crash exit code 1)
        if not final_state.get('validation_passed', False):
            sys.exit(2)

    except Exception as e:
        print(f"\n❌ Pipeline failed: {str(e)}")
        sys.exit(1)

    finally:
        # Clean up MCP servers
        if mcp_manager:
            print("\nStopping MCP server...")
            mcp_manager.stop()
            print("MCP server stopped.")

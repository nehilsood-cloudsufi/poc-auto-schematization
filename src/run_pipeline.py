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
from src.agents.sampling_agent import create_sampling_agent, SamplingAgent, SamplingAgentWrapper
from src.agents.schema_selection_agent import create_schema_selection_agent
from src.agents.pvmap_generation_agent import PVMAPGenerationAgent
from src.agents.pvmap_retry_loop import create_pvmap_retry_loop
from src.agents.evaluation_agent import EvaluationAgent
from typing import Optional, Dict, Any
import uuid
import logging
import asyncio

# MCP integration (optional)
try:
    from src.data_commons.api.mcp_server_manager import MCPServerManager
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


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
        return {}


def create_runner(
    root_agent,
    output_dir: Path,
    dataset_name: Optional[str] = None,
    session_id: Optional[str] = None
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

    # Create runner with auto_create_session
    runner = Runner(
        app_name="agents",
        agent=root_agent,
        session_service=InMemorySessionService(),
        plugins=all_plugins,
        auto_create_session=True
    )

    return runner


def run_discovery(input_dir: Path, output_dir: Path) -> dict:
    """
    Run discovery phase with logging.

    Args:
        input_dir: Input directory containing datasets
        output_dir: Output directory for logs

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
    use_structured_output: bool = False,
    model: str = "gemini-3-pro-preview",
    enable_mcp: bool = False,
    mcp_url: Optional[str] = None,
    skip_sampling: bool = False,
    force_resample: bool = False
) -> dict:
    """
    Run full pipeline for a single dataset with comprehensive logging.

    Args:
        dataset_name: Dataset name
        input_dir: Input directory
        output_dir: Output directory
        schema_base_dir: Schema examples directory (optional)
        use_structured_output: If True, use structured JSON output with deterministic CSV conversion
        model: Gemini model to use for generation
        enable_mcp: Enable MCP integration for StatVar discovery
        mcp_url: MCP server URL (required if enable_mcp=True)
        skip_sampling: If True, skip agentic sampling phase
        force_resample: If True, force re-run sampling even if cached

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

    # Create Sampling agent (agentic sampling with LLM)
    sampling_agent = SamplingAgentWrapper(
        name="Sampling",
        model=os.getenv("SAMPLING_AGENT_MODEL", "gemini-2.5-pro")
    )

    # Create PVMAP generation agent or retry loop based on structured_output flag
    if use_structured_output:
        # Use new ADK LoopAgent-based retry loop with structured output
        pvmap_agent = create_pvmap_retry_loop(
            model=model,
            max_retries=2,  # 3 total attempts
            use_structured_output=True,
            name="PVMAPRetryLoop"
        )
        logger.info("Using ADK LoopAgent-based PVMAP retry loop with structured output")
    else:
        # Use original BaseAgent-based generation
        pvmap_agent = PVMAPGenerationAgent(
            name="PVMAPGeneration",
            use_structured_output=False,
            model=model
        )
        logger.info("Using BaseAgent-based PVMAPGenerationAgent")

    # Create evaluation agent
    evaluation_agent = EvaluationAgent(name="Evaluation")

    # Build sub_agents list - Sampling first, then StatVar discovery, then generation, then evaluation
    sub_agents = [sampling_agent]
    logger.info("SamplingAgentWrapper added to pipeline")

    # Add StatVarDiscoveryAgent if MCP is enabled (for pre-generation StatVar discovery)
    if enable_mcp and mcp_url:
        try:
            from src.agents.statvar_discovery_agent import StatVarDiscoveryAgent
            statvar_discovery = StatVarDiscoveryAgent(
                name="StatVarDiscovery",
                model=model
            )
            sub_agents.append(statvar_discovery)
            logger.info("StatVarDiscoveryAgent added to pipeline")
        except ImportError as e:
            logger.warning(f"StatVarDiscoveryAgent not available: {e}")

    # Add generation and evaluation
    sub_agents.extend([pvmap_agent, evaluation_agent])

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
        session_id=session_id
    )

    # Discover dataset files using DiscoveryAgent helper
    dataset_path = input_dir / dataset_name
    discovery_agent = DiscoveryAgent(name="Discovery")
    current_dataset = discovery_agent._discover_single_dataset(dataset_path, dataset_name)
    current_dataset.output_dir = output_dir / dataset_name

    logger.info(f"Discovered dataset: {current_dataset}")

    # Read sampled data content for session state (StatVarDiscoveryAgent needs this)
    sampled_data_content = ""
    if current_dataset.combined_sampled_data and Path(current_dataset.combined_sampled_data).exists():
        with open(current_dataset.combined_sampled_data, 'r') as f:
            sampled_data_content = f.read()

    # Read metadata content for session state
    metadata_content = ""
    if current_dataset.combined_metadata and Path(current_dataset.combined_metadata).exists():
        with open(current_dataset.combined_metadata, 'r') as f:
            metadata_content = f.read()

    # Initial state with DatasetInfo object
    # Use dataset-specific output_dir so EvaluationAgent saves results in correct location
    initial_state = {
        "input_dir": str(input_dir),
        "output_dir": str(current_dataset.output_dir),  # Dataset-specific output dir
        "dataset_name": dataset_name,
        "current_dataset": current_dataset,
        "sampled_data_content": sampled_data_content,  # For StatVar discovery
        "metadata_content": metadata_content,          # For StatVar discovery
        # Sampling agent flags
        "skip_sampling": skip_sampling,
        "force_resample": force_resample,
    }

    if schema_base_dir:
        initial_state["schema_base_dir"] = str(schema_base_dir)

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
        # Step 1: Create session with initial state BEFORE running
        async def create_session_with_state():
            session = await runner.session_service.create_session(
                app_name="agents",
                user_id="pipeline_user",
                state=initial_state,
                session_id=session_id
            )
            return session

        asyncio.run(create_session_with_state())
        logger.info(f"Session created with initial state, current_dataset set")

        # Step 2: Run the pipeline with the prepared session
        user_message = types.Content(parts=[types.Part(text=f"Generate PVMAP for {dataset_name}")])
        events = []
        for event in runner.run(
            user_id="pipeline_user",
            session_id=session_id,
            new_message=user_message
        ):
            events.append(event)

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

        logger.info(f"Pipeline completed for {dataset_name}. Success: {generation_success}")
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
    parser.add_argument("--structured-output", "-s", action="store_true",
                        help="Use structured JSON output from LLM with deterministic CSV conversion")
    parser.add_argument("--model", "-m", type=str, default="gemini-3-pro-preview",
                        help="Gemini model to use (default: gemini-3-pro-preview)")
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
    args = parser.parse_args()

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

    # Get dataset name from command line or use default
    if args.dataset:
        dataset_name = args.dataset
    else:
        # Run discovery to find datasets
        print("Running discovery...")
        discovery_result = run_discovery(input_dir, output_dir)
        datasets = discovery_result.get("datasets", [])

        if not datasets:
            print("No datasets found!")
            sys.exit(1)

        # Use first dataset
        dataset_name = datasets[0].name
        print(f"No dataset specified, using first discovered: {dataset_name}")

    # Run pipeline for dataset
    print(f"\nRunning pipeline for: {dataset_name}")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Model: {args.model}")
    if args.structured_output:
        print(f"Generation mode: ADK LoopAgent with structured output")
    else:
        print(f"Generation mode: BaseAgent (legacy)")
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
            use_structured_output=args.structured_output,
            model=args.model,
            enable_mcp=enable_mcp,
            mcp_url=mcp_url,
            skip_sampling=args.skip_sampling,
            force_resample=args.force_resample
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

        print(f"\nLogs location: {output_dir}/logs/")
        print(f"Artifacts location: {output_dir}/{dataset_name}/")

    except Exception as e:
        print(f"\n❌ Pipeline failed: {str(e)}")
        sys.exit(1)

    finally:
        # Clean up MCP server
        if mcp_manager:
            print("\nStopping MCP server...")
            mcp_manager.stop()
            print("MCP server stopped.")

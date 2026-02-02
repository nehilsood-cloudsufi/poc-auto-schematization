"""ADK pipeline runner with comprehensive logging."""
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
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types
from src.utils.logging_config import setup_adk_logging, setup_python_logging
from src.utils.artifact_plugin import ArtifactLoggingPlugin
from src.agents.discovery_agent import DiscoveryAgent
from src.agents.sampling_agent import SamplingAgent
from src.agents.schema_selection_agent import create_schema_selection_agent
from src.agents.pvmap_generation_agent import PVMAPGenerationAgent
from src.agents.evaluation_agent import EvaluationAgent
from typing import Optional, Dict, Any
import uuid
import logging
import asyncio


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
    model: str = "gemini-3-pro-preview"
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

    Returns:
        Final state dictionary
    """
    # Create PVMAP generation agent as root
    pvmap_agent = PVMAPGenerationAgent(
        name="PVMAPGeneration",
        use_structured_output=use_structured_output,
        model=model
    )

    # Create runner with dataset-specific artifact logging
    session_id = f"{dataset_name}_{uuid.uuid4().hex[:8]}"
    runner = create_runner(
        root_agent=pvmap_agent,
        output_dir=output_dir,
        dataset_name=dataset_name,
        session_id=session_id
    )

    # Setup Python logging for compatibility (Layer 3)
    logger = setup_python_logging(
        output_dir=output_dir,
        session_id=session_id,
        level=logging.DEBUG
    )

    logger.info(f"Starting PVMAP pipeline for dataset: {dataset_name}")

    # Discover dataset files using DiscoveryAgent helper
    dataset_path = input_dir / dataset_name
    discovery_agent = DiscoveryAgent(name="Discovery")
    current_dataset = discovery_agent._discover_single_dataset(dataset_path, dataset_name)
    current_dataset.output_dir = output_dir / dataset_name

    logger.info(f"Discovered dataset: {current_dataset}")

    # Initial state with DatasetInfo object
    initial_state = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "dataset_name": dataset_name,
        "current_dataset": current_dataset,
    }

    if schema_base_dir:
        initial_state["schema_base_dir"] = str(schema_base_dir)

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

        # Update final state with artifact-based success determination
        final_state["generation_success"] = generation_success
        final_state["pvmap_path"] = str(pvmap_path) if pvmap_exists else None
        final_state["validation_passed"] = validation_passed

        logger.info(f"Pipeline completed for {dataset_name}. Success: {generation_success}")
        logger.info(f"  PVMAP exists: {pvmap_exists}, Validation passed: {validation_passed}")
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
    args = parser.parse_args()

    # Setup paths
    base_dir = Path(__file__).parent.parent
    input_dir = Path(args.input_dir) if args.input_dir else base_dir / "input"
    output_dir = Path(args.output_dir) if args.output_dir else base_dir / "output"

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

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
    print("-" * 60)

    try:
        final_state = run_dataset_pipeline(
            dataset_name=dataset_name,
            input_dir=input_dir,
            output_dir=output_dir,
            use_structured_output=args.structured_output,
            model=args.model
        )

        print("\n" + "=" * 60)
        print("Pipeline Complete!")
        print("=" * 60)
        print(f"Generation success: {final_state.get('generation_success', False)}")

        if final_state.get('error'):
            print(f"Error: {final_state['error']}")

        print(f"\nLogs location: {output_dir}/logs/")
        print(f"Artifacts location: {output_dir}/{dataset_name}/")

    except Exception as e:
        print(f"\n❌ Pipeline failed: {str(e)}")
        sys.exit(1)

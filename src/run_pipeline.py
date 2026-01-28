"""ADK pipeline runner with comprehensive logging."""
import sys
import os
from pathlib import Path

# Setup sys.path before any other imports
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
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
from typing import Optional
import uuid
import logging
import asyncio


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

    # Get final state using async
    async def get_final_state_async():
        session = await runner.session_service.get_session(
            session_id=session_id,
            user_id="pipeline_user",
            app_name="agents"
        )
        return session.state if session else {}

    return asyncio.run(get_final_state_async())


def run_dataset_pipeline(
    dataset_name: str,
    input_dir: Path,
    output_dir: Path,
    schema_base_dir: Optional[Path] = None
) -> dict:
    """
    Run full pipeline for a single dataset with comprehensive logging.

    Args:
        dataset_name: Dataset name
        input_dir: Input directory
        output_dir: Output directory
        schema_base_dir: Schema examples directory (optional)

    Returns:
        Final state dictionary
    """
    # Create PVMAP generation agent as root
    pvmap_agent = PVMAPGenerationAgent(name="PVMAPGeneration")

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

    # Initial state
    initial_state = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "dataset_name": dataset_name,
    }

    if schema_base_dir:
        initial_state["schema_base_dir"] = str(schema_base_dir)

    # Run pipeline
    try:
        # Step 1: Dummy run to force session auto-creation
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
                session.state.update(initial_state)
                return True
            return False

        asyncio.run(set_session_state())

        # Step 3: Run actual pipeline
        user_message = types.Content(parts=[types.Part(text=f"Generate PVMAP for {dataset_name}")])
        events = []
        for event in runner.run(
            user_id="pipeline_user",
            session_id=session_id,
            new_message=user_message
        ):
            events.append(event)

        # Get final state using async
        async def get_final_state_async():
            session = await runner.session_service.get_session(
                session_id=session_id,
                user_id="pipeline_user",
                app_name="agents"
            )
            return session.state if session else {}

        final_state = asyncio.run(get_final_state_async())

        logger.info(f"Pipeline completed for {dataset_name}. Success: {final_state.get('generation_success', False)}")
        logger.info(f"Received {len(events)} events from execution")

        return final_state

    except Exception as e:
        logger.error(f"Pipeline failed for {dataset_name}: {str(e)}", exc_info=True)
        raise


# Example usage
if __name__ == "__main__":
    import sys

    # Setup paths
    base_dir = Path(__file__).parent.parent
    input_dir = base_dir / "src" / "input"
    output_dir = base_dir / "src" / "output"

    # Get dataset name from command line or use default
    if len(sys.argv) > 1:
        dataset_name = sys.argv[1]
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
            output_dir=output_dir
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

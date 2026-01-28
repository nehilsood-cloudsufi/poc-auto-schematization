"""
Pipeline Coordinator for ADK pipeline.

Uses SequentialAgent to orchestrate all pipeline phases.
No custom class needed - just configuration!
"""

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import SequentialAgent

from src.agents.discovery_agent import DiscoveryAgent
from src.agents.sampling_agent import SamplingAgent
from src.agents.schema_selection_agent import create_schema_selection_agent
from src.agents.pvmap_generation_agent import PVMAPGenerationAgent
from src.agents.evaluation_agent import EvaluationAgent


def create_pipeline_coordinator(
    name: str = "PipelineCoordinator",
    max_retries: int = 2,
    model: str = "gemini-3-pro-preview"
) -> SequentialAgent:
    """
    Create pipeline coordinator using SequentialAgent.

    The coordinator orchestrates all pipeline phases in sequence:
    1. Discovery - Scan input directory for datasets
    2. Sampling - Create representative data samples
    3. Schema Selection - Choose appropriate schema category
    4. PVMAP Generation - Generate and validate PVMAP with retry loop
    5. Evaluation - Compare against ground truth

    Each agent checks its own skip flags in ctx.session.state:
    - skip_sampling: bool
    - skip_schema_selection: bool
    - skip_evaluation: bool

    Args:
        name: Coordinator name (default: "PipelineCoordinator")
        max_retries: Max retries for PVMAP generation (default: 2, for 3 total attempts)
        model: Gemini model to use for LLM agents (default: "gemini-3-pro-preview")

    Returns:
        Configured SequentialAgent ready to run the pipeline

    Example:
        ```python
        from google.adk import Runner
        from src.agents.coordinator import create_pipeline_coordinator

        # Create coordinator
        coordinator = create_pipeline_coordinator()

        # Create runner
        runner = Runner(root_agent=coordinator)

        # Run with initial state
        initial_state = {
            "input_dir": "input/",
            "skip_sampling": False,
            "skip_schema_selection": False,
            "skip_evaluation": False
        }

        result = runner.run(session_state=initial_state)
        print(result.state.get("dataset_count"))
        ```
    """

    # Create individual agents
    discovery = DiscoveryAgent(name="DiscoveryAgent")
    sampling = SamplingAgent(name="SamplingAgent")
    schema_selection = create_schema_selection_agent(name="SchemaSelectionAgent", model=model)
    pvmap_generation = PVMAPGenerationAgent(
        name="PVMAPGenerationAgent",
        max_retries=max_retries,
        model=model
    )
    evaluation = EvaluationAgent(name="EvaluationAgent")

    # Create SequentialAgent coordinator
    coordinator = SequentialAgent(
        name=name,
        sub_agents=[
            discovery,
            sampling,
            schema_selection,
            pvmap_generation,
            evaluation
        ]
    )

    return coordinator


# Alias for backward compatibility
PipelineCoordinator = create_pipeline_coordinator

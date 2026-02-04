"""
Pipeline Coordinator for ADK pipeline.

Uses SequentialAgent to orchestrate all pipeline phases.
Optionally integrates with Data Commons MCP for enhanced StatVar discovery.

MCP Integration:
    When enable_mcp=True, the coordinator can use MCP tools for:
    - Pre-generation StatVar discovery
    - Place resolution validation
    - Schema validation

    The MCP server must be started separately (via MCPServerManager).
    Pass the mcp_url to enable MCP tools in agents that support it.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import SequentialAgent

from src.agents.discovery_agent import DiscoveryAgent
from src.agents.sampling_agent import create_sampling_agent
from src.agents.schema_selection_agent import create_schema_selection_agent
from src.agents.pvmap_generation_agent import PVMAPGenerationAgent
from src.agents.evaluation_agent import EvaluationAgent

logger = logging.getLogger(__name__)


def create_pipeline_coordinator(
    name: str = "PipelineCoordinator",
    max_retries: int = 2,
    model: str = "gemini-3-pro-preview",
    use_structured_output: bool = False,
    enable_mcp: bool = False,
    mcp_url: Optional[str] = None
) -> SequentialAgent:
    """
    Create pipeline coordinator using SequentialAgent.

    The coordinator orchestrates all pipeline phases in sequence:
    1. Discovery - Scan input directory for datasets
    2. Sampling - Create representative data samples
    3. Schema Selection - Choose appropriate schema category
    3.5. (Optional) DC Query - Pre-generation StatVar discovery via MCP
    4. PVMAP Generation - Generate and validate PVMAP with retry loop
    5. Evaluation - Compare against ground truth

    Each agent checks its own skip flags in ctx.session.state:
    - skip_sampling: bool
    - skip_schema_selection: bool
    - skip_evaluation: bool
    - mcp_enabled: bool (set automatically if enable_mcp=True)
    - mcp_url: str (set automatically if mcp_url provided)

    Args:
        name: Coordinator name (default: "PipelineCoordinator")
        max_retries: Max retries for PVMAP generation (default: 2, for 3 total attempts)
        model: Gemini model to use for LLM agents (default: "gemini-3-pro-preview")
        use_structured_output: Use JSON structured output for PVMAP generation
        enable_mcp: Enable MCP integration for StatVar discovery (default: False)
        mcp_url: MCP server URL (default: None, uses "http://localhost:3000/mcp" if enable_mcp=True)

    Returns:
        Configured SequentialAgent ready to run the pipeline

    Example:
        ```python
        from google.adk import Runner
        from src.agents.coordinator import create_pipeline_coordinator
        from src.data_commons.api.mcp_server_manager import MCPServerManager

        # Without MCP
        coordinator = create_pipeline_coordinator()

        # With MCP (requires MCPServerManager to be running)
        with MCPServerManager() as mcp:
            coordinator = create_pipeline_coordinator(
                enable_mcp=True,
                mcp_url=mcp.mcp_url
            )

            runner = Runner(root_agent=coordinator)
            initial_state = {
                "input_dir": "input/",
                "mcp_enabled": True,
                "mcp_url": mcp.mcp_url
            }
            result = runner.run(session_state=initial_state)
        ```
    """

    # Create individual agents
    discovery = DiscoveryAgent(name="DiscoveryAgent")
    sampling = create_sampling_agent(name="SamplingAgent", model=model)
    schema_selection = create_schema_selection_agent(name="SchemaSelectionAgent", model=model)

    # Build sub_agents list
    sub_agents = [discovery, sampling, schema_selection]

    # Optionally add DC Query Agent for pre-generation StatVar discovery
    if enable_mcp:
        if mcp_url is None:
            mcp_url = "http://localhost:3000/mcp"

        logger.info(f"MCP enabled, adding DCQueryAgent with URL: {mcp_url}")

        from src.agents.dc_query_agent import create_dc_query_agent
        dc_query = create_dc_query_agent(
            mcp_url=mcp_url,
            model=model,
            name="DCQueryAgent"
        )
        sub_agents.append(dc_query)

    # Add PVMAP generation and evaluation
    pvmap_generation = PVMAPGenerationAgent(
        name="PVMAPGenerationAgent",
        max_retries=max_retries,
        model=model,
        use_structured_output=use_structured_output
    )
    evaluation = EvaluationAgent(name="EvaluationAgent")

    sub_agents.extend([pvmap_generation, evaluation])

    # Create SequentialAgent coordinator
    coordinator = SequentialAgent(
        name=name,
        sub_agents=sub_agents
    )

    logger.info(f"Created coordinator with {len(sub_agents)} agents: "
               f"{[a.name for a in sub_agents]}")

    return coordinator


# Alias for backward compatibility
PipelineCoordinator = create_pipeline_coordinator

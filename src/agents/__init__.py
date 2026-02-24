"""ADK Agents for the PVMAP generation pipeline.

Main agents:
- DiscoveryAgent: Discovers datasets in input directory
- ProgrammaticSamplingAgent: Code-orchestrated data sampling (2 LLM calls)
- SchemaSelectionAgent: Selects appropriate schema category
- PVMAPRetryLoop: ADK LoopAgent-based PVMAP generation with retry loop
- ValidationAgent: Validates PVMAP and escalates on success
- FeedbackAgent: Analyzes errors for retry
- EvaluationAgent: Compares generated PVMAP against ground truth
- DCQueryAgent: Queries Data Commons via MCP (optional)
- StatVarDiscoveryAgent: Discovers StatVars via MCP before PVMAP generation

Coordinator:
- create_pipeline_coordinator: Creates SequentialAgent to orchestrate all phases

Retry Loop Architecture:
- Uses ADK LoopAgent with max_iterations for automatic retries
- Generator produces structured JSON via output_schema
- Validator converts to CSV and runs subprocess; escalates on success
- Feedback analyzes errors for next iteration
"""

from src.agents.discovery_agent import DiscoveryAgent
from src.agents.sampling_agent_v2 import ProgrammaticSamplingAgent
from src.agents.schema_selection_agent import create_schema_selection_agent
from src.agents.pvmap_generator_agent import create_pvmap_generator
from src.agents.validation_agent import ValidationAgent
from src.agents.feedback_agent import create_feedback_agent
from src.agents.quality_evaluation_agent import QualityEvaluationAgent
from src.agents.pvmap_retry_loop import (
    create_pvmap_retry_loop,
    ConditionalFeedbackAgent,
    StatePreparationAgent,
    MaxRetriesCheckAgent,
)
from src.agents.evaluation_agent import EvaluationAgent
from src.agents.coordinator import create_pipeline_coordinator, PipelineCoordinator

# StatVar Discovery Agent (requires MCP)
try:
    from src.agents.statvar_discovery_agent import StatVarDiscoveryAgent
    STATVAR_DISCOVERY_AVAILABLE = True
except ImportError:
    StatVarDiscoveryAgent = None
    STATVAR_DISCOVERY_AVAILABLE = False

# DC Query Agent (requires MCP)
try:
    from src.agents.dc_query_agent import (
        create_dc_query_agent,
        create_statvar_discovery_agent,
        create_observation_fetch_agent
    )
    DC_QUERY_AVAILABLE = True
except ImportError:
    create_dc_query_agent = None
    create_statvar_discovery_agent = None
    create_observation_fetch_agent = None
    DC_QUERY_AVAILABLE = False

__all__ = [
    # Core agents
    'DiscoveryAgent',
    'ProgrammaticSamplingAgent',
    'create_schema_selection_agent',
    'EvaluationAgent',
    # ADK LoopAgent-based architecture
    'create_pvmap_generator',
    'ValidationAgent',
    'create_feedback_agent',
    'QualityEvaluationAgent',
    'create_pvmap_retry_loop',
    'ConditionalFeedbackAgent',
    'StatePreparationAgent',
    'MaxRetriesCheckAgent',
    # Coordinator
    'create_pipeline_coordinator',
    'PipelineCoordinator',
    # Optional MCP-based agents
    'StatVarDiscoveryAgent',
    'STATVAR_DISCOVERY_AVAILABLE',
    'create_dc_query_agent',
    'create_statvar_discovery_agent',
    'create_observation_fetch_agent',
    'DC_QUERY_AVAILABLE'
]

"""ADK Agents for the PVMAP generation pipeline.

Main agents:
- DiscoveryAgent: Discovers datasets in input directory
- SamplingAgent: Agentic data sampling with LLM-driven decisions
- SchemaSelectionAgent: Selects appropriate schema category
- PVMAPGenerationAgent: Generates PVMAP with retry loop and validation (legacy)
- PVMAPRetryLoop: ADK LoopAgent-based PVMAP generation with structured output (new)
- ValidationAgent: Validates PVMAP and escalates on success
- FeedbackAgent: Analyzes errors for retry
- EvaluationAgent: Compares generated PVMAP against ground truth
- DCQueryAgent: Queries Data Commons via MCP (optional)
- StatVarDiscoveryAgent: Discovers StatVars via MCP before PVMAP generation

Coordinator:
- create_pipeline_coordinator: Creates SequentialAgent to orchestrate all phases

Retry Loop Architecture (when using --structured-output):
- Uses ADK LoopAgent with max_iterations for automatic retries
- Generator produces structured JSON via output_schema
- Validator converts to CSV and runs subprocess; escalates on success
- Feedback analyzes errors for next iteration

Sampling Agent:
The SamplingAgent uses an LLM to make intelligent sampling decisions based on
data evidence. It has 5 tools: preview_data, analyze_columns, sample_rows,
check_coverage, and generate_context. Use create_sampling_agent() for new code.
"""

from src.agents.discovery_agent import DiscoveryAgent
from src.agents.sampling_agent import create_sampling_agent, SamplingAgent
from src.agents.schema_selection_agent import create_schema_selection_agent
from src.agents.pvmap_generation_agent import PVMAPGenerationAgent
from src.agents.pvmap_generator_agent import create_pvmap_generator
from src.agents.validation_agent import ValidationAgent
from src.agents.feedback_agent import create_feedback_agent
from src.agents.quality_evaluation_agent import QualityEvaluationAgent
# Deprecated: quality_feedback_agent is superseded by unified ConditionalFeedbackAgent
# Kept for backward compatibility with simple retry loop
from src.agents.quality_feedback_agent import (
    create_quality_feedback_agent,
    ConditionalQualityFeedbackAgent,
)
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
    'create_sampling_agent',
    'SamplingAgent',
    'create_schema_selection_agent',
    'PVMAPGenerationAgent',  # Legacy BaseAgent-based
    'EvaluationAgent',
    # New ADK LoopAgent-based architecture
    'create_pvmap_generator',
    'ValidationAgent',
    'create_feedback_agent',
    'QualityEvaluationAgent',
    'create_quality_feedback_agent',
    'ConditionalQualityFeedbackAgent',
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

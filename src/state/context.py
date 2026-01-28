"""
⚠️ DEPRECATED: PipelineContext for ADK migration.

This module is DEPRECATED in favor of Google ADK's native state management.

**Migration Path:**
- Instead of PipelineContext, use `ctx.session.state` (dict) directly in agents
- Access state: `ctx.session.state.get("key")`
- Update state: `ctx.session.state["key"] = value`

**Why Deprecated:**
Google ADK provides InvocationContext with session.state dictionary that handles:
- State persistence across agent invocations
- State sharing between agents in a session
- Proper serialization/deserialization

This PipelineContext class duplicates ADK functionality and is kept only for:
1. Reference documentation of expected state keys
2. Backward compatibility with old code during migration

**See STATE_SCHEMA below for complete state structure documentation.**

---

Original docstring:
Provides state management for the multi-agent pipeline using a hybrid approach:
- ADK Context for state flow between agents
- Typed DatasetInfo object for file path management
"""

from typing import Any, Dict, Optional, List
from pathlib import Path
from datetime import datetime


# ============================================================================
# STATE SCHEMA REFERENCE
# ============================================================================
# This documents the expected keys in ctx.session.state for ADK agents.
# Use this as a reference when reading/writing state in agents.
# ============================================================================

STATE_SCHEMA = {
    # -------------------------------------------------------------------------
    # Discovery Phase (DiscoveryAgent)
    # -------------------------------------------------------------------------
    "input_dir": "str - Path to input directory containing datasets",
    "datasets": "List[DatasetInfo] - Discovered dataset objects",
    "dataset_count": "int - Number of datasets found",
    "current_dataset": "DatasetInfo - Current dataset being processed",

    # -------------------------------------------------------------------------
    # Sampling Phase (SamplingAgent)
    # -------------------------------------------------------------------------
    "sampled_data_files": "List[Path] - Individual sampled data files",
    "combined_sampled_data": "Path - Combined sampled data file path",
    "skip_sampling": "bool - Whether to skip sampling phase",

    # -------------------------------------------------------------------------
    # Schema Selection Phase (SchemaSelectionAgent)
    # -------------------------------------------------------------------------
    "schema_category": "str - Selected schema category name",
    "schema_examples_file": "Path - Schema examples .txt file",
    "schema_mcf_file": "Path - Schema MCF .mcf file",
    "available_categories": "List[str] - Available schema categories",

    # -------------------------------------------------------------------------
    # PVMAP Generation Phase (PVMAPGenerationAgent)
    # -------------------------------------------------------------------------
    "pvmap_prompt": "str - Populated prompt for LLM generation",
    "pvmap_path": "Path - Generated PVMAP CSV file path",
    "pvmap_content": "str - Generated PVMAP CSV content",
    "generation_notes": "str - Notes from generation process",
    "attempt_number": "int - Current generation attempt (for retry loop)",
    "max_retries": "int - Maximum retry attempts (default: 3)",

    # -------------------------------------------------------------------------
    # Validation Phase (ValidationAgent)
    # -------------------------------------------------------------------------
    "validation_passed": "bool - Whether validation succeeded",
    "validation_error_logs": "str - Sampled validation error logs",
    "processed_output_file": "Path - statvar_processor output file",
    "validation_output_path": "Path - Directory for validation outputs",

    # -------------------------------------------------------------------------
    # Evaluation Phase (EvaluationAgent)
    # -------------------------------------------------------------------------
    "eval_metrics": "Dict[str, Any] - Evaluation metrics (precision, recall, etc.)",
    "best_ground_truth_pvmap": "str - Path to best matching ground truth",
    "ground_truth_pvmaps": "List[Path] - All available ground truth files",
    "skip_evaluation": "bool - Whether to skip evaluation phase",

    # -------------------------------------------------------------------------
    # Error/Retry State
    # -------------------------------------------------------------------------
    "error": "Optional[str] - Current error message if any",
    "error_feedback": "Optional[str] - Feedback for retry attempts",
    "retry_count": "int - Number of retry attempts made",

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------
    "model": "str - LLM model name (e.g., 'gemini-2.5-flash')",
    "output_dir": "Path - Base output directory for artifacts",
}
# ============================================================================


class PipelineContext:
    """
    Enhanced context for pipeline state management.

    State Keys:
        # Discovery Phase
        dataset_info: DatasetInfo - Typed object for dataset details
        metadata_files: List[Path] - Discovered metadata files
        input_data_files: List[Path] - Discovered input data files

        # Sampling Phase
        sampled_data: List[Path] - Sampled data file paths
        combined_sampled_data: Path - Combined sampled data file

        # Schema Selection Phase
        schema_category: str - Selected schema category
        schema_files: Dict[str, Path] - Selected schema files
        schema_examples_file: Path - Schema examples file path
        schema_mcf_file: Path - Schema MCF file path

        # PVMAP Generation Phase
        pvmap_prompt: str - Populated prompt for generation
        pvmap_path: Path - Generated PVMAP file location
        pvmap_content: str - Generated PVMAP CSV content
        generation_notes: str - Generation notes
        attempt_number: int - Current retry attempt number

        # Validation Phase
        validation_passed: bool - Validation result
        validation_error_logs: str - Sampled error logs
        processed_output_file: Path - Validation output file

        # Evaluation Phase
        eval_metrics: Dict - Evaluation metrics
        best_ground_truth_pvmap: str - Best matching ground truth file

        # Error/Retry State
        error_feedback: Optional[str] - Current retry error feedback
        retry_count: int - Number of retry attempts

        # Configuration
        cli_config: Dict[str, Any] - CLI arguments configuration
    """

    def __init__(self, dataset_info: Any, cli_config: Dict[str, Any]):
        """
        Initialize pipeline context.

        Args:
            dataset_info: DatasetInfo object or dict with dataset details
            cli_config: CLI configuration dictionary
        """
        self._state = {
            "dataset_info": dataset_info,
            "cli_config": cli_config,
            "phase_outputs": {},
            "errors": [],
            "retry_count": 0,
            "attempt_number": 0,
            "created_at": datetime.now().isoformat()
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get state value by key.

        Args:
            key: State key
            default: Default value if key not found

        Returns:
            State value or default
        """
        return self._state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set state value.

        Args:
            key: State key
            value: Value to store
        """
        self._state[key] = value

    def get_phase_output(self, phase: str) -> Any:
        """
        Get output from a specific phase.

        Args:
            phase: Phase name (e.g., "sampling", "schema_selection")

        Returns:
            Phase output or None
        """
        return self._state["phase_outputs"].get(phase)

    def set_phase_output(self, phase: str, output: Any) -> None:
        """
        Store phase output.

        Args:
            phase: Phase name
            output: Output value to store
        """
        self._state["phase_outputs"][phase] = output

    def add_error(self, phase: str, error: str) -> None:
        """
        Track error for debugging.

        Args:
            phase: Phase where error occurred
            error: Error message
        """
        self._state["errors"].append({
            "phase": phase,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })

    def get_errors(self) -> List[Dict[str, str]]:
        """
        Get all tracked errors.

        Returns:
            List of error dictionaries
        """
        return self._state["errors"]

    def increment_retry(self) -> int:
        """
        Increment and return retry count.

        Returns:
            Updated retry count
        """
        self._state["retry_count"] += 1
        return self._state["retry_count"]

    def increment_attempt(self) -> int:
        """
        Increment and return attempt number.

        Returns:
            Updated attempt number
        """
        self._state["attempt_number"] += 1
        return self._state["attempt_number"]

    def reset_retry(self) -> None:
        """Reset retry counter."""
        self._state["retry_count"] = 0

    def to_dict(self) -> Dict[str, Any]:
        """
        Export state for serialization.

        Returns:
            Complete state dictionary
        """
        return self._state.copy()

    def __repr__(self) -> str:
        """String representation of context."""
        dataset_name = "unknown"
        if hasattr(self._state.get("dataset_info"), "name"):
            dataset_name = self._state["dataset_info"].name
        elif isinstance(self._state.get("dataset_info"), dict):
            dataset_name = self._state["dataset_info"].get("name", "unknown")

        return (
            f"PipelineContext(dataset={dataset_name}, "
            f"retry_count={self._state.get('retry_count', 0)}, "
            f"errors={len(self._state.get('errors', []))})"
        )

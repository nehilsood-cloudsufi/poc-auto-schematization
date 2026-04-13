"""API server configuration constants."""
import os
from pathlib import Path

# Server settings
API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8000"))

# Output directory for UI runs (matches old Streamlit config).
# Resolve to absolute path at import time so all derived paths are
# CWD-independent (pipeline threads, subprocesses, etc.)
UI_OUTPUT_DIR = Path(os.environ.get("UI_OUTPUT_DIR", "ui_output")).resolve()

# Default pipeline settings
DEFAULT_MODEL = "gemini-3.1-pro-preview"
DEFAULT_MAX_RETRIES = 1
MIN_PIPELINE_ATTEMPTS = 2

# MCP settings
MCP_DEFAULT_PORT = 3000

# Cloud Run detection
CLOUD_RUN = os.environ.get("K_SERVICE", "") != ""
GCS_BUCKET = os.environ.get("GCS_BUCKET", "")

# Supported upload types
SUPPORTED_EXTENSIONS = {".csv"}

# Pipeline phases for progress display
PHASE_LABELS = {
    "StatePrep": "Preparing state",
    "Sampling": "Sampling data",
    "SchemaSelectionAgent": "Selecting schema",
    "SchemaOrgEnrichment": "Enriching with Schema.org",
    "MappingPlan": "Generating mapping plan",
    "PlanGate": "Plan approval",
    "StatVarDiscovery": "Discovering StatVars (MCP)",
    "Generator": "Generating PVMAP",
    "MetadataGenerator": "Generating metadata config",
    "Validator": "Validating PVMAP",
    "MCPSpotCheck": "Spot-checking mappings (MCP)",
    "MCPErrorResolver": "Resolving errors (MCP)",
    "QualityEvaluator": "Evaluating quality",
    "UnifiedFeedback": "Generating feedback",
    "MaxRetriesCheck": "Checking retry status",
    "Evaluation": "Running evaluation",
}

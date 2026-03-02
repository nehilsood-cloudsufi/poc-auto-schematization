"""UI configuration constants."""
import json
import logging
import os
from pathlib import Path

# Default model for pipeline
DEFAULT_MODEL = "gemini-3.1-pro-preview"

# MCP settings
MCP_DEFAULT_PORT = 3000

# Prompt settings
DEFAULT_PROMPT_VERSION = "v2"

# Pipeline settings
MIN_PIPELINE_ATTEMPTS = 2  # Always run at least 2 attempts in UI mode
DEFAULT_MAX_RETRIES = 1    # Default max retries (2 total attempts: initial + 1 retry)

# Output directory for UI runs (env-var driven for Cloud Run)
UI_OUTPUT_DIR = Path(os.environ.get("UI_OUTPUT_DIR", "ui_output"))

# Cloud Run detection
CLOUD_RUN = os.environ.get("K_SERVICE", "") != ""

# GCS bucket for Cloud Run output (derived from project)
GCS_BUCKET = os.environ.get("GCS_BUCKET", "")
GCS_PROJECT = os.environ.get("K_SERVICE", "")  # non-empty on Cloud Run

# Supported upload types
SUPPORTED_UPLOAD_TYPES = ["csv"]

# Logging format (matches backend convention)
_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class CloudRunFormatter(logging.Formatter):
    """JSON log formatter for Google Cloud Logging."""

    def format(self, record):
        entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        for key in ("run_id", "dataset_name", "action", "user_event"):
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        return json.dumps(entry)


def setup_ui_logging(run_dir: Path) -> logging.Logger:
    """Configure the ``src.ui`` logger hierarchy with file + console handlers.

    Idempotent — safe to call multiple times; existing handlers are skipped.

    Args:
        run_dir: The run directory; log file is written to ``{run_dir}/logs/ui.log``.

    Returns:
        The configured ``src.ui`` parent logger.
    """
    ui_logger = logging.getLogger("src.ui")

    # Avoid adding duplicate handlers on re-runs
    if ui_logger.handlers:
        return ui_logger

    ui_logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(_LOG_FORMAT)

    # File handler — DEBUG level
    log_dir = run_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_dir / "ui.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    ui_logger.addHandler(fh)

    # Console handler — INFO level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(CloudRunFormatter() if CLOUD_RUN else formatter)
    ui_logger.addHandler(ch)

    return ui_logger

# Pipeline phases for progress display
PHASE_LABELS = {
    "StatePrep": "Preparing state...",
    "Sampling": "Sampling data...",
    "SchemaSelection": "Selecting schema...",
    "SchemaSelectionAgent": "Selecting schema...",
    "StatVarDiscovery": "Discovering StatVars (MCP)...",
    "Generator": "Generating PVMAP...",
    "MetadataGenerator": "Generating metadata config...",
    "Validator": "Validating PVMAP...",
    "MCPSpotCheck": "Spot-checking mappings (MCP)...",
    "MCPErrorResolver": "Resolving errors (MCP)...",
    "QualityEvaluator": "Evaluating quality...",
    "UnifiedFeedback": "Generating feedback...",
    "MaxRetriesCheck": "Checking retry status...",
    "Evaluation": "Running evaluation...",
}

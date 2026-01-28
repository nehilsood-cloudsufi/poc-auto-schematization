"""Logging configuration for ADK pipeline."""
from pathlib import Path
from google.adk.plugins import LoggingPlugin, DebugLoggingPlugin
from typing import Optional, List
from google.adk.plugins import BasePlugin
import logging


def setup_adk_logging(
    output_dir: Path,
    session_id: str,
    console_logging: bool = True,
    debug_logging: bool = True,
    custom_plugins: Optional[List[BasePlugin]] = None
) -> List[BasePlugin]:
    """
    Setup ADK logging plugins.

    Args:
        output_dir: Base output directory (e.g., src/output/)
        session_id: Session identifier for log files
        console_logging: Enable console logging plugin
        debug_logging: Enable debug YAML logging
        custom_plugins: Additional plugins to include

    Returns:
        List of configured plugins
    """
    plugins = []

    # Layer 1: Console logging for real-time visibility
    if console_logging:
        console_plugin = LoggingPlugin(name="console_logger")
        plugins.append(console_plugin)

    # Layer 1: Debug logging for detailed analysis
    if debug_logging:
        logs_dir = output_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        debug_file = logs_dir / f"adk_trace_{session_id}.yaml"
        debug_plugin = DebugLoggingPlugin(
            output_path=str(debug_file),
            include_session_state=True,
            include_system_instruction=True
        )
        plugins.append(debug_plugin)

    # Layer 2: Custom plugins
    if custom_plugins:
        plugins.extend(custom_plugins)

    return plugins


def setup_python_logging(
    output_dir: Path,
    session_id: str,
    level: int = logging.DEBUG
) -> logging.Logger:
    """
    Setup traditional Python logging (for compatibility).

    Args:
        output_dir: Base output directory
        session_id: Session identifier
        level: Logging level

    Returns:
        Configured logger
    """
    logs_dir = output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"adk_pipeline_{session_id}")
    logger.setLevel(level)

    # File handler
    fh = logging.FileHandler(logs_dir / f"pipeline_{session_id}.log")
    fh.setLevel(level)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger

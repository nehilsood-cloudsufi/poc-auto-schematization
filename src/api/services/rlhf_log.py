"""Per-run RLHF interaction logger.

Append-only JSONL log capturing every user input for RLHF training data.
Written per-run to {run_dir}/rlhf_interactions.jsonl.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def log_interaction(
    run_dir: Path | str,
    user_email: str,
    action: str,
    data: dict | None = None,
) -> None:
    """Append an RLHF interaction entry to the run's log."""
    run_dir = Path(run_dir)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "user": user_email,
        "action": action,
        **(data or {}),
    }
    log_path = run_dir / "rlhf_interactions.jsonl"
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        logger.debug("Failed to write RLHF log to %s", log_path, exc_info=True)

"""Per-user activity logger.

Tracks user events across all runs to {output_dir}/users/{email}/activity.jsonl.
Separate from RLHF log — this is for user activity analytics, not training data.
"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _sanitize_email(email: str) -> str:
    """Sanitize email for use as a directory name."""
    return re.sub(r'[^\w@.\-]', '_', email)


def log_activity(
    base_dir: Path | str,
    user_email: str,
    event: str,
    details: dict | None = None,
) -> None:
    """Append an activity event to the user's log."""
    base_dir = Path(base_dir)
    user_dir = base_dir / "users" / _sanitize_email(user_email)
    try:
        user_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "user": user_email,
            **(details or {}),
        }
        with open(user_dir / "activity.jsonl", "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:
        logger.debug("Failed to write activity log for %s", user_email, exc_info=True)

"""Feedback persistence for pipeline runs."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


def save_feedback(
    entry: Dict,
    output_dir: Path,
) -> Path:
    """Save feedback entry as JSON to the output directory's feedback folder."""
    feedback_dir = output_dir / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)

    # Auto-number feedback files
    existing = sorted(feedback_dir.glob("feedback_*.json"))
    next_num = len(existing) + 1

    entry.setdefault("timestamp", datetime.now().isoformat())
    entry.setdefault("feedback_round", next_num)

    feedback_path = feedback_dir / f"feedback_{next_num:03d}.json"
    feedback_path.write_text(json.dumps(entry, indent=2, default=str))
    logger.info("Saved feedback round %d to %s", next_num, feedback_path)
    return feedback_path


def load_feedback_history(output_dir: Path) -> List[Dict]:
    """Load all feedback JSONs for a run, sorted by round."""
    feedback_dir = output_dir / "feedback"
    if not feedback_dir.exists():
        return []

    entries = []
    for f in sorted(feedback_dir.glob("feedback_*.json")):
        try:
            entries.append(json.loads(f.read_text()))
        except Exception:
            logger.warning("Failed to parse feedback file: %s", f)
    logger.debug("Loaded %d feedback entries from %s", len(entries), feedback_dir)
    return entries

"""File management for API runs with output versioning (framework-agnostic)."""
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from src.api.config import UI_OUTPUT_DIR

logger = logging.getLogger(__name__)


def create_run_directory(run_id: str, base_dir: Optional[Path] = None) -> Path:
    """Create directory structure for a pipeline run."""
    base = base_dir if base_dir is not None else UI_OUTPUT_DIR
    run_dir = base / run_id
    (run_dir / "input").mkdir(parents=True, exist_ok=True)
    (run_dir / "output").mkdir(parents=True, exist_ok=True)
    logger.info("Created run directory: %s", run_dir)
    return run_dir


def save_uploaded_bytes(data: bytes, target_dir: Path, filename: str) -> Path:
    """Save raw bytes to disk (framework-agnostic replacement for save_uploaded_file)."""
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    target_path.write_bytes(data)
    logger.info("Saved uploaded file: %s (%d bytes)", target_path, len(data))
    return target_path


def get_output_files(output_dir: Path) -> Dict[str, Path]:
    """Map known output filenames to paths (only files that exist)."""
    known_files = [
        "generated_pvmap.csv",
        "output_metadata.csv",
        "processed.csv",
        "processed.mcf",
        "processed.tmcf",
        "processed_stat_vars.mcf",
        "generation_notes.md",
        "processed_counters.txt",
        "statvar_processor_raw_logs.txt",
    ]
    result = {}
    for fname in known_files:
        fpath = output_dir / fname
        if fpath.exists():
            result[fname] = fpath
    logger.debug("get_output_files(%s): found %s", output_dir, list(result.keys()))
    return result


def snapshot_version(output_dir: Path, version: int) -> Path:
    """Copy current output files to a versioned snapshot directory."""
    version_dir = output_dir / f"v{version}"
    version_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for item in output_dir.iterdir():
        if item.is_file():
            shutil.copy2(item, version_dir / item.name)
            copied += 1
        elif item.is_dir() and item.name == "generated_response":
            shutil.copytree(item, version_dir / item.name, dirs_exist_ok=True)
            copied += 1

    logger.info("Snapshot v%d: copied %d items to %s", version, copied, version_dir)
    return version_dir


def save_run_manifest(
    output_dir: Path,
    version: int,
    config: dict,
    result: dict,
) -> Path:
    """Write run_manifest.json for a version snapshot."""
    version_dir = output_dir / f"v{version}"
    version_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": config.get("run_id", ""),
        "version": version,
        "timestamp": datetime.now().isoformat(),
        "dataset_name": config.get("dataset_name", ""),
        "model": config.get("model", ""),
        "input_file": config.get("input_file", ""),
        "metadata_file": config.get("metadata_file", ""),
        "mcp_enabled": config.get("mcp_enabled", False),
        "attempts": result.get("retry_count", 0) + 1,
        "exit_reason": result.get("exit_reason", ""),
        "heuristic_score": result.get("quality_metrics", {}).get("heuristic_score", 0)
        if isinstance(result.get("quality_metrics"), dict)
        else 0,
        "validation_passed": result.get("validation_passed", False),
        "human_feedback_text": config.get("human_feedback", ""),
        "used_edited_pvmap": config.get("used_edited_pvmap", False),
        "skip_sampling": config.get("skip_sampling", False),
        "use_schema_examples": config.get("use_schema_examples", True),
    }

    manifest_path = version_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    logger.info(
        "Saved run manifest v%d: dataset=%s, attempts=%s, validation=%s",
        version, manifest["dataset_name"], manifest["attempts"], manifest["validation_passed"],
    )
    return manifest_path


def save_edited_files(
    output_dir: Path,
    version: int,
    edited_pvmap_df: Optional[pd.DataFrame] = None,
    edited_metadata_df: Optional[pd.DataFrame] = None,
) -> Path:
    """Save user-edited files to the version's feedback directory."""
    feedback_dir = output_dir / f"v{version}" / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)

    if edited_pvmap_df is not None:
        edited_pvmap_df.to_csv(feedback_dir / "edited_pvmap.csv", index=False)
        logger.info("Saved edited PVMAP to %s", feedback_dir / "edited_pvmap.csv")

    if edited_metadata_df is not None:
        edited_metadata_df.to_csv(feedback_dir / "edited_metadata.csv", index=False)
        logger.info("Saved edited metadata to %s", feedback_dir / "edited_metadata.csv")

    return feedback_dir


def get_latest_version(output_dir: Path) -> int:
    """Scan v{N} directories and return highest version number."""
    max_v = 0
    if output_dir.exists():
        for item in output_dir.iterdir():
            if item.is_dir() and item.name.startswith("v"):
                try:
                    v = int(item.name[1:])
                    max_v = max(max_v, v)
                except ValueError:
                    pass
    logger.debug("get_latest_version(%s) = %d", output_dir, max_v)
    return max_v


def discover_historical_runs(base_dir: Optional[Path] = None) -> list:
    """Scan output directory for past runs and return summary metadata.

    Args:
        base_dir: Override the default UI_OUTPUT_DIR (useful for testing).

    Returns a list of dicts sorted by timestamp descending (most recent first):
        {run_id, dataset_name, timestamp, model, attempts, has_pvmap, run_dir, result}
    """
    output_root = base_dir if base_dir is not None else UI_OUTPUT_DIR
    if not output_root.exists():
        return []

    runs = []
    for run_dir in output_root.iterdir():
        if not run_dir.is_dir():
            continue

        run_id = run_dir.name
        output_dir = run_dir / "output"
        if not output_dir.exists():
            continue

        # Find the dataset subdirectory (skip "logs")
        dataset_name = None
        dataset_dir = None
        for item in output_dir.iterdir():
            if item.is_dir() and item.name != "logs":
                dataset_name = item.name
                dataset_dir = item
                break

        if not dataset_name or not dataset_dir:
            continue

        # Read attempt JSONs to extract metadata
        response_dir = dataset_dir / "generated_response"
        attempts = []
        if response_dir.exists():
            for attempt_file in sorted(response_dir.glob("attempt_*.json")):
                try:
                    data = json.loads(attempt_file.read_text())
                    attempts.append(data)
                except (json.JSONDecodeError, OSError):
                    pass

        model = attempts[0].get("model", "") if attempts else ""
        timestamp = attempts[0].get("start_time", "") if attempts else ""
        if not timestamp:
            timestamp = datetime.fromtimestamp(run_dir.stat().st_mtime).isoformat()

        last_attempt = attempts[-1] if attempts else {}
        validation_passed = last_attempt.get("validation_success", False)
        has_pvmap = (dataset_dir / "generated_pvmap.csv").exists()

        result = {
            "validation_passed": validation_passed,
            "exit_reason": "max_retries" if len(attempts) > 1 else "complete",
            "retry_count": max(0, len(attempts) - 1),
        }

        runs.append({
            "run_id": run_id,
            "dataset_name": dataset_name,
            "timestamp": timestamp,
            "model": model,
            "attempts": len(attempts),
            "has_pvmap": has_pvmap,
            "run_dir": str(run_dir),
            "result": result,
        })

    runs.sort(key=lambda r: r["timestamp"], reverse=True)
    return runs


def cleanup_old_runs(max_age_hours: int = 24, base_dir: Optional[Path] = None) -> None:
    """Remove stale run directories older than max_age_hours."""
    output_root = base_dir if base_dir is not None else UI_OUTPUT_DIR
    if not output_root.exists():
        return
    cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
    removed = 0
    for run_dir in output_root.iterdir():
        if run_dir.is_dir() and run_dir.stat().st_mtime < cutoff:
            shutil.rmtree(run_dir, ignore_errors=True)
            removed += 1
    if removed:
        logger.info("cleanup_old_runs: removed %d stale directories", removed)

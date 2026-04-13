"""Programmatic enforcement of human feedback constraints on PVMAPs.

This module provides pure functions that act as a "hard guarantee" layer:
even if the LLM ignores human instructions, these functions restore pinned
rows and explicit mappings before the PVMAP is committed.

Enforced types:
    - PIN_ROW: replaces (or appends) the entire row identified by the target key
    - SET_MAPPING: replaces (or appends) the property mapping for the target column

Not enforced (guidance-only, handled by LLM):
    - APPLY_RULE
    - FREE_TEXT
    - AUTO  (never structural constraints)

Usage:
    from src.agents.feedback_enforcement import apply_enforcement
    enforced_pvmap, changes = apply_enforcement(pvmap_csv, ledger)
"""
from __future__ import annotations

import logging

from src.api.models.feedback import FeedbackLedger, FeedbackType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _split_lines(pvmap_csv: str) -> list[str]:
    """Return non-empty lines from a PVMAP CSV string."""
    return [line for line in pvmap_csv.splitlines() if line.strip()]


def _key_of(row: str) -> str:
    """Return the first column value (the key) from a CSV row."""
    import csv, io
    parsed = next(csv.reader(io.StringIO(row)), [])
    return parsed[0] if parsed else ""


def _join_lines(lines: list[str]) -> str:
    """Re-join lines with newlines, preserving a final newline if the
    original had one."""
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def enforce_pinned_row(
    pvmap_csv: str, target_key: str, pinned_content: str
) -> tuple[str, bool]:
    """Enforce a pinned row constraint by key match.

    Matches by first column value (the key column), NOT by positional index.

    Args:
        pvmap_csv: Current PVMAP CSV string.
        target_key: The key (first column) of the row to pin.
        pinned_content: The full desired row content (e.g. "Year,observationDate,{Data}").

    Returns:
        (new_pvmap, changed) where changed is True if the PVMAP was modified.
    """
    lines = _split_lines(pvmap_csv)

    # Check if a row with this key already exists
    key_index: int | None = None
    for i, line in enumerate(lines):
        if _key_of(line) == target_key:
            key_index = i
            break

    if key_index is None:
        # Key not found — append the pinned row
        logger.warning(
            "enforce_pinned_row: key %r not found in PVMAP — appending as new row",
            target_key,
        )
        lines.append(pinned_content)
        return _join_lines(lines), True

    if lines[key_index] == pinned_content:
        # Already correct — no change
        return pvmap_csv, False

    # Replace the existing row
    lines[key_index] = pinned_content
    return _join_lines(lines), True


def enforce_mapping(
    pvmap_csv: str, target_column: str, mapping_content: str
) -> tuple[str, bool]:
    """Enforce a specific property mapping for a column.

    Finds the row where the first column equals target_column and replaces
    the rest of that row with mapping_content.  If no such row exists, a
    new row is created.

    The resulting row format is: "{target_column},{mapping_content}"

    Args:
        pvmap_csv: Current PVMAP CSV string.
        target_column: The column name (first CSV column) to target.
        mapping_content: Everything after the key in the desired row
            (e.g. "observationDate,{Data},unit,Year").

    Returns:
        (new_pvmap, changed) where changed is True if the PVMAP was modified.
    """
    desired_row = f"{target_column},{mapping_content}"
    lines = _split_lines(pvmap_csv)

    key_index: int | None = None
    for i, line in enumerate(lines):
        if _key_of(line) == target_column:
            key_index = i
            break

    if key_index is None:
        # Column not mapped — append new row
        lines.append(desired_row)
        return _join_lines(lines), True

    if lines[key_index] == desired_row:
        # Already correct — no change
        return pvmap_csv, False

    # Replace the existing mapping
    lines[key_index] = desired_row
    return _join_lines(lines), True


def apply_enforcement(
    pvmap_csv: str, ledger: FeedbackLedger
) -> tuple[str, list[str]]:
    """Apply all active human structural constraints from the ledger.

    Iterates over ledger.active_human_entries() and enforces:
    - PIN_ROW entries (with a non-None target): calls enforce_pinned_row
    - SET_MAPPING entries (with a non-None target): calls enforce_mapping

    APPLY_RULE and FREE_TEXT entries are intentionally skipped — they are
    guidance for the LLM, not structural constraints.

    Args:
        pvmap_csv: The PVMAP CSV string to enforce constraints on.
        ledger: FeedbackLedger containing all feedback entries.

    Returns:
        (enforced_pvmap, changes) where changes is a list of human-readable
        descriptions of each modification made.
    """
    current_pvmap = pvmap_csv
    changes: list[str] = []

    for entry in ledger.active_human_entries():
        if entry.type == FeedbackType.PIN_ROW:
            if entry.target is None:
                logger.debug(
                    "apply_enforcement: skipping PIN_ROW entry %r — no target set",
                    entry.id,
                )
                continue
            current_pvmap, changed = enforce_pinned_row(
                current_pvmap, entry.target, entry.content
            )
            if changed:
                changes.append(
                    f"PIN_ROW enforced for key '{entry.target}': {entry.content!r}"
                )

        elif entry.type == FeedbackType.SET_MAPPING:
            if entry.target is None:
                logger.debug(
                    "apply_enforcement: skipping SET_MAPPING entry %r — no target set",
                    entry.id,
                )
                continue
            current_pvmap, changed = enforce_mapping(
                current_pvmap, entry.target, entry.content
            )
            if changed:
                changes.append(
                    f"SET_MAPPING enforced for column '{entry.target}': {entry.content!r}"
                )

        # APPLY_RULE and FREE_TEXT are guidance-only — skip silently

    return current_pvmap, changes


__all__ = [
    "enforce_pinned_row",
    "enforce_mapping",
    "apply_enforcement",
]

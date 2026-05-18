"""Pydantic data models for the structured feedback ledger."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import ClassVar, Literal, Optional

from pydantic import BaseModel, Field


class FeedbackType(str, Enum):
    PIN_ROW = "pin_row"
    SET_MAPPING = "set_mapping"
    APPLY_RULE = "apply_rule"
    FREE_TEXT = "free_text"
    AUTO = "auto"


def _short_uuid() -> str:
    return uuid.uuid4().hex[:8]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class FeedbackEntry(BaseModel):
    """A single structured feedback entry."""

    id: str = Field(default_factory=_short_uuid)
    type: FeedbackType
    round: int
    source: Literal["human", "auto"]
    content: str
    target: Optional[str] = None
    retracted: bool = False
    superseded: bool = False
    timestamp: datetime = Field(default_factory=_now_utc)


class FeedbackEntryInput(BaseModel):
    """Input shape for creating a new feedback entry (no id/timestamp/state fields)."""

    type: FeedbackType
    content: str
    target: Optional[str] = None

    # Maps old free-text category strings to FeedbackType values.
    _LEGACY_CATEGORY_MAP: ClassVar[dict[str, FeedbackType]] = {
        "Column mapping": FeedbackType.SET_MAPPING,
        "Property names": FeedbackType.SET_MAPPING,
        "Value formatting": FeedbackType.APPLY_RULE,
        "Missing mappings": FeedbackType.SET_MAPPING,
        "Incorrect mappings": FeedbackType.SET_MAPPING,
        "Structural issue": FeedbackType.APPLY_RULE,
        "Other": FeedbackType.FREE_TEXT,
    }

    @classmethod
    def from_legacy(
        cls, category: str, content: str, target: Optional[str] = None
    ) -> FeedbackEntryInput:
        """Map an old category string to a typed FeedbackEntryInput."""
        feedback_type = cls._LEGACY_CATEGORY_MAP.get(category, FeedbackType.FREE_TEXT)
        return cls(type=feedback_type, content=content, target=target)


class FeedbackLedger(BaseModel):
    """Ordered log of all feedback entries for a pipeline run."""

    entries: list[FeedbackEntry] = Field(default_factory=list)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def active_human_entries(self) -> list[FeedbackEntry]:
        """Non-retracted, non-superseded human entries."""
        return [
            e
            for e in self.entries
            if e.source == "human" and not e.retracted and not e.superseded
        ]

    def active_auto_entries(self) -> list[FeedbackEntry]:
        """Non-retracted auto entries.

        Superseded auto entries are included here — conflict filtering is
        the responsibility of FeedbackMerger (Task 2).
        """
        return [e for e in self.entries if e.source == "auto" and not e.retracted]

    def has_human_entries(self) -> bool:
        return any(e.source == "human" for e in self.entries)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def retract(self, entry_id: str) -> bool:
        """Mark the entry with *entry_id* as retracted.

        Returns True if found and retracted, False if not found.
        """
        for entry in self.entries:
            if entry.id == entry_id:
                entry.retracted = True
                return True
        return False

    def add_entry(self, entry: FeedbackEntry) -> None:
        """Append *entry*, superseding older same-source entries with the same target.

        Only entries with a non-None target participate in superseding.
        Cross-source superseding (human over auto or vice versa) does not occur.
        """
        if entry.target is not None:
            for existing in self.entries:
                if (
                    existing.source == entry.source
                    and existing.target == entry.target
                    and not existing.superseded
                ):
                    existing.superseded = True

        self.entries.append(entry)

    def clear_auto_entries(self) -> None:
        """Remove all auto entries from the ledger."""
        self.entries = [e for e in self.entries if e.source != "auto"]

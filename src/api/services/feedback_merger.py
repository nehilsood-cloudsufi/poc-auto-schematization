"""FeedbackMerger: renders a FeedbackLedger into prompt-ready text."""
from __future__ import annotations

from src.api.models.feedback import FeedbackEntry, FeedbackLedger, FeedbackType


class FeedbackMerger:
    """Stateless helper that converts a FeedbackLedger into strings for LLM prompts."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def merge(ledger: FeedbackLedger) -> str:
        """Return a single combined prompt string (human + auto, conflict-filtered).

        Suitable for backward-compatible use with the ``error_feedback`` state key.
        """
        human_text, auto_text = FeedbackMerger.render_separate(ledger)
        parts = [p for p in (human_text, auto_text) if p]
        return "\n\n".join(parts)

    @staticmethod
    def render_separate(ledger: FeedbackLedger) -> tuple[str, str]:
        """Return (human_text, auto_text) with conflict filtering applied.

        Auto entries whose ``target`` matches any active human entry's ``target``
        are suppressed — human instructions take precedence.
        """
        human_entries = ledger.active_human_entries()
        auto_entries = ledger.active_auto_entries()

        # Collect targets covered by active human entries for conflict filtering.
        human_targets: set[str] = {e.target for e in human_entries if e.target}

        # Filter auto entries: keep only those whose target is NOT in human_targets.
        # Auto entries with target=None are never filtered.
        filtered_auto = [
            e for e in auto_entries
            if e.target is None or e.target not in human_targets
        ]

        human_text = "\n".join(
            FeedbackMerger._render_entry(e) for e in human_entries
        )
        auto_text = "\n".join(
            FeedbackMerger._render_entry(e) for e in filtered_auto
        )

        return human_text, auto_text

    @staticmethod
    def render_human_summary(ledger: FeedbackLedger) -> str:
        """Compact summary for feedback-agent read-only context.

        Format per entry: ``- [type] content (target: X)``

        Returns ``"(No human instructions provided)"`` when there are no active
        human entries.
        """
        human_entries = ledger.active_human_entries()
        if not human_entries:
            return "(No human instructions provided)"

        lines: list[str] = []
        for e in human_entries:
            target_part = f" (target: {e.target})" if e.target else ""
            lines.append(f"- [{e.type.value}] {e.content}{target_part}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _render_entry(entry: FeedbackEntry) -> str:
        """Render a single FeedbackEntry to its prompt string."""
        t = entry.type
        content = entry.content
        target = entry.target or ""

        if t == FeedbackType.PIN_ROW:
            return f"PINNED ROW {target}: {content} -- DO NOT MODIFY THIS ROW"

        if t == FeedbackType.SET_MAPPING:
            return f"REQUIRED MAPPING: Column `{target}` must map to `{content}`"

        if t == FeedbackType.APPLY_RULE:
            return f"RULE: {content}"

        # FREE_TEXT and AUTO both emit content verbatim.
        return content

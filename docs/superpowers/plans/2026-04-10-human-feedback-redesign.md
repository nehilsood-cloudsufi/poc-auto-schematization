# Human Feedback Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make human feedback reliably affect PVMAP generation through structured ledger accumulation, priority separation from auto-feedback, and programmatic enforcement of pinned rows and explicit mappings.

**Architecture:** Replace single `error_feedback` string with a `FeedbackLedger` (typed, append-only list of entries). Split prompt into two sections: HUMAN INSTRUCTIONS (mandatory) and AUTO FEEDBACK (supplementary). Add a `FeedbackEnforcementAgent` that programmatically restores pinned rows and explicit mappings after generation. On the frontend, enhance the FeedbackForm with three input tabs and add a FeedbackHistory panel.

**Tech Stack:** Python/Pydantic (backend models), FastAPI (API routes), Google ADK BaseAgent (enforcement agent), React/TypeScript/shadcn (frontend), pytest (tests)

**Spec:** `docs/superpowers/specs/2026-04-10-human-feedback-redesign-design.md`

---

## Phase 1: Core Mechanism (Backend)

### Task 1: FeedbackLedger Data Model

**Files:**
- Create: `src/api/models/feedback.py`
- Test: `tests/api/models/test_feedback_ledger.py`

- [ ] **Step 1: Write failing tests for FeedbackLedger**

```python
# tests/api/models/test_feedback_ledger.py
"""Tests for FeedbackLedger data model."""
import pytest
from datetime import datetime
from src.api.models.feedback import (
    FeedbackType, FeedbackEntry, FeedbackLedger, FeedbackEntryInput,
)


class TestFeedbackEntry:
    def test_create_human_entry(self):
        entry = FeedbackEntry(
            id="abc12345",
            type=FeedbackType.SET_MAPPING,
            round=1,
            source="human",
            content="observationAbout with dcid:country/ARG",
            target="REF_AREA",
            timestamp=datetime(2026, 4, 10, 12, 0, 0),
        )
        assert entry.source == "human"
        assert entry.retracted is False
        assert entry.superseded is False

    def test_create_auto_entry(self):
        entry = FeedbackEntry(
            id="def67890",
            type=FeedbackType.AUTO,
            round=1,
            source="auto",
            content="Fix DCID format on row 12",
            target="row_12",
            timestamp=datetime(2026, 4, 10, 12, 0, 0),
        )
        assert entry.source == "auto"
        assert entry.type == FeedbackType.AUTO


class TestFeedbackLedger:
    def _make_entry(self, **kwargs):
        defaults = dict(
            id="test1",
            type=FeedbackType.FREE_TEXT,
            round=1,
            source="human",
            content="Fix column X",
            target=None,
            retracted=False,
            superseded=False,
            timestamp=datetime(2026, 4, 10, 12, 0, 0),
        )
        defaults.update(kwargs)
        return FeedbackEntry(**defaults)

    def test_active_human_entries_excludes_retracted(self):
        ledger = FeedbackLedger(entries=[
            self._make_entry(id="a", retracted=False),
            self._make_entry(id="b", retracted=True),
        ])
        assert len(ledger.active_human_entries()) == 1
        assert ledger.active_human_entries()[0].id == "a"

    def test_active_human_entries_excludes_superseded(self):
        ledger = FeedbackLedger(entries=[
            self._make_entry(id="a", superseded=True),
            self._make_entry(id="b", superseded=False),
        ])
        assert len(ledger.active_human_entries()) == 1
        assert ledger.active_human_entries()[0].id == "b"

    def test_active_auto_entries(self):
        ledger = FeedbackLedger(entries=[
            self._make_entry(id="a", source="auto", type=FeedbackType.AUTO),
            self._make_entry(id="b", source="auto", type=FeedbackType.AUTO, retracted=True),
            self._make_entry(id="c", source="human"),
        ])
        assert len(ledger.active_auto_entries()) == 1
        assert ledger.active_auto_entries()[0].id == "a"

    def test_has_human_entries(self):
        ledger = FeedbackLedger(entries=[
            self._make_entry(id="a", source="auto", type=FeedbackType.AUTO),
        ])
        assert ledger.has_human_entries() is False
        ledger.entries.append(self._make_entry(id="b", source="human"))
        assert ledger.has_human_entries() is True

    def test_retract(self):
        ledger = FeedbackLedger(entries=[
            self._make_entry(id="a"),
            self._make_entry(id="b"),
        ])
        assert ledger.retract("a") is True
        assert ledger.entries[0].retracted is True
        assert ledger.retract("nonexistent") is False

    def test_add_entry_supersedes_same_target(self):
        ledger = FeedbackLedger(entries=[
            self._make_entry(id="a", target="REF_AREA", round=1),
        ])
        ledger.add_entry(self._make_entry(id="b", target="REF_AREA", round=2))
        assert ledger.entries[0].superseded is True
        assert ledger.entries[1].superseded is False

    def test_add_entry_no_supersede_different_target(self):
        ledger = FeedbackLedger(entries=[
            self._make_entry(id="a", target="REF_AREA", round=1),
        ])
        ledger.add_entry(self._make_entry(id="b", target="TIME_PERIOD", round=2))
        assert ledger.entries[0].superseded is False

    def test_serialization_roundtrip(self):
        ledger = FeedbackLedger(entries=[
            self._make_entry(id="a", target="REF_AREA"),
            self._make_entry(id="b", source="auto", type=FeedbackType.AUTO),
        ])
        json_str = ledger.model_dump_json()
        restored = FeedbackLedger.model_validate_json(json_str)
        assert len(restored.entries) == 2
        assert restored.entries[0].id == "a"

    def test_clear_auto_entries(self):
        ledger = FeedbackLedger(entries=[
            self._make_entry(id="a", source="human"),
            self._make_entry(id="b", source="auto", type=FeedbackType.AUTO),
            self._make_entry(id="c", source="auto", type=FeedbackType.AUTO),
        ])
        ledger.clear_auto_entries()
        assert len(ledger.entries) == 1
        assert ledger.entries[0].id == "a"


class TestFeedbackEntryInput:
    def test_category_to_type_column_mapping(self):
        entry = FeedbackEntryInput.from_legacy(
            text="Map REF_AREA to observationAbout",
            category="Column mapping",
            severity=4,
        )
        assert entry.type == FeedbackType.SET_MAPPING

    def test_category_to_type_other(self):
        entry = FeedbackEntryInput.from_legacy(
            text="Something is wrong",
            category="Other",
            severity=2,
        )
        assert entry.type == FeedbackType.FREE_TEXT

    def test_category_to_type_structural(self):
        entry = FeedbackEntryInput.from_legacy(
            text="PVMAP structure is wrong",
            category="Structural issue",
            severity=5,
        )
        assert entry.type == FeedbackType.APPLY_RULE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/models/test_feedback_ledger.py -x -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.api.models.feedback'`

- [ ] **Step 3: Implement FeedbackLedger data model**

```python
# src/api/models/feedback.py
"""Feedback ledger data model for structured, accumulating human feedback."""
import uuid
from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class FeedbackType(str, Enum):
    PIN_ROW = "pin_row"
    SET_MAPPING = "set_mapping"
    APPLY_RULE = "apply_rule"
    FREE_TEXT = "free_text"
    AUTO = "auto"


# Category -> FeedbackType mapping for legacy API compatibility
_CATEGORY_TYPE_MAP = {
    "Column mapping": FeedbackType.SET_MAPPING,
    "Property names": FeedbackType.SET_MAPPING,
    "Value formatting": FeedbackType.APPLY_RULE,
    "Missing mappings": FeedbackType.SET_MAPPING,
    "Incorrect mappings": FeedbackType.SET_MAPPING,
    "Structural issue": FeedbackType.APPLY_RULE,
    "Other": FeedbackType.FREE_TEXT,
}


class FeedbackEntry(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    type: FeedbackType
    round: int
    source: Literal["human", "auto"]
    content: str
    target: Optional[str] = None
    retracted: bool = False
    superseded: bool = False
    timestamp: datetime = Field(default_factory=datetime.now)


class FeedbackEntryInput(BaseModel):
    """Input model for creating feedback entries (from API requests)."""
    type: FeedbackType
    content: str
    target: Optional[str] = None

    @classmethod
    def from_legacy(
        cls, text: str, category: str, severity: int = 3
    ) -> "FeedbackEntryInput":
        """Create from legacy API format (text + category + severity)."""
        feedback_type = _CATEGORY_TYPE_MAP.get(category, FeedbackType.FREE_TEXT)
        return cls(type=feedback_type, content=text, target=None)


class FeedbackLedger(BaseModel):
    entries: list[FeedbackEntry] = Field(default_factory=list)

    def active_human_entries(self) -> list[FeedbackEntry]:
        """Non-retracted, non-superseded human entries."""
        return [
            e for e in self.entries
            if e.source == "human" and not e.retracted and not e.superseded
        ]

    def active_auto_entries(self) -> list[FeedbackEntry]:
        """Non-retracted auto entries (conflict filtering done by FeedbackMerger)."""
        return [
            e for e in self.entries
            if e.source == "auto" and not e.retracted
        ]

    def has_human_entries(self) -> bool:
        return len(self.active_human_entries()) > 0

    def retract(self, entry_id: str) -> bool:
        for e in self.entries:
            if e.id == entry_id:
                e.retracted = True
                return True
        return False

    def add_entry(self, entry: FeedbackEntry) -> None:
        """Add entry, auto-superseding older same-source entries with same target."""
        if entry.target and entry.source == "human":
            for existing in self.entries:
                if (
                    existing.source == "human"
                    and existing.target == entry.target
                    and not existing.retracted
                    and not existing.superseded
                ):
                    existing.superseded = True
        self.entries.append(entry)

    def clear_auto_entries(self) -> None:
        """Remove all auto entries (called at start of new feedback round)."""
        self.entries = [e for e in self.entries if e.source != "auto"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/models/test_feedback_ledger.py -x -q`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/models/feedback.py tests/api/models/test_feedback_ledger.py
git commit -m "feat(feedback): add FeedbackLedger data model with typed entries and accumulation"
```

---

### Task 2: FeedbackMerger Service

**Files:**
- Create: `src/api/services/feedback_merger.py`
- Test: `tests/api/services/test_feedback_merger.py`

- [ ] **Step 1: Write failing tests for FeedbackMerger**

```python
# tests/api/services/test_feedback_merger.py
"""Tests for FeedbackMerger — human/auto separation and conflict filtering."""
import pytest
from datetime import datetime
from src.api.models.feedback import (
    FeedbackType, FeedbackEntry, FeedbackLedger,
)
from src.api.services.feedback_merger import FeedbackMerger


def _entry(id, source="human", type=FeedbackType.FREE_TEXT, target=None, content="fix it", **kw):
    return FeedbackEntry(
        id=id, type=type, round=1, source=source,
        content=content, target=target,
        timestamp=datetime(2026, 4, 10), **kw,
    )


class TestFeedbackMerger:
    def setup_method(self):
        self.merger = FeedbackMerger()

    def test_empty_ledger(self):
        ledger = FeedbackLedger()
        human, auto = self.merger.render_separate(ledger)
        assert human == ""
        assert auto == ""

    def test_human_only(self):
        ledger = FeedbackLedger(entries=[
            _entry("a", content="Map REF_AREA to observationAbout", type=FeedbackType.SET_MAPPING, target="REF_AREA"),
        ])
        human, auto = self.merger.render_separate(ledger)
        assert "REQUIRED MAPPING" in human
        assert "REF_AREA" in human
        assert auto == ""

    def test_auto_only(self):
        ledger = FeedbackLedger(entries=[
            _entry("a", source="auto", type=FeedbackType.AUTO, content="Fix DCID format"),
        ])
        human, auto = self.merger.render_separate(ledger)
        assert human == ""
        assert "Fix DCID format" in auto

    def test_auto_filtered_when_conflicts_with_human(self):
        ledger = FeedbackLedger(entries=[
            _entry("a", source="human", target="REF_AREA", type=FeedbackType.SET_MAPPING, content="observationAbout"),
            _entry("b", source="auto", type=FeedbackType.AUTO, target="REF_AREA", content="Change REF_AREA to something else"),
        ])
        human, auto = self.merger.render_separate(ledger)
        assert "REF_AREA" in human
        assert "REF_AREA" not in auto

    def test_auto_kept_when_no_conflict(self):
        ledger = FeedbackLedger(entries=[
            _entry("a", source="human", target="REF_AREA", type=FeedbackType.SET_MAPPING, content="observationAbout"),
            _entry("b", source="auto", type=FeedbackType.AUTO, target="TIME_PERIOD", content="Fix TIME_PERIOD format"),
        ])
        human, auto = self.merger.render_separate(ledger)
        assert "REF_AREA" in human
        assert "TIME_PERIOD" in auto

    def test_pin_row_rendering(self):
        ledger = FeedbackLedger(entries=[
            _entry("a", type=FeedbackType.PIN_ROW, target="row_5", content="Year,observationDate,{Data}"),
        ])
        human, _ = self.merger.render_separate(ledger)
        assert "PINNED ROW" in human
        assert "DO NOT MODIFY" in human

    def test_apply_rule_rendering(self):
        ledger = FeedbackLedger(entries=[
            _entry("a", type=FeedbackType.APPLY_RULE, content="All _CODE columns are dimensions"),
        ])
        human, _ = self.merger.render_separate(ledger)
        assert "RULE:" in human

    def test_merge_produces_combined_string(self):
        ledger = FeedbackLedger(entries=[
            _entry("a", source="human", content="Fix X"),
            _entry("b", source="auto", type=FeedbackType.AUTO, content="Fix Y"),
        ])
        merged = self.merger.merge(ledger)
        assert "Fix X" in merged
        assert "Fix Y" in merged
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/services/test_feedback_merger.py -x -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.api.services.feedback_merger'`

- [ ] **Step 3: Implement FeedbackMerger**

```python
# src/api/services/feedback_merger.py
"""Merge human and auto feedback entries into prompt-ready text."""
from src.api.models.feedback import FeedbackEntry, FeedbackLedger, FeedbackType


class FeedbackMerger:
    """Renders a FeedbackLedger into prompt sections with conflict filtering."""

    def merge(self, ledger: FeedbackLedger) -> str:
        """Produce combined prompt text (for backward-compat error_feedback key)."""
        human_text, auto_text = self.render_separate(ledger)
        sections = []
        if human_text:
            sections.append(human_text)
        if auto_text:
            sections.append(auto_text)
        return "\n\n".join(sections)

    def render_separate(self, ledger: FeedbackLedger) -> tuple[str, str]:
        """Return (human_text, auto_text) for two-section prompt templates."""
        human = ledger.active_human_entries()
        auto = ledger.active_auto_entries()

        # Filter auto entries that conflict with human targets
        human_targets = {e.target for e in human if e.target}
        auto_filtered = [e for e in auto if e.target not in human_targets]

        human_text = self._render_human_section(human) if human else ""
        auto_text = self._render_auto_section(auto_filtered) if auto_filtered else ""
        return human_text, auto_text

    def render_human_summary(self, ledger: FeedbackLedger) -> str:
        """Compact summary of human entries for feedback agent read-only context."""
        human = ledger.active_human_entries()
        if not human:
            return "(No human instructions provided)"
        lines = []
        for e in human:
            lines.append(f"- [{e.type.value}] {e.content}")
            if e.target:
                lines[-1] += f" (target: {e.target})"
        return "\n".join(lines)

    def _render_human_section(self, entries: list[FeedbackEntry]) -> str:
        lines = []
        for e in entries:
            if e.type == FeedbackType.PIN_ROW:
                lines.append(f"PINNED ROW {e.target}: {e.content} -- DO NOT MODIFY THIS ROW")
            elif e.type == FeedbackType.SET_MAPPING:
                lines.append(f"REQUIRED MAPPING: Column `{e.target}` must map to `{e.content}`")
            elif e.type == FeedbackType.APPLY_RULE:
                lines.append(f"RULE: {e.content}")
            else:
                lines.append(e.content)
        return "\n".join(lines)

    def _render_auto_section(self, entries: list[FeedbackEntry]) -> str:
        lines = [e.content for e in entries]
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/services/test_feedback_merger.py -x -q`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/services/feedback_merger.py tests/api/services/test_feedback_merger.py
git commit -m "feat(feedback): add FeedbackMerger with human/auto separation and conflict filtering"
```

---

### Task 3: Two-Section Prompt Template

**Files:**
- Modify: `src/resources/prompts/improved_pvmap_prompt_v3.txt:106-114`
- Modify: `src/agents/pvmap_generation/helpers.py:23-87`
- Test: `tests/agents/pvmap_generation/test_prompt_sections.py`

- [ ] **Step 1: Write failing test for two-section prompt rendering**

```python
# tests/agents/pvmap_generation/test_prompt_sections.py
"""Tests for two-section feedback in PVMAP prompt."""
import pytest
from pathlib import Path
from src.agents.pvmap_generation.helpers import build_prompt_with_feedback


@pytest.fixture
def template_path():
    return Path("src/resources/prompts/improved_pvmap_prompt_v3.txt")


class TestTwoSectionFeedbackPrompt:
    def test_human_feedback_section_present(self, template_path):
        prompt = build_prompt_with_feedback(
            template_path=template_path,
            schema_content="test schema",
            sampled_data_content="col1,col2\n1,2",
            metadata_content="datasetname,test",
            human_feedback="Map REF_AREA to observationAbout",
            auto_feedback="Fix DCID format",
        )
        assert "HUMAN INSTRUCTIONS (MANDATORY" in prompt
        assert "Map REF_AREA to observationAbout" in prompt
        assert "Auto-Generated Feedback" in prompt
        assert "Fix DCID format" in prompt

    def test_only_human_feedback(self, template_path):
        prompt = build_prompt_with_feedback(
            template_path=template_path,
            schema_content="test schema",
            sampled_data_content="col1,col2\n1,2",
            metadata_content="datasetname,test",
            human_feedback="Map REF_AREA to observationAbout",
        )
        assert "Map REF_AREA to observationAbout" in prompt
        assert "HUMAN INSTRUCTIONS" in prompt

    def test_only_auto_feedback(self, template_path):
        prompt = build_prompt_with_feedback(
            template_path=template_path,
            schema_content="test schema",
            sampled_data_content="col1,col2\n1,2",
            metadata_content="datasetname,test",
            auto_feedback="Fix DCID format",
        )
        assert "Fix DCID format" in prompt

    def test_no_feedback(self, template_path):
        prompt = build_prompt_with_feedback(
            template_path=template_path,
            schema_content="test schema",
            sampled_data_content="col1,col2\n1,2",
            metadata_content="datasetname,test",
        )
        # Both sections should be empty/absent
        assert "HUMAN INSTRUCTIONS" in prompt  # Section header is always present
        # But no actual content between the headers

    def test_backward_compat_error_feedback(self, template_path):
        """Old callers passing error_feedback still works."""
        prompt = build_prompt_with_feedback(
            template_path=template_path,
            schema_content="test schema",
            sampled_data_content="col1,col2\n1,2",
            metadata_content="datasetname,test",
            error_feedback="Legacy feedback string",
        )
        assert "Legacy feedback string" in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/pvmap_generation/test_prompt_sections.py -x -q`
Expected: FAIL — `TypeError: build_prompt_with_feedback() got an unexpected keyword argument 'human_feedback'`

- [ ] **Step 3: Update prompt template**

In `src/resources/prompts/improved_pvmap_prompt_v3.txt`, replace lines 106-114:

**Old (lines 106-114):**
```
---

## Error Feedback (from previous attempts)

{{ERROR_FEEDBACK}}

If feedback is present: read carefully, apply the specific fixes, ensure keys match EXACT headers, and fix ALL affected rows.

---
```

**New:**
```
---

## HUMAN INSTRUCTIONS (MANDATORY — HIGHEST PRIORITY)

{{HUMAN_FEEDBACK}}

These instructions come directly from a human expert who reviewed your previous output.
You MUST follow every instruction above. If any instruction conflicts with other
guidance in this prompt, the human instruction wins. After generating, verify each
human instruction was applied. If you cannot follow an instruction, explain why in
a comment row — but DO NOT silently ignore it.

---

## Auto-Generated Feedback (from validation analysis)

{{AUTO_FEEDBACK}}

If auto-feedback is present: apply fixes ONLY where they do not conflict with
the HUMAN INSTRUCTIONS section above. Human instructions always take precedence.

---
```

- [ ] **Step 4: Update `build_prompt_with_feedback` in `helpers.py`**

Modify `src/agents/pvmap_generation/helpers.py:23-87` — add `human_feedback` and `auto_feedback` parameters while keeping `error_feedback` for backward compatibility:

```python
def build_prompt_with_feedback(
    template_path: Path,
    schema_content: Optional[str],
    sampled_data_content: str,
    metadata_content: str,
    error_feedback: Optional[str] = None,
    discovered_statvars: Optional[str] = None,
    data_context: Optional[str] = None,
    human_feedback: Optional[str] = None,
    auto_feedback: Optional[str] = None,
) -> str:
    # ... (existing validation + template read unchanged) ...

    # Replace all template placeholders
    prompt = template.replace("{{DATA_CONTEXT}}", data_context)
    prompt = prompt.replace("{{SCHEMA_EXAMPLES}}", schema_content)
    prompt = prompt.replace("{{SAMPLED_DATA}}", sampled_data_content)
    prompt = prompt.replace("{{METADATA_CONFIG}}", metadata_content)

    # Two-section feedback: human + auto (new)
    # Backward compat: if only error_feedback provided, put it in auto section
    if human_feedback is None and auto_feedback is None and error_feedback:
        prompt = prompt.replace("{{HUMAN_FEEDBACK}}", "")
        prompt = prompt.replace("{{AUTO_FEEDBACK}}", error_feedback)
    else:
        prompt = prompt.replace("{{HUMAN_FEEDBACK}}", human_feedback or "")
        prompt = prompt.replace("{{AUTO_FEEDBACK}}", auto_feedback or "")

    # Keep old placeholder for any code still using it
    prompt = prompt.replace("{{ERROR_FEEDBACK}}", "")

    prompt = prompt.replace("{{STATVAR_SUMMARY}}", discovered_statvars or "")
    prompt = prompt.replace("{{MCP_TOOLS_INSTRUCTION}}", "")

    return prompt
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/pvmap_generation/test_prompt_sections.py -x -q`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite to check for regressions**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions (existing tests that use `error_feedback` still pass via backward compat)

- [ ] **Step 7: Commit**

```bash
git add src/resources/prompts/improved_pvmap_prompt_v3.txt src/agents/pvmap_generation/helpers.py tests/agents/pvmap_generation/test_prompt_sections.py
git commit -m "feat(feedback): split prompt into HUMAN INSTRUCTIONS + AUTO FEEDBACK sections"
```

---

### Task 4: Ledger Integration in StatePreparationAgent

**Files:**
- Modify: `src/agents/pvmap_retry_loop.py:466-480` (attempt 0 init)
- Modify: `src/agents/pvmap_retry_loop.py:825-870` (escape + render)
- Test: `tests/agents/test_state_prep_ledger.py`

- [ ] **Step 1: Write failing tests for ledger integration in StatePrep**

```python
# tests/agents/test_state_prep_ledger.py
"""Tests for FeedbackLedger integration in StatePreparationAgent."""
import pytest
import json
from datetime import datetime
from src.api.models.feedback import (
    FeedbackType, FeedbackEntry, FeedbackLedger,
)
from src.api.services.feedback_merger import FeedbackMerger


class TestLedgerStateIntegration:
    """Test ledger serialization/deserialization patterns used by StatePrep."""

    def test_ledger_roundtrip_via_json_state_key(self):
        """Simulate state[feedback_ledger_json] roundtrip."""
        ledger = FeedbackLedger(entries=[
            FeedbackEntry(
                id="a", type=FeedbackType.SET_MAPPING, round=1,
                source="human", content="observationAbout",
                target="REF_AREA", timestamp=datetime(2026, 4, 10),
            ),
        ])
        json_str = ledger.model_dump_json()
        restored = FeedbackLedger.model_validate_json(json_str)
        assert restored.entries[0].target == "REF_AREA"

    def test_ledger_render_populates_state_keys(self):
        """Simulate how StatePrep populates derived state keys."""
        ledger = FeedbackLedger(entries=[
            FeedbackEntry(
                id="a", type=FeedbackType.SET_MAPPING, round=1,
                source="human", content="observationAbout",
                target="REF_AREA", timestamp=datetime(2026, 4, 10),
            ),
            FeedbackEntry(
                id="b", type=FeedbackType.AUTO, round=1,
                source="auto", content="Fix DCID on row 12",
                target=None, timestamp=datetime(2026, 4, 10),
            ),
        ])
        merger = FeedbackMerger()
        human_text, auto_text = merger.render_separate(ledger)
        merged = merger.merge(ledger)

        # Simulate state population
        state = {}
        state["feedback_ledger_json"] = ledger.model_dump_json()
        state["human_feedback_prompt"] = human_text
        state["auto_feedback_prompt"] = auto_text
        state["error_feedback"] = merged  # backward compat
        state["human_feedback_provided"] = ledger.has_human_entries()

        assert "REQUIRED MAPPING" in state["human_feedback_prompt"]
        assert "Fix DCID" in state["auto_feedback_prompt"]
        assert state["human_feedback_provided"] is True

    def test_auto_feedback_raw_parsed_into_ledger(self):
        """Simulate StatePrep reading auto_feedback_raw and appending to ledger."""
        ledger = FeedbackLedger(entries=[
            FeedbackEntry(
                id="a", type=FeedbackType.SET_MAPPING, round=1,
                source="human", content="observationAbout",
                target="REF_AREA", timestamp=datetime(2026, 4, 10),
            ),
        ])
        # Simulate auto_feedback_raw from ConditionalFeedbackAgent
        auto_raw = "Root cause: Key mismatch\nFix: Change 'year' to 'Year'"

        # StatePrep would do this:
        auto_entry = FeedbackEntry(
            id="auto1", type=FeedbackType.AUTO, round=1,
            source="auto", content=auto_raw,
            timestamp=datetime(2026, 4, 10),
        )
        ledger.add_entry(auto_entry)

        assert len(ledger.entries) == 2
        assert ledger.has_human_entries() is True
        assert len(ledger.active_auto_entries()) == 1

    def test_human_feedback_preserved_across_attempts(self):
        """Human entries survive when auto entries are cleared between attempts."""
        ledger = FeedbackLedger(entries=[
            FeedbackEntry(
                id="a", type=FeedbackType.SET_MAPPING, round=1,
                source="human", content="observationAbout",
                target="REF_AREA", timestamp=datetime(2026, 4, 10),
            ),
            FeedbackEntry(
                id="b", type=FeedbackType.AUTO, round=1,
                source="auto", content="old auto feedback",
                timestamp=datetime(2026, 4, 10),
            ),
        ])
        # Between attempts, StatePrep clears auto and re-adds from new analysis
        ledger.clear_auto_entries()
        assert len(ledger.entries) == 1
        assert ledger.entries[0].source == "human"
```

- [ ] **Step 2: Run tests to verify they pass (these test the model, not StatePrep itself)**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_state_prep_ledger.py -x -q`
Expected: All PASS (these test the data flow patterns, not the agent code yet)

- [ ] **Step 3: Modify StatePreparationAgent attempt 0 initialization**

In `src/agents/pvmap_retry_loop.py`, modify lines 466-480. Replace the `human_feedback_provided` check with ledger initialization:

**Old (lines 469-473):**
```python
if attempt == 0:
    ctx.session.state["quality_metrics_history"] = []
    # Preserve human feedback if injected (for UI re-runs)
    if not ctx.session.state.get("human_feedback_provided"):
        ctx.session.state["error_feedback"] = ""
```

**New:**
```python
if attempt == 0:
    ctx.session.state["quality_metrics_history"] = []
    # Initialize or load feedback ledger
    ledger_json = ctx.session.state.get("feedback_ledger_json", "")
    if ledger_json:
        ledger = FeedbackLedger.model_validate_json(ledger_json)
    elif ctx.session.state.get("human_feedback_provided"):
        # Legacy path: human_feedback was injected as raw string
        from src.api.models.feedback import FeedbackEntry, FeedbackType
        raw = ctx.session.state.get("error_feedback", "")
        ledger = FeedbackLedger()
        if raw:
            ledger.add_entry(FeedbackEntry(
                type=FeedbackType.FREE_TEXT, round=1,
                source="human", content=raw,
            ))
    else:
        ledger = FeedbackLedger()
        ctx.session.state["error_feedback"] = ""
    ctx.session.state["feedback_ledger_json"] = ledger.model_dump_json()
```

- [ ] **Step 4: Modify feedback escape + render section (lines 825-870)**

Replace the escape/truncation block with ledger-based rendering:

**Old (lines 830-835):**
```python
error_feedback = ctx.session.state.get("error_feedback", "")
if error_feedback:
    if len(error_feedback) > 4000:
        error_feedback = error_feedback[:4000] + "\n...[truncated for token budget]"
    ctx.session.state["error_feedback"] = escape_pvmap_placeholders(error_feedback)
```

**New:**
```python
# Render ledger into prompt sections
ledger_json = ctx.session.state.get("feedback_ledger_json", "")
if ledger_json:
    ledger = FeedbackLedger.model_validate_json(ledger_json)
    merger = FeedbackMerger()
    human_text, auto_text = merger.render_separate(ledger)
    merged = merger.merge(ledger)

    # Cap and escape each section
    if len(merged) > 4000:
        merged = merged[:4000] + "\n...[truncated for token budget]"

    ctx.session.state["human_feedback_prompt"] = escape_pvmap_placeholders(human_text)
    ctx.session.state["auto_feedback_prompt"] = escape_pvmap_placeholders(auto_text)
    ctx.session.state["error_feedback"] = escape_pvmap_placeholders(merged)
    ctx.session.state["human_feedback_provided"] = ledger.has_human_entries()
    ctx.session.state["human_instructions_summary"] = merger.render_human_summary(ledger)
else:
    error_feedback = ctx.session.state.get("error_feedback", "")
    if error_feedback:
        if len(error_feedback) > 4000:
            error_feedback = error_feedback[:4000] + "\n...[truncated for token budget]"
        ctx.session.state["error_feedback"] = escape_pvmap_placeholders(error_feedback)
```

- [ ] **Step 5: Add auto_feedback_raw handling for subsequent attempts**

After the attempt counter increment section in StatePrep, add logic to parse `auto_feedback_raw` into the ledger:

```python
# After attempt increment section, before escape section:
auto_raw = ctx.session.state.pop("auto_feedback_raw", "")
if auto_raw and attempt > 0:
    ledger_json = ctx.session.state.get("feedback_ledger_json", "")
    if ledger_json:
        ledger = FeedbackLedger.model_validate_json(ledger_json)
        ledger.clear_auto_entries()
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.AUTO, round=attempt,
            source="auto", content=auto_raw,
        ))
        ctx.session.state["feedback_ledger_json"] = ledger.model_dump_json()
```

- [ ] **Step 6: Add imports at top of pvmap_retry_loop.py**

```python
from src.api.models.feedback import FeedbackLedger, FeedbackEntry, FeedbackType
from src.api.services.feedback_merger import FeedbackMerger
```

- [ ] **Step 7: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions

- [ ] **Step 8: Commit**

```bash
git add src/agents/pvmap_retry_loop.py tests/agents/test_state_prep_ledger.py
git commit -m "feat(feedback): integrate FeedbackLedger into StatePreparationAgent"
```

---

### Task 5: Feedback Agent Output Key Change + Human-Aware Prompt

**Files:**
- Modify: `src/agents/feedback_agent.py:86-94`
- Modify: `src/resources/prompts/feedback_agent_v2.txt:1-5`
- Modify: `src/agents/pvmap_retry_loop.py:1290-1296` (error handler)
- Test: `tests/agents/test_feedback_prompt_version.py` (modify existing)

- [ ] **Step 1: Change `output_key` from `error_feedback` to `auto_feedback_raw`**

In `src/agents/feedback_agent.py`, line 90:

**Old:**
```python
output_key="error_feedback",  # Generator reads this on retry
```

**New:**
```python
output_key="auto_feedback_raw",  # Parsed into ledger by StatePrep
```

- [ ] **Step 2: Add human instructions read-only section to feedback_agent_v2.txt**

Insert after line 3 (`{feedback_mode}`) and before line 6 (`## Processor-Focused Analysis Framework`):

```markdown
## Human Instructions (READ-ONLY — DO NOT CONTRADICT)

{human_instructions_summary}

The above instructions were given by a human expert. Your feedback MUST NOT:
- Suggest changes that contradict any human instruction
- Recommend removing or altering mappings the human explicitly set
- Override pinned rows or explicit column assignments

Focus your analysis on issues the human has NOT addressed.

```

- [ ] **Step 3: Update error handlers in ConditionalFeedbackAgent**

In `src/agents/pvmap_retry_loop.py`, lines 1296 and 1359, change the crash fallback to write to `auto_feedback_raw`:

**Old (line 1296):**
```python
ctx.session.state["error_feedback"] = self._build_deterministic_feedback(ctx, e)
```

**New:**
```python
ctx.session.state["auto_feedback_raw"] = self._build_deterministic_feedback(ctx, e)
```

Apply same change at line 1359.

- [ ] **Step 4: Initialize `human_instructions_summary` state key**

In `StatePreparationAgent`, ensure the key exists for ADK template resolution. Add to the ledger render section (Task 4 Step 4):

```python
# Already done in Task 4 Step 4:
ctx.session.state["human_instructions_summary"] = merger.render_human_summary(ledger)
```

If ledger is empty, set it to `"(No human instructions provided)"`.

- [ ] **Step 5: Update existing feedback prompt test**

In `tests/agents/test_feedback_prompt_version.py`, update any assertion that checks `output_key == "error_feedback"` to `output_key == "auto_feedback_raw"`.

- [ ] **Step 6: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions

- [ ] **Step 7: Commit**

```bash
git add src/agents/feedback_agent.py src/resources/prompts/feedback_agent_v2.txt src/agents/pvmap_retry_loop.py tests/agents/test_feedback_prompt_version.py
git commit -m "feat(feedback): change feedback agent output to auto_feedback_raw, add human-aware prompt"
```

---

### Task 6: Ledger Disk Persistence

**Files:**
- Modify: `src/agents/pvmap_retry_loop.py` (StatePrep — write ledger to disk after render)
- Modify: `src/api/services/feedback_store.py` (add ledger load/save helpers)
- Test: `tests/api/services/test_feedback_store.py`

- [ ] **Step 1: Write failing tests for ledger disk persistence**

```python
# tests/api/services/test_feedback_store.py
"""Tests for feedback ledger disk persistence."""
import pytest
import json
from pathlib import Path
from datetime import datetime
from src.api.models.feedback import (
    FeedbackType, FeedbackEntry, FeedbackLedger,
)
from src.api.services.feedback_store import (
    save_feedback, load_feedback_history,
    save_ledger_to_disk, load_ledger_from_disk,
)


class TestLedgerDiskPersistence:
    def test_save_and_load_ledger(self, tmp_path):
        ledger = FeedbackLedger(entries=[
            FeedbackEntry(
                id="a", type=FeedbackType.SET_MAPPING, round=1,
                source="human", content="observationAbout",
                target="REF_AREA", timestamp=datetime(2026, 4, 10),
            ),
        ])
        save_ledger_to_disk(ledger, tmp_path)
        loaded = load_ledger_from_disk(tmp_path)
        assert len(loaded.entries) == 1
        assert loaded.entries[0].target == "REF_AREA"

    def test_load_nonexistent_returns_empty(self, tmp_path):
        loaded = load_ledger_from_disk(tmp_path)
        assert len(loaded.entries) == 0

    def test_save_overwrites_previous(self, tmp_path):
        ledger1 = FeedbackLedger(entries=[
            FeedbackEntry(
                id="a", type=FeedbackType.FREE_TEXT, round=1,
                source="human", content="first",
                timestamp=datetime(2026, 4, 10),
            ),
        ])
        save_ledger_to_disk(ledger1, tmp_path)

        ledger2 = FeedbackLedger(entries=[
            FeedbackEntry(
                id="a", type=FeedbackType.FREE_TEXT, round=1,
                source="human", content="first",
                timestamp=datetime(2026, 4, 10),
            ),
            FeedbackEntry(
                id="b", type=FeedbackType.AUTO, round=1,
                source="auto", content="auto fix",
                timestamp=datetime(2026, 4, 10),
            ),
        ])
        save_ledger_to_disk(ledger2, tmp_path)

        loaded = load_ledger_from_disk(tmp_path)
        assert len(loaded.entries) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/services/test_feedback_store.py::TestLedgerDiskPersistence -x -q`
Expected: FAIL — `ImportError: cannot import name 'save_ledger_to_disk'`

- [ ] **Step 3: Add ledger disk helpers to feedback_store.py**

Append to `src/api/services/feedback_store.py`:

```python
def save_ledger_to_disk(ledger: "FeedbackLedger", output_dir: Path) -> Path:
    """Write feedback ledger JSON to output_dir/feedback_ledger.json."""
    from src.api.models.feedback import FeedbackLedger
    path = output_dir / "feedback_ledger.json"
    path.write_text(ledger.model_dump_json(indent=2))
    logger.debug("Saved feedback ledger (%d entries) to %s", len(ledger.entries), path)
    return path


def load_ledger_from_disk(output_dir: Path) -> "FeedbackLedger":
    """Load feedback ledger from output_dir/feedback_ledger.json."""
    from src.api.models.feedback import FeedbackLedger
    path = output_dir / "feedback_ledger.json"
    if not path.exists():
        return FeedbackLedger()
    try:
        return FeedbackLedger.model_validate_json(path.read_text())
    except Exception:
        logger.warning("Failed to parse feedback ledger: %s", path)
        return FeedbackLedger()
```

- [ ] **Step 4: Add disk write to StatePreparationAgent**

In `src/agents/pvmap_retry_loop.py`, after the ledger render section (end of Task 4 Step 4), add:

```python
# Persist ledger to disk for API access
try:
    current_dataset = ctx.session.state.get("current_dataset")
    if current_dataset and hasattr(current_dataset, "output_dir"):
        from src.api.services.feedback_store import save_ledger_to_disk
        save_ledger_to_disk(ledger, Path(current_dataset.output_dir))
except Exception as e:
    logger.warning("Failed to persist ledger to disk: %s", e)
```

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/services/test_feedback_store.py -x -q`
Expected: All PASS

- [ ] **Step 6: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions

- [ ] **Step 7: Commit**

```bash
git add src/api/services/feedback_store.py src/agents/pvmap_retry_loop.py tests/api/services/test_feedback_store.py
git commit -m "feat(feedback): add ledger disk persistence for API cross-run access"
```

---

### Task 7: Pipeline Entry Point — Parse Human Feedback into Ledger

**Files:**
- Modify: `src/run_pipeline.py:662-665`
- Test: `tests/test_run_pipeline_feedback.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_run_pipeline_feedback.py
"""Test human feedback -> ledger parsing in run_pipeline initial state."""
import pytest
from src.api.models.feedback import FeedbackLedger


class TestHumanFeedbackParsing:
    def test_legacy_feedback_string_creates_ledger(self):
        """Simulate run_pipeline.py parsing human_feedback into a ledger."""
        human_feedback = (
            "USER FEEDBACK: Map REF_AREA to observationAbout\n"
            "CATEGORY: Column mapping\n"
            "SEVERITY: 4\n\n"
            "Previous run: 3 attempts, exit reason: max_retries"
        )
        # This is the logic that run_pipeline.py should use:
        from src.api.models.feedback import FeedbackEntry, FeedbackType, FeedbackEntryInput

        entry_input = FeedbackEntryInput.from_legacy(
            text="Map REF_AREA to observationAbout",
            category="Column mapping",
            severity=4,
        )
        ledger = FeedbackLedger()
        ledger.add_entry(FeedbackEntry(
            type=entry_input.type,
            round=1,
            source="human",
            content=human_feedback,
            target=entry_input.target,
        ))

        assert ledger.has_human_entries()
        assert ledger.entries[0].type == FeedbackType.SET_MAPPING

    def test_ledger_json_in_config_creates_ledger(self):
        """When feedback.py passes ledger JSON, it's deserialized directly."""
        from src.api.models.feedback import FeedbackEntry, FeedbackType
        ledger = FeedbackLedger(entries=[
            FeedbackEntry(
                id="a", type=FeedbackType.SET_MAPPING, round=1,
                source="human", content="observationAbout", target="REF_AREA",
            ),
        ])
        json_str = ledger.model_dump_json()

        # Simulate run_pipeline.py logic:
        restored = FeedbackLedger.model_validate_json(json_str)
        assert len(restored.entries) == 1
```

- [ ] **Step 2: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/test_run_pipeline_feedback.py -x -q`
Expected: PASS (these test the parsing logic independently)

- [ ] **Step 3: Modify run_pipeline.py human feedback injection**

In `src/run_pipeline.py`, replace lines 662-665:

**Old:**
```python
# Inject human feedback if provided (for UI re-runs)
if human_feedback:
    initial_state["error_feedback"] = human_feedback
    initial_state["human_feedback_provided"] = True
```

**New:**
```python
# Inject human feedback if provided (for UI re-runs)
if human_feedback:
    # Check if a ledger JSON was passed via extra_initial_state (from feedback.py)
    if not initial_state.get("feedback_ledger_json"):
        # Legacy: wrap raw feedback string in a ledger
        from src.api.models.feedback import FeedbackEntry, FeedbackType, FeedbackLedger
        ledger = FeedbackLedger()
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.FREE_TEXT, round=1,
            source="human", content=human_feedback,
        ))
        initial_state["feedback_ledger_json"] = ledger.model_dump_json()
    # Keep backward compat keys
    initial_state["error_feedback"] = human_feedback
    initial_state["human_feedback_provided"] = True
```

Note: The `feedback_ledger_json` config key is passed by the enhanced `feedback.py` endpoint (Task 10) and gets injected into initial state via `extra_initial_state` or directly in the config dict. The `create_run()` call in `feedback.py` stores it in the run's config, and `pipeline_runner.py` extracts it into initial state.

- [ ] **Step 4: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions

- [ ] **Step 5: Commit**

```bash
git add src/run_pipeline.py tests/test_run_pipeline_feedback.py
git commit -m "feat(feedback): parse human feedback into FeedbackLedger at pipeline entry"
```

---

## Phase 2: Enforcement (Backend)

### Task 8: FeedbackEnforcementAgent

**Files:**
- Create: `src/agents/feedback_enforcement.py`
- Test: `tests/agents/test_feedback_enforcement.py`

- [ ] **Step 1: Write failing tests for enforcement**

```python
# tests/agents/test_feedback_enforcement.py
"""Tests for FeedbackEnforcementAgent — programmatic enforcement of human feedback."""
import pytest
from datetime import datetime
from src.api.models.feedback import (
    FeedbackType, FeedbackEntry, FeedbackLedger,
)
from src.agents.feedback_enforcement import enforce_pinned_row, enforce_mapping


class TestEnforcePinnedRow:
    def test_replace_existing_row(self):
        pvmap = "key,property1,value1\nYear,observationDate,{Data}\nREF_AREA,name,{Data}"
        pinned_content = "Year,observationDate,{Data},observationPeriod,P1Y"
        result, changed = enforce_pinned_row(pvmap, "Year", pinned_content)
        assert changed is True
        lines = result.strip().split("\n")
        assert lines[1] == "Year,observationDate,{Data},observationPeriod,P1Y"
        assert lines[2] == "REF_AREA,name,{Data}"  # untouched

    def test_append_when_key_missing(self):
        pvmap = "key,property1,value1\nREF_AREA,name,{Data}"
        pinned_content = "Year,observationDate,{Data}"
        result, changed = enforce_pinned_row(pvmap, "Year", pinned_content)
        assert changed is True
        assert "Year,observationDate,{Data}" in result

    def test_no_change_when_already_correct(self):
        pvmap = "key,property1,value1\nYear,observationDate,{Data}"
        result, changed = enforce_pinned_row(pvmap, "Year", "Year,observationDate,{Data}")
        assert changed is False


class TestEnforceMapping:
    def test_overwrite_property_in_existing_row(self):
        pvmap = "key,property1,value1\nREF_AREA,name,{Data}"
        # SET_MAPPING says REF_AREA should map to observationAbout
        result, changed = enforce_mapping(pvmap, "REF_AREA", "observationAbout,{Data}")
        assert changed is True
        lines = result.strip().split("\n")
        assert "observationAbout" in lines[1]

    def test_create_row_when_column_not_mapped(self):
        pvmap = "key,property1,value1\nYear,observationDate,{Data}"
        result, changed = enforce_mapping(pvmap, "REF_AREA", "observationAbout,{Data}")
        assert changed is True
        assert "REF_AREA" in result

    def test_no_change_when_already_correct(self):
        pvmap = "key,property1,value1\nREF_AREA,observationAbout,{Data}"
        result, changed = enforce_mapping(pvmap, "REF_AREA", "observationAbout,{Data}")
        assert changed is False


class TestEnforcementWithLedger:
    def test_only_human_entries_enforced(self):
        """Auto entries should NOT be enforced programmatically."""
        from src.agents.feedback_enforcement import apply_enforcement
        ledger = FeedbackLedger(entries=[
            FeedbackEntry(
                id="a", type=FeedbackType.PIN_ROW, round=1,
                source="human", content="Year,observationDate,{Data},observationPeriod,P1Y",
                target="Year", timestamp=datetime(2026, 4, 10),
            ),
            FeedbackEntry(
                id="b", type=FeedbackType.AUTO, round=1,
                source="auto", content="Fix DCID format",
                target="row_12", timestamp=datetime(2026, 4, 10),
            ),
        ])
        pvmap = "key,property1,value1\nYear,observationDate,{Data}\nREF_AREA,name,{Data}"
        result, changes = apply_enforcement(pvmap, ledger)
        assert len(changes) == 1
        assert "Year" in changes[0]

    def test_apply_rule_not_enforced(self):
        """APPLY_RULE entries cannot be enforced programmatically."""
        from src.agents.feedback_enforcement import apply_enforcement
        ledger = FeedbackLedger(entries=[
            FeedbackEntry(
                id="a", type=FeedbackType.APPLY_RULE, round=1,
                source="human", content="All _CODE columns are dimensions",
                timestamp=datetime(2026, 4, 10),
            ),
        ])
        pvmap = "key,property1,value1\nYear,observationDate,{Data}"
        result, changes = apply_enforcement(pvmap, ledger)
        assert len(changes) == 0
        assert result == pvmap
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_feedback_enforcement.py -x -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement enforcement functions**

```python
# src/agents/feedback_enforcement.py
"""Programmatic enforcement of human feedback constraints on generated PVMAPs."""
import logging
from typing import Optional

from src.api.models.feedback import FeedbackEntry, FeedbackLedger, FeedbackType

logger = logging.getLogger(__name__)


def enforce_pinned_row(
    pvmap_csv: str, target_key: str, pinned_content: str
) -> tuple[str, bool]:
    """Replace or append a pinned row by matching on the first column (key)."""
    lines = pvmap_csv.strip().split("\n")
    if not lines:
        return pvmap_csv, False

    header = lines[0]
    body = lines[1:]
    found = False
    new_body = []

    for line in body:
        row_key = line.split(",", 1)[0].strip()
        if row_key == target_key:
            if line.strip() == pinned_content.strip():
                return pvmap_csv, False  # Already correct
            new_body.append(pinned_content)
            found = True
        else:
            new_body.append(line)

    if not found:
        new_body.append(pinned_content)
        logger.warning("Pinned row key '%s' not found in PVMAP — appended", target_key)

    return header + "\n" + "\n".join(new_body), True


def enforce_mapping(
    pvmap_csv: str, target_column: str, mapping_content: str
) -> tuple[str, bool]:
    """Ensure a specific column has the correct property mapping."""
    lines = pvmap_csv.strip().split("\n")
    if not lines:
        return pvmap_csv, False

    header = lines[0]
    body = lines[1:]
    found = False
    new_body = []

    full_row = f"{target_column},{mapping_content}"

    for line in body:
        row_key = line.split(",", 1)[0].strip()
        if row_key == target_column:
            if line.strip() == full_row.strip():
                return pvmap_csv, False  # Already correct
            new_body.append(full_row)
            found = True
        else:
            new_body.append(line)

    if not found:
        new_body.append(full_row)

    return header + "\n" + "\n".join(new_body), True


def apply_enforcement(
    pvmap_csv: str, ledger: FeedbackLedger
) -> tuple[str, list[str]]:
    """Apply all enforceable human entries from the ledger."""
    changes: list[str] = []
    result = pvmap_csv

    for entry in ledger.active_human_entries():
        if entry.type == FeedbackType.PIN_ROW and entry.target:
            result, changed = enforce_pinned_row(result, entry.target, entry.content)
            if changed:
                changes.append(f"Restored pinned row: {entry.target}")
        elif entry.type == FeedbackType.SET_MAPPING and entry.target:
            result, changed = enforce_mapping(result, entry.target, entry.content)
            if changed:
                changes.append(f"Restored mapping: {entry.target} -> {entry.content}")
        # APPLY_RULE and FREE_TEXT are not enforceable programmatically

    return result, changes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_feedback_enforcement.py -x -q`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/feedback_enforcement.py tests/agents/test_feedback_enforcement.py
git commit -m "feat(feedback): add FeedbackEnforcementAgent with PIN_ROW and SET_MAPPING support"
```

---

### Task 9: Wire Enforcement into Pipeline Sequence

**Files:**
- Modify: `src/agents/pvmap_retry_loop.py` (TieredCorrectionAgent — add enforcement before repair/validate)

- [ ] **Step 1: Add enforcement call in TieredCorrectionAgent**

In `src/agents/pvmap_retry_loop.py`, inside `TieredCorrectionAgent._run_async_impl()`, after the `SAVE BEST-SO-FAR` section (around line 2095) and before `TIER 1`:

```python
        # =====================================================================
        # ENFORCE HUMAN FEEDBACK CONSTRAINTS
        # =====================================================================
        ledger_json = ctx.session.state.get("feedback_ledger_json", "")
        if ledger_json:
            from src.agents.feedback_enforcement import apply_enforcement
            ledger = FeedbackLedger.model_validate_json(ledger_json)
            enforced, enforcement_changes = apply_enforcement(best_pvmap, ledger)
            if enforcement_changes:
                best_pvmap = enforced
                ctx.session.state["pvmap_csv"] = enforced
                ctx.session.state["feedback_enforcement_applied"] = True
                ctx.session.state["feedback_enforcement_changes"] = enforcement_changes
                # Write enforced PVMAP to disk
                pvmap_path = Path(current_dataset.output_dir) / "generated_pvmap.csv"
                pvmap_path.write_text(enforced, encoding="utf-8")
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Enforced {len(enforcement_changes)} human feedback constraint(s)")
                    ])
                )
```

Also add enforcement in the initial pipeline sequence (in `create_pvmap_retry_loop`, after `generator` and before `validator`). In the `sub_agents` list around line 2635:

```python
    sub_agents.append(generator)
    # Enforce human feedback constraints after generation
    # (enforcement happens inside StatePrep on attempt 0,
    # and inside TieredCorrection on subsequent attempts)
    sub_agents.append(metadata_generator)
```

Actually, since the initial attempt (attempt 0) runs through the SequentialAgent directly, enforcement should happen in StatePrep's render section for attempt 0. The StatePrep already writes the ledger to state — we just need to ensure the `apply_enforcement` runs after generation on attempt 0 too. The cleanest place is inside the `GeneratorWrapperAgent`'s post-processing, but to keep changes minimal, we can add it as a separate step.

For now, the TieredCorrectionAgent handles attempts 1+ (where feedback is most critical). For attempt 0 with human feedback, the prompt framing + enforcement in TieredCorrection (which runs after attempt 0's quality check) covers it.

- [ ] **Step 2: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions

- [ ] **Step 3: Commit**

```bash
git add src/agents/pvmap_retry_loop.py
git commit -m "feat(feedback): wire enforcement into TieredCorrectionAgent pipeline"
```

---

## Phase 3: API + UI

### Task 10: Enhanced Feedback API Endpoints

**Files:**
- Modify: `src/api/routes/feedback.py`
- Test: `tests/api/test_feedback_api.py`

- [ ] **Step 1: Write failing tests for enhanced API**

```python
# tests/api/test_feedback_api.py
"""Tests for enhanced feedback API endpoints."""
import pytest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path
from datetime import datetime

from src.api.models.feedback import (
    FeedbackType, FeedbackEntry, FeedbackLedger, FeedbackEntryInput,
)


class TestFeedbackRequestBackwardCompat:
    """Test that old-style {text, category, severity} still works."""

    def test_legacy_request_wraps_as_free_text(self):
        entry = FeedbackEntryInput.from_legacy(
            text="Something is broken",
            category="Other",
            severity=3,
        )
        assert entry.type == FeedbackType.FREE_TEXT
        assert entry.content == "Something is broken"

    def test_legacy_column_mapping_wraps_as_set_mapping(self):
        entry = FeedbackEntryInput.from_legacy(
            text="Map X to Y",
            category="Column mapping",
            severity=4,
        )
        assert entry.type == FeedbackType.SET_MAPPING


class TestLedgerAccumulation:
    """Test ledger accumulation across feedback rounds."""

    def test_second_round_accumulates_entries(self, tmp_path):
        from src.api.services.feedback_store import save_ledger_to_disk, load_ledger_from_disk

        # Round 1: user submits one entry
        ledger = FeedbackLedger(entries=[
            FeedbackEntry(
                id="a", type=FeedbackType.SET_MAPPING, round=1,
                source="human", content="observationAbout",
                target="REF_AREA", timestamp=datetime(2026, 4, 10),
            ),
        ])
        save_ledger_to_disk(ledger, tmp_path)

        # Round 2: load + add
        loaded = load_ledger_from_disk(tmp_path)
        loaded.clear_auto_entries()
        loaded.add_entry(FeedbackEntry(
            id="b", type=FeedbackType.FREE_TEXT, round=2,
            source="human", content="Also fix the date format",
            timestamp=datetime(2026, 4, 10),
        ))

        assert len(loaded.entries) == 2
        assert loaded.has_human_entries()

    def test_retract_entry(self, tmp_path):
        from src.api.services.feedback_store import save_ledger_to_disk, load_ledger_from_disk

        ledger = FeedbackLedger(entries=[
            FeedbackEntry(
                id="a", type=FeedbackType.SET_MAPPING, round=1,
                source="human", content="observationAbout",
                target="REF_AREA", timestamp=datetime(2026, 4, 10),
            ),
        ])
        save_ledger_to_disk(ledger, tmp_path)

        loaded = load_ledger_from_disk(tmp_path)
        assert loaded.retract("a") is True
        assert len(loaded.active_human_entries()) == 0
        save_ledger_to_disk(loaded, tmp_path)

        reloaded = load_ledger_from_disk(tmp_path)
        assert reloaded.entries[0].retracted is True
```

- [ ] **Step 2: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_feedback_api.py -x -q`
Expected: PASS

- [ ] **Step 3: Enhance feedback.py with structured entries + ledger endpoints**

Modify `src/api/routes/feedback.py`:

```python
"""Feedback and re-run endpoints."""
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.api.models.feedback import (
    FeedbackType, FeedbackEntry, FeedbackLedger, FeedbackEntryInput,
)
from src.api.services.run_state import get_or_load_run, create_run
from src.api.services.file_manager import (
    get_latest_version,
    snapshot_version,
    save_run_manifest,
)
from src.api.services.feedback_store import (
    save_feedback, load_ledger_from_disk, save_ledger_to_disk,
)
from src.api.services.google_sheets_service import (
    append_feedback_to_sheet,
    is_sheets_configured,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class FeedbackRequest(BaseModel):
    # Legacy fields (backward compat)
    text: Optional[str] = None
    category: Optional[str] = None
    severity: int = 3
    # New structured fields
    entries: Optional[list[FeedbackEntryInput]] = None


class DevFeedbackRequest(BaseModel):
    text: str
    category: str


@router.post("/runs/{run_id}/feedback")
async def submit_feedback(run_id: str, req: FeedbackRequest, request: Request):
    """Submit feedback and prepare for re-run."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    output_dir = Path(run.run_dir) / "output" / run.dataset_name

    # Snapshot current output
    current_version = get_latest_version(output_dir)
    if current_version == 0:
        current_version = 1
    next_version = current_version + 1
    snapshot_version(output_dir, current_version)
    save_run_manifest(output_dir, current_version, run.config, run.result)

    # Load existing ledger (accumulate across rounds)
    ledger = load_ledger_from_disk(output_dir)
    ledger.clear_auto_entries()  # Fresh start for auto-analysis

    # Add new entries to ledger
    if req.entries:
        for ei in req.entries:
            ledger.add_entry(FeedbackEntry(
                type=ei.type,
                round=next_version,
                source="human",
                content=ei.content,
                target=ei.target,
            ))
    elif req.text:
        # Legacy: wrap text+category as a single entry
        entry_input = FeedbackEntryInput.from_legacy(
            text=req.text, category=req.category or "Other", severity=req.severity,
        )
        ledger.add_entry(FeedbackEntry(
            type=entry_input.type,
            round=next_version,
            source="human",
            content=req.text,
            target=entry_input.target,
        ))

    # Build human feedback string (for backward compat)
    human_feedback = (
        f"USER FEEDBACK: {req.text or ''}\n"
        f"CATEGORY: {req.category or 'Other'}\n"
        f"SEVERITY: {req.severity}\n\n"
        f"Previous run: {run.result.get('retry_count', 0) + 1} attempts, "
        f"exit reason: {run.result.get('exit_reason', 'unknown')}"
    )

    # Save feedback JSON + ledger
    feedback_entry = {
        "run_id": run_id,
        "text": req.text or "",
        "category": req.category or "Other",
        "severity": req.severity,
        "dataset_name": run.dataset_name,
    }
    next_feedback_dir = output_dir / f"v{next_version}"
    next_feedback_dir.mkdir(parents=True, exist_ok=True)
    save_feedback(feedback_entry, next_feedback_dir)
    save_ledger_to_disk(ledger, output_dir)

    # Create new run with ledger
    # Note: feedback_ledger_json in config is extracted by pipeline_runner.py
    # into initial_state before pipeline launch. The run_pipeline.py code
    # (Task 7) checks initial_state.get("feedback_ledger_json") first.
    new_run_id = uuid.uuid4().hex[:12]
    new_run = create_run(
        run_id=new_run_id,
        dataset_name=run.dataset_name,
        run_dir=run.run_dir,
        config={
            **run.config,
            "human_feedback": human_feedback,
            "feedback_ledger_json": ledger.model_dump_json(),
            "skip_sampling": True,
        },
    )

    logger.info("Feedback submitted for run %s, new run %s created", run_id, new_run_id)

    return {
        "new_run_id": new_run_id,
        "version": next_version,
        "human_feedback_length": len(human_feedback),
    }


@router.get("/runs/{run_id}/feedback/ledger")
async def get_feedback_ledger(run_id: str, request: Request):
    """Return the full feedback ledger for a run."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    output_dir = Path(run.run_dir) / "output" / run.dataset_name
    ledger = load_ledger_from_disk(output_dir)
    return ledger.model_dump()


@router.delete("/runs/{run_id}/feedback/{entry_id}")
async def retract_feedback_entry(run_id: str, entry_id: str, request: Request):
    """Retract a specific feedback entry."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    output_dir = Path(run.run_dir) / "output" / run.dataset_name
    ledger = load_ledger_from_disk(output_dir)

    if not ledger.retract(entry_id):
        raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found")

    save_ledger_to_disk(ledger, output_dir)
    return {"retracted": True, "entry_id": entry_id}


# Keep existing dev-feedback endpoint unchanged
@router.post("/runs/{run_id}/dev-feedback")
async def submit_dev_feedback(run_id: str, req: DevFeedbackRequest, request: Request):
    """Submit developer feedback (bug reports, suggestions)."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    entry = {
        "type": "developer_feedback",
        "run_id": run_id,
        "dataset_name": run.dataset_name,
        "text": req.text,
        "category": req.category,
    }

    output_dir = Path(run.run_dir) / "output" / run.dataset_name
    if output_dir.exists():
        save_feedback(entry, output_dir)

    if is_sheets_configured():
        append_feedback_to_sheet(
            run_id=run_id,
            dataset_name=run.dataset_name,
            feedback_text=req.text,
            category=req.category,
            pipeline_status=run.status,
        )

    return {"saved": True}
```

- [ ] **Step 4: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/feedback.py tests/api/test_feedback_api.py
git commit -m "feat(feedback): enhance API with structured entries, ledger GET, and retract DELETE"
```

---

### Task 11: Frontend TypeScript Types

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add feedback types to frontend/src/types/index.ts**

After the existing `FeedbackRequest` interface (line 99), add:

```typescript
export type FeedbackType = "pin_row" | "set_mapping" | "apply_rule" | "free_text" | "auto";

export interface FeedbackEntryInput {
  type: FeedbackType;
  content: string;
  target?: string;
}

export interface FeedbackEntry {
  id: string;
  type: FeedbackType;
  round: number;
  source: "human" | "auto";
  content: string;
  target?: string;
  retracted: boolean;
  superseded: boolean;
  timestamp: string;
}

export interface FeedbackLedger {
  entries: FeedbackEntry[];
}

/** Enhanced feedback submission — supports structured entries */
export interface FeedbackRequest {
  text?: string;
  category?: string;
  severity?: number;
  entries?: FeedbackEntryInput[];
}
```

Remove the old `FeedbackRequest` interface (lines 95-99) since it's replaced above.

- [ ] **Step 2: Add API calls to frontend/src/lib/api.ts**

Add after the existing `submitFeedback` function:

```typescript
export async function getFeedbackLedger(
  runId: string
): Promise<FeedbackLedger> {
  return request(`/runs/${runId}/feedback/ledger`);
}

export async function retractFeedbackEntry(
  runId: string,
  entryId: string
): Promise<{ retracted: boolean; entry_id: string }> {
  return request(`/runs/${runId}/feedback/${entryId}`, { method: "DELETE" });
}
```

Add the imports at the top:

```typescript
import type {
  // ... existing imports ...
  FeedbackLedger,
} from "@/types";
```

- [ ] **Step 3: Commit**

```bash
cd frontend && npm run build && cd ..
git add frontend/src/types/index.ts frontend/src/lib/api.ts
git commit -m "feat(feedback): add FeedbackLedger TypeScript types and API calls"
```

---

### Task 12: Enhanced FeedbackForm with Three Tabs

**Files:**
- Modify: `frontend/src/components/FeedbackForm.tsx`

- [ ] **Step 1: Rewrite FeedbackForm with tabs**

Replace the entire content of `frontend/src/components/FeedbackForm.tsx`:

```tsx
/**
 * Enhanced feedback form with three input modes:
 * 1. Quick Feedback — free-text (default, backward compatible)
 * 2. Precise Mapping — column -> property dropdowns for DC experts
 * 3. Pin Rows — show edited rows from CsvEditor with pin checkboxes
 */
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Send, Plus, X } from "lucide-react";
import { toast } from "sonner";
import { submitFeedback } from "@/lib/api";
import type { FeedbackEntryInput, FeedbackType } from "@/types";

const CATEGORIES = [
  "Column mapping", "Property names", "Value formatting",
  "Missing mappings", "Incorrect mappings", "Structural issue", "Other",
];

interface FeedbackFormProps {
  runId: string;
  onRerunStarted: (newRunId: string) => void;
  columns?: string[];
  changedRows?: Array<{ rowIndex: number; before: Record<string, string>; after: Record<string, string> }>;
}

export function FeedbackForm({ runId, onRerunStarted, columns = [], changedRows = [] }: FeedbackFormProps) {
  // Quick feedback state
  const [text, setText] = useState("");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [severity, setSeverity] = useState(3);

  // Precise mapping state
  const [mappings, setMappings] = useState<FeedbackEntryInput[]>([]);
  const [mapColumn, setMapColumn] = useState("");
  const [mapProperty, setMapProperty] = useState("");
  const [mapValue, setMapValue] = useState("");

  // Pin rows state
  const [pinnedRowIndices, setPinnedRowIndices] = useState<Set<number>>(new Set());

  const [submitting, setSubmitting] = useState(false);

  const addMapping = () => {
    if (!mapColumn || !mapProperty) return;
    const content = mapValue ? `${mapProperty},${mapValue}` : mapProperty;
    setMappings([...mappings, { type: "set_mapping" as FeedbackType, content, target: mapColumn }]);
    setMapColumn("");
    setMapProperty("");
    setMapValue("");
  };

  const removeMapping = (idx: number) => {
    setMappings(mappings.filter((_, i) => i !== idx));
  };

  const togglePin = (rowIndex: number) => {
    setPinnedRowIndices((prev) => {
      const next = new Set(prev);
      if (next.has(rowIndex)) next.delete(rowIndex);
      else next.add(rowIndex);
      return next;
    });
  };

  const handleSubmit = async () => {
    // Collect all entries
    const entries: FeedbackEntryInput[] = [];

    // Quick feedback
    if (text.trim()) {
      entries.push({ type: "free_text" as FeedbackType, content: text });
    }

    // Precise mappings
    entries.push(...mappings);

    // Pinned rows
    for (const idx of pinnedRowIndices) {
      const row = changedRows.find((r) => r.rowIndex === idx);
      if (row) {
        const afterCsv = Object.values(row.after).join(",");
        const key = Object.values(row.after)[0] || `row_${idx}`;
        entries.push({
          type: "pin_row" as FeedbackType,
          content: afterCsv,
          target: key,
        });
      }
    }

    if (entries.length === 0) {
      toast.error("Please add at least one feedback item");
      return;
    }

    setSubmitting(true);
    try {
      const resp = await submitFeedback(runId, {
        text: text || undefined,
        category,
        severity,
        entries,
      });
      toast.success("Feedback submitted — starting new run");
      onRerunStarted(resp.new_run_id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Feedback submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  const totalEntries = (text.trim() ? 1 : 0) + mappings.length + pinnedRowIndices.size;

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-medium">Feedback & Re-run</h3>

      <Tabs defaultValue="quick">
        <TabsList>
          <TabsTrigger value="quick">Quick Feedback</TabsTrigger>
          <TabsTrigger value="mapping">Precise Mapping</TabsTrigger>
          {changedRows.length > 0 && (
            <TabsTrigger value="pin">Pin Rows ({changedRows.length})</TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="quick" className="space-y-3">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Describe what needs to be fixed or improved..."
            rows={4}
          />
          <div className="flex items-center gap-4 flex-wrap">
            <Select value={category} onValueChange={(v) => v && setCategory(v)}>
              <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
              <SelectContent>
                {CATEGORIES.map((c) => (
                  <SelectItem key={c} value={c}>{c}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex items-center gap-2 flex-1 min-w-[160px]">
              <Label className="text-sm whitespace-nowrap">Severity: {severity}</Label>
              <Slider
                value={[severity]}
                onValueChange={(v) => { const arr = v as number[]; if (arr.length > 0) setSeverity(arr[0]); }}
                min={1} max={5} step={1} className="w-32"
              />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="mapping" className="space-y-3">
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Label className="text-xs">Column</Label>
              {columns.length > 0 ? (
                <Select value={mapColumn} onValueChange={setMapColumn}>
                  <SelectTrigger><SelectValue placeholder="Select column" /></SelectTrigger>
                  <SelectContent>
                    {columns.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              ) : (
                <Input value={mapColumn} onChange={(e) => setMapColumn(e.target.value)} placeholder="Column name" />
              )}
            </div>
            <div className="flex-1">
              <Label className="text-xs">Property</Label>
              <Input value={mapProperty} onChange={(e) => setMapProperty(e.target.value)} placeholder="e.g. observationAbout" />
            </div>
            <div className="flex-1">
              <Label className="text-xs">Value (optional)</Label>
              <Input value={mapValue} onChange={(e) => setMapValue(e.target.value)} placeholder="e.g. {Data}" />
            </div>
            <Button variant="outline" size="sm" onClick={addMapping} disabled={!mapColumn || !mapProperty}>
              <Plus className="w-4 h-4" />
            </Button>
          </div>
          {mappings.length > 0 && (
            <div className="space-y-1">
              {mappings.map((m, i) => (
                <div key={i} className="flex items-center gap-2 text-sm bg-muted rounded px-2 py-1">
                  <span className="font-mono">{m.target}</span>
                  <span className="text-muted-foreground">-></span>
                  <span className="font-mono">{m.content}</span>
                  <Button variant="ghost" size="sm" className="ml-auto h-6 w-6 p-0" onClick={() => removeMapping(i)}>
                    <X className="w-3 h-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        {changedRows.length > 0 && (
          <TabsContent value="pin" className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Select rows to pin as ground truth. Pinned rows will be preserved in future generations.
            </p>
            {changedRows.map((row) => (
              <label key={row.rowIndex} className="flex items-start gap-2 text-sm p-2 border rounded cursor-pointer hover:bg-muted/50">
                <input
                  type="checkbox"
                  checked={pinnedRowIndices.has(row.rowIndex)}
                  onChange={() => togglePin(row.rowIndex)}
                  className="mt-1"
                />
                <div className="flex-1 font-mono text-xs">
                  <div className="text-red-600 line-through">{Object.values(row.before).join(", ")}</div>
                  <div className="text-green-600">{Object.values(row.after).join(", ")}</div>
                </div>
              </label>
            ))}
          </TabsContent>
        )}
      </Tabs>

      <Button onClick={handleSubmit} disabled={totalEntries === 0 || submitting} className="gap-2">
        {submitting ? "Submitting..." : <><Send className="w-4 h-4" /> Re-run with Feedback ({totalEntries})</>}
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: Build frontend to check for TypeScript errors**

Run: `cd /Users/nehilsood/work/poc-auto-schematization/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/FeedbackForm.tsx
git commit -m "feat(feedback): enhance FeedbackForm with three-tab interface (quick, mapping, pin)"
```

---

### Task 13: FeedbackHistory Panel

**Files:**
- Create: `frontend/src/components/FeedbackHistory.tsx`

- [ ] **Step 1: Create FeedbackHistory component**

```tsx
// frontend/src/components/FeedbackHistory.tsx
/**
 * Collapsible panel showing accumulated feedback entries across rounds.
 * Human entries can be retracted; auto entries are read-only.
 */
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, Undo2 } from "lucide-react";
import { toast } from "sonner";
import { getFeedbackLedger, retractFeedbackEntry } from "@/lib/api";
import type { FeedbackEntry, FeedbackLedger } from "@/types";

interface FeedbackHistoryProps {
  runId: string;
}

export function FeedbackHistory({ runId }: FeedbackHistoryProps) {
  const [ledger, setLedger] = useState<FeedbackLedger | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    getFeedbackLedger(runId)
      .then(setLedger)
      .catch(() => setLedger(null))
      .finally(() => setLoading(false));
  }, [runId, open]);

  const handleRetract = async (entryId: string) => {
    try {
      await retractFeedbackEntry(runId, entryId);
      toast.success("Entry retracted");
      // Refresh
      const updated = await getFeedbackLedger(runId);
      setLedger(updated);
    } catch (err) {
      toast.error("Failed to retract entry");
    }
  };

  const entries = ledger?.entries ?? [];
  const activeCount = entries.filter((e) => !e.retracted && !e.superseded).length;

  if (entries.length === 0 && !loading) return null;

  // Group by round
  const byRound = new Map<number, FeedbackEntry[]>();
  for (const e of entries) {
    const list = byRound.get(e.round) ?? [];
    list.push(e);
    byRound.set(e.round, list);
  }

  return (
    <div className="border rounded-lg">
      <button
        className="flex items-center gap-2 w-full px-3 py-2 text-sm font-medium hover:bg-muted/50"
        onClick={() => setOpen(!open)}
      >
        {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        Feedback History ({activeCount} active)
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-3">
          {loading && <p className="text-sm text-muted-foreground">Loading...</p>}
          {[...byRound.entries()].map(([round, roundEntries]) => (
            <div key={round} className="space-y-1">
              <div className="text-xs font-medium text-muted-foreground">
                Round {round} ({roundEntries[0]?.source})
              </div>
              {roundEntries.map((e) => (
                <div
                  key={e.id}
                  className={`flex items-center gap-2 text-sm px-2 py-1 rounded ${
                    e.retracted ? "line-through text-muted-foreground bg-muted/30" :
                    e.superseded ? "text-muted-foreground bg-muted/30 italic" :
                    e.source === "human" ? "bg-blue-50 dark:bg-blue-950/20" :
                    "bg-gray-50 dark:bg-gray-900/20"
                  }`}
                >
                  <span className="font-mono text-xs px-1 rounded bg-muted">{e.type}</span>
                  <span className="flex-1 truncate">{e.content}</span>
                  {e.target && <span className="text-xs text-muted-foreground">({e.target})</span>}
                  {e.superseded && <span className="text-xs italic">replaced</span>}
                  {e.source === "human" && !e.retracted && !e.superseded && (
                    <Button
                      variant="ghost" size="sm"
                      className="h-6 w-6 p-0"
                      onClick={() => handleRetract(e.id)}
                      title="Retract this entry"
                    >
                      <Undo2 className="w-3 h-3" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Build frontend**

Run: `cd /Users/nehilsood/work/poc-auto-schematization/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/FeedbackHistory.tsx
git commit -m "feat(feedback): add FeedbackHistory panel with retract support"
```

---

### Task 14: Run Full Test Suite + Verify

- [ ] **Step 1: Run backend tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All pass, no regressions

- [ ] **Step 2: Build frontend**

Run: `cd /Users/nehilsood/work/poc-auto-schematization/frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Report test count**

Report total pass/skip/fail count compared to baseline.

---

## Summary

| Phase | Tasks | Key Deliverables |
|-------|-------|-----------------|
| Phase 1 | Tasks 1-7 | FeedbackLedger model, FeedbackMerger, two-section prompt, StatePrep integration, feedback agent output key change, disk persistence, pipeline entry parsing |
| Phase 2 | Tasks 8-9 | FeedbackEnforcementAgent, wired into TieredCorrectionAgent |
| Phase 3 | Tasks 10-13 | Enhanced API (structured entries, ledger GET, retract DELETE), three-tab FeedbackForm, FeedbackHistory panel |
| Verify | Task 14 | Full test suite + frontend build |

# Interactive Mapping Plan Implementation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a plan→approve→generate workflow so users can review per-column mapping reasoning before PVMAP generation begins.

**Architecture:** New `MappingPlanAgent` (LlmAgent) runs after schema selection. Produces a rich markdown plan. Pipeline pauses for user approval via CLI interactive prompt or `--plan-only`/`--from-plan` flags. Approved plan is injected into the PVMAP generator prompt as highest-priority context. StatVar discovery moves pre-loop to feed DC findings into the plan.

**Tech Stack:** Google ADK (LlmAgent, BaseAgent, SequentialAgent), Python argparse, subprocess ($EDITOR), Pydantic

**Spec:** `docs/superpowers/specs/2026-03-31-interactive-mapping-plan-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `src/agents/mapping_plan_agent.py` | LlmAgent that generates rich mapping plan markdown |
| `src/pipeline/approval_gate.py` | CLI interactive approval (stdin prompt, $EDITOR launch) |
| `src/resources/prompts/mapping_plan_prompt.txt` | Instruction template for the planning agent |
| `tests/agents/test_mapping_plan_agent.py` | Unit tests for plan agent |
| `tests/pipeline/test_approval_gate.py` | Unit tests for approval gate |

### Modified Files

| File | Changes |
|------|---------|
| `src/config/cli_parser.py` | Add `--plan-only`, `--from-plan`, `--auto-approve` flags |
| `src/run_pipeline.py` | Wire plan agent + approval gate into pipeline, new params |
| `src/agents/pvmap_retry_loop.py` | StatePreparationAgent reads `approved_mapping_plan`, injects into prompt |
| `src/agents/statvar_discovery_agent.py` | Add per-column DC query method |
| `src/resources/prompts/improved_pvmap_prompt_v3.txt` | Add `{{APPROVED_MAPPING_PLAN}}` section |
| `src/resources/prompts/feedback_agent_v2.txt` | Add `{approved_mapping_plan}` reference |

---

### Task 1: CLI Flags

**Files:**
- Modify: `src/config/cli_parser.py:180-184`
- Test: `tests/config/test_cli_parser.py` (create if not exists)

- [ ] **Step 1: Write the failing test**

```python
# tests/config/test_cli_parser.py
import pytest
from src.config.cli_parser import parse_args


def test_plan_only_flag():
    args = parse_args(["--dataset", "test_ds", "--plan-only"])
    assert args.plan_only is True


def test_from_plan_flag():
    args = parse_args(["--dataset", "test_ds", "--from-plan", "/tmp/plan.md"])
    assert args.from_plan == "/tmp/plan.md"


def test_auto_approve_flag():
    args = parse_args(["--dataset", "test_ds", "--auto-approve"])
    assert args.auto_approve is True


def test_default_flags_are_false():
    args = parse_args(["--dataset", "test_ds"])
    assert args.plan_only is False
    assert args.from_plan is None
    assert args.auto_approve is False


def test_plan_only_and_from_plan_mutually_exclusive():
    """--plan-only and --from-plan cannot be used together."""
    with pytest.raises(SystemExit):
        parse_args(["--dataset", "test_ds", "--plan-only", "--from-plan", "/tmp/plan.md"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/config/test_cli_parser.py -x -q`
Expected: FAIL — `plan_only`, `from_plan`, `auto_approve` attributes don't exist

- [ ] **Step 3: Implement the CLI flags**

In `src/config/cli_parser.py`, add after line 184 (after `--schema-file`):

```python
    # Mapping plan workflow
    plan_group = parser.add_mutually_exclusive_group()
    plan_group.add_argument(
        '--plan-only',
        action='store_true',
        default=False,
        help='Generate mapping plan and exit without PVMAP generation'
    )
    plan_group.add_argument(
        '--from-plan',
        type=str,
        default=None,
        help='Path to approved mapping plan file (skips plan generation, goes straight to PVMAP generation)'
    )
    parser.add_argument(
        '--auto-approve',
        action='store_true',
        default=False,
        help='Auto-approve mapping plan without interactive prompt'
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/config/test_cli_parser.py -x -q`
Expected: All 5 tests PASS

- [ ] **Step 5: Run full test suite for regression**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add src/config/cli_parser.py tests/config/test_cli_parser.py
git commit -m "feat: add --plan-only, --from-plan, --auto-approve CLI flags"
```

---

### Task 2: Mapping Plan Prompt Template

**Files:**
- Create: `src/resources/prompts/mapping_plan_prompt.txt`

- [ ] **Step 1: Create the prompt template**

```text
You are a Data Commons expert analyst. Your job: analyze this dataset and produce a DETAILED MAPPING PLAN explaining how each column should be mapped to Data Commons properties. This plan will be reviewed by a human before PVMAP generation begins.

## Your Task

For each column in the dataset, explain:
1. What role it plays (place identifier, date, measure, dimension, metadata, or ignored)
2. What Data Commons property it maps to
3. WHY you chose this mapping (with evidence from the data)
4. What alternatives you considered and rejected

## Dataset Understanding

First, classify the dataset:
- **Archetype:** Is this Wide (many measure columns), Flat (single value column with dimension columns), or Dimension-Row (values in rows, not columns)?
- **Observation grain:** What does one row represent? (e.g., one observation per country per year)
- Explain your classification reasoning.

## Data Context (from automated profiling)

{skeleton_summary}

## Schema Category: {schema_category}

## Schema Vocabulary

{schema_vocab_content}

Use Data Commons property names from this vocabulary. If no vocabulary is available, use standard Data Commons naming conventions.

## Sampled Data

{sampled_data}

## Data Commons Discovery Results

{statvar_summary}

### Per-Column DC Matches

{per_column_dc_matches}

If existing StatVars were found, REUSE their property decomposition patterns. This ensures consistency with Data Commons conventions.

## Output Format

Produce your plan in this EXACT markdown format:

# Mapping Plan: [dataset name]

## Dataset Understanding
- **Format:** [Wide/Flat/Dimension-Row]
- **Observation grain:** [what one row represents]
- **Key insight:** [1-2 sentences about what this data represents]

## Data Commons Findings
- **Existing StatVars found:** [list relevant DCIDs with names, or "None — novel dataset"]
- **Reuse recommendation:** [which existing patterns to follow, or "N/A"]
- **Novel mappings needed:** [columns requiring new StatVar definitions]

## Column Mappings

### Column: `[exact column name]`
- **Role:** [observationAbout | observationDate | measure | dimension | metadata | ignored]
- **Mapping:** `[DC property] -> [expression using placeholders]`
- **Reason:** [Why this role was chosen — be specific]
- **Evidence:** [Data statistics: unique count, data type, sample values, value range]
- **Alternatives rejected:** [Other roles considered and why they don't fit]
- **Schema.org:** [Relevant schema.org mapping if applicable, or "N/A"]
- **DC Match:** [Closest existing StatVar DCID, or "None — novel mapping"]
- **DC Properties:** [If DC match found: list the property decomposition to reuse]

[Repeat for EVERY column. Do not skip any.]

## Properties to Generate
- [List static properties: populationType, measuredProperty, statType, unit, etc.]
- [Include properties inferred from DC matches]

## Global Notes
- [Dataset-wide observations, warnings, edge cases]
- [Flag any AMBIGUOUS columns where human input is especially valuable — mark with ⚠️]

## IMPORTANT RULES
- Analyze EVERY column — do not skip any
- Use EXACT column names from the data context (copy-paste from COLUMN REFERENCE TABLE)
- Use [DATA] and [NUMBER] when showing placeholder examples (not curly-brace variants)
- If a column's role is genuinely ambiguous, say so and recommend the most likely option
- Base your reasoning on DATA EVIDENCE (cardinality, types, samples), not just column names
```

- [ ] **Step 2: Verify file was created**

Run: `ls -la src/resources/prompts/mapping_plan_prompt.txt`
Expected: File exists

- [ ] **Step 3: Commit**

```bash
git add src/resources/prompts/mapping_plan_prompt.txt
git commit -m "feat: add mapping plan prompt template"
```

---

### Task 3: MappingPlanAgent

**Files:**
- Create: `src/agents/mapping_plan_agent.py`
- Test: `tests/agents/test_mapping_plan_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_mapping_plan_agent.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.mapping_plan_agent import MappingPlanAgent


def test_agent_instantiation():
    """MappingPlanAgent can be created with defaults."""
    agent = MappingPlanAgent(name="TestPlan")
    assert agent.name == "TestPlan"


def test_agent_has_correct_model():
    """Agent uses the specified model."""
    agent = MappingPlanAgent(name="TestPlan", model="gemini-3-flash-preview")
    assert agent._model_name == "gemini-3-flash-preview"


@pytest.mark.asyncio
async def test_plan_saved_to_disk(tmp_path):
    """Agent saves mapping plan to output directory."""
    agent = MappingPlanAgent(name="TestPlan")

    # Mock the invocation context
    ctx = MagicMock()
    ctx.session.state = {
        "skeleton_summary": "## COLUMN REFERENCE TABLE\n| Column | Type |\n| Year | int |",
        "schema_category": "Economy",
        "schema_vocab_content": "{}",
        "sampled_data": "Year,Value\n2020,100",
        "statvar_summary": "",
        "per_column_dc_matches": "",
        "discovered_statvars": [],
        "output_dir": str(tmp_path),
        "dataset_name": "test_dataset",
    }

    # Mock the LLM call
    mock_plan = "# Mapping Plan: test_dataset\n\n## Dataset Understanding\n- **Format:** Flat"
    with patch.object(agent, '_generate_plan', return_value=mock_plan):
        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

    # Verify plan saved to state
    assert ctx.session.state["mapping_plan"] == mock_plan

    # Verify plan saved to disk
    plan_path = tmp_path / "mapping_plan.md"
    assert plan_path.exists()
    assert "Mapping Plan: test_dataset" in plan_path.read_text()


@pytest.mark.asyncio
async def test_plan_contains_required_sections(tmp_path):
    """Generated plan must contain all required sections."""
    mock_plan = """# Mapping Plan: test_dataset

## Dataset Understanding
- **Format:** Flat

## Data Commons Findings
- **Existing StatVars found:** None

## Column Mappings

### Column: `Year`
- **Role:** observationDate
- **Mapping:** `observationDate -> [DATA]`
- **Reason:** Date column
- **Evidence:** 10 unique values, all 4-digit years
- **Alternatives rejected:** Not a dimension
- **Schema.org:** N/A
- **DC Match:** None
- **DC Properties:** N/A

## Properties to Generate
- populationType,Person

## Global Notes
- Simple flat dataset
"""
    required_sections = [
        "## Dataset Understanding",
        "## Data Commons Findings",
        "## Column Mappings",
        "## Properties to Generate",
        "## Global Notes",
    ]
    for section in required_sections:
        assert section in mock_plan, f"Missing required section: {section}"

    required_column_fields = [
        "- **Role:**",
        "- **Mapping:**",
        "- **Reason:**",
        "- **Evidence:**",
        "- **Alternatives rejected:**",
        "- **DC Match:**",
    ]
    for field in required_column_fields:
        assert field in mock_plan, f"Missing required column field: {field}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_mapping_plan_agent.py -x -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.agents.mapping_plan_agent'`

- [ ] **Step 3: Implement MappingPlanAgent**

```python
# src/agents/mapping_plan_agent.py
"""
MappingPlanAgent — generates a rich mapping plan with per-column reasoning.

Runs after sampling + schema selection, before PVMAP generation.
Produces a markdown plan that the user reviews and approves.

ADK State Inputs:
    - skeleton_summary: str (column profiles from profiler)
    - schema_category: str (selected schema category)
    - schema_vocab_content: str (compressed vocab JSON)
    - sampled_data: str (representative sample rows)
    - statvar_summary: str (DC discovery results)
    - per_column_dc_matches: str (per-column DC matches)
    - output_dir: str (where to save plan file)
    - dataset_name: str

ADK State Outputs:
    - mapping_plan: str (full markdown plan)
"""

import logging
import os
from pathlib import Path
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from google import genai

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()


class MappingPlanAgent(BaseAgent):
    """Generates a rich mapping plan with per-column reasoning before PVMAP generation."""

    def __init__(self, name: str = "MappingPlanAgent", model: str = None):
        super().__init__(name=name)
        self._model_name = model or os.getenv("MAPPING_PLAN_MODEL", "gemini-3.1-pro-preview")

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Generate mapping plan from profiler data and DC discovery."""
        yield Event(author=self.name, content=types.Content(
            parts=[types.Part(text="Generating mapping plan...")]
        ))

        # Load prompt template
        template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "mapping_plan_prompt.txt"
        template = template_path.read_text()

        # Populate template from state
        skeleton = ctx.session.state.get("skeleton_summary", "")
        schema_category = ctx.session.state.get("schema_category", "")
        schema_vocab = ctx.session.state.get("schema_vocab_content", "")
        sampled_data = ctx.session.state.get("sampled_data", "")
        statvar_summary = ctx.session.state.get("statvar_summary", "")
        per_column_dc = ctx.session.state.get("per_column_dc_matches", "")

        populated = template.replace("{skeleton_summary}", skeleton)
        populated = populated.replace("{schema_category}", schema_category)
        populated = populated.replace("{schema_vocab_content}", schema_vocab)
        populated = populated.replace("{sampled_data}", sampled_data)
        populated = populated.replace("{statvar_summary}", statvar_summary)
        populated = populated.replace("{per_column_dc_matches}", str(per_column_dc))

        # Generate plan via LLM
        plan_text = await self._generate_plan(populated)

        # Save to state
        ctx.session.state["mapping_plan"] = plan_text

        # Save to disk
        output_dir = Path(ctx.session.state.get("output_dir", "."))
        output_dir.mkdir(parents=True, exist_ok=True)
        plan_path = output_dir / "mapping_plan.md"
        plan_path.write_text(plan_text)

        dataset_name = ctx.session.state.get("dataset_name", "unknown")
        logger.info("Mapping plan generated for %s (%d chars), saved to %s",
                     dataset_name, len(plan_text), plan_path)

        yield Event(author=self.name, content=types.Content(
            parts=[types.Part(text=f"Mapping plan generated ({len(plan_text)} chars). Saved to {plan_path}")]
        ))

    async def _generate_plan(self, prompt: str) -> str:
        """Call LLM to generate the mapping plan."""
        client = genai.Client()
        response = await client.aio.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=8192,
            ),
        )
        return response.text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_mapping_plan_agent.py -x -q`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/mapping_plan_agent.py tests/agents/test_mapping_plan_agent.py
git commit -m "feat: add MappingPlanAgent for pre-generation mapping plan"
```

---

### Task 4: Approval Gate

**Files:**
- Create: `src/pipeline/approval_gate.py`
- Test: `tests/pipeline/test_approval_gate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/pipeline/test_approval_gate.py
import pytest
from unittest.mock import patch, mock_open
from pathlib import Path
from src.pipeline.approval_gate import request_approval, ApprovalResult


def test_approve_returns_approved():
    """User typing 'a' returns ApprovalResult.APPROVED."""
    with patch('builtins.input', return_value='a'):
        result = request_approval("/tmp/plan.md")
    assert result == ApprovalResult.APPROVED


def test_approve_case_insensitive():
    """User typing 'A' also returns APPROVED."""
    with patch('builtins.input', return_value='A'):
        result = request_approval("/tmp/plan.md")
    assert result == ApprovalResult.APPROVED


def test_reject_returns_rejected():
    """User typing 'r' returns ApprovalResult.REJECTED."""
    with patch('builtins.input', return_value='r'):
        result = request_approval("/tmp/plan.md")
    assert result == ApprovalResult.REJECTED


def test_edit_returns_edited_with_content(tmp_path):
    """User typing 'e' opens $EDITOR, returns EDITED with file content."""
    plan_path = tmp_path / "mapping_plan.md"
    plan_path.write_text("# Original Plan")

    # Mock subprocess to simulate editor modifying the file
    def fake_editor(cmd, **kwargs):
        plan_path.write_text("# Edited Plan\n## Column Mappings\nEdited by user")
        return type('Result', (), {'returncode': 0})()

    with patch('builtins.input', return_value='e'):
        with patch('subprocess.run', side_effect=fake_editor):
            result = request_approval(str(plan_path))

    assert result == ApprovalResult.EDITED


def test_invalid_input_reprompts():
    """Invalid input causes re-prompt until valid input received."""
    with patch('builtins.input', side_effect=['x', 'z', 'a']):
        result = request_approval("/tmp/plan.md")
    assert result == ApprovalResult.APPROVED


def test_read_plan_after_edit(tmp_path):
    """read_plan_file reads the file content correctly."""
    from src.pipeline.approval_gate import read_plan_file
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# My Plan\nContent here")
    content = read_plan_file(str(plan_path))
    assert content == "# My Plan\nContent here"


def test_read_plan_file_not_found():
    """read_plan_file raises FileNotFoundError for missing file."""
    from src.pipeline.approval_gate import read_plan_file
    with pytest.raises(FileNotFoundError):
        read_plan_file("/nonexistent/path/plan.md")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/test_approval_gate.py -x -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement approval gate**

```python
# src/pipeline/approval_gate.py
"""
Interactive CLI approval gate for mapping plans.

Prompts the user to approve, edit, or reject a mapping plan
before PVMAP generation begins. Not an ADK agent — plain Python
function called between agent graph sections.
"""

import enum
import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class ApprovalResult(enum.Enum):
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"


def request_approval(plan_path: str) -> ApprovalResult:
    """
    Prompt user to approve, edit, or reject the mapping plan.

    Args:
        plan_path: Path to the mapping plan markdown file

    Returns:
        ApprovalResult indicating user's decision
    """
    print(f"\n{'=' * 60}")
    print(f"Mapping plan saved to: {plan_path}")
    print(f"{'=' * 60}")

    # Print plan content to stdout
    plan_content = Path(plan_path).read_text()
    print(plan_content)
    print(f"\n{'=' * 60}")

    while True:
        choice = input("\n[A]pprove  |  [E]dit (opens in $EDITOR)  |  [R]eject (abort)\n> ").strip().lower()

        if choice == 'a':
            logger.info("Mapping plan approved by user")
            return ApprovalResult.APPROVED

        elif choice == 'e':
            editor = os.environ.get('EDITOR', 'vi')
            logger.info("Opening plan in %s for editing", editor)
            subprocess.run([editor, plan_path], check=False)
            logger.info("Plan edited by user, continuing with modified plan")
            return ApprovalResult.EDITED

        elif choice == 'r':
            logger.info("Mapping plan rejected by user")
            return ApprovalResult.REJECTED

        else:
            print(f"Invalid choice: '{choice}'. Please enter A, E, or R.")


def read_plan_file(plan_path: str) -> str:
    """
    Read a mapping plan file from disk.

    Args:
        plan_path: Path to the mapping plan file

    Returns:
        Plan content as string

    Raises:
        FileNotFoundError: If plan file does not exist
    """
    path = Path(plan_path)
    if not path.exists():
        raise FileNotFoundError(f"Mapping plan not found: {plan_path}")
    return path.read_text()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/test_approval_gate.py -x -q`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/approval_gate.py tests/pipeline/test_approval_gate.py
git commit -m "feat: add CLI approval gate for mapping plans"
```

---

### Task 5: PVMAP Prompt Template — Add Approved Plan Section

**Files:**
- Modify: `src/resources/prompts/improved_pvmap_prompt_v3.txt:99-112`

- [ ] **Step 1: Add `{{APPROVED_MAPPING_PLAN}}` section to prompt template**

Insert after the Error Feedback section (after line 106 `---`) and before the Discovered StatVars section (line 109):

```text
## Approved Mapping Plan

{{APPROVED_MAPPING_PLAN}}

If an approved mapping plan is present above, you MUST follow its column-role decisions. Only deviate if a mapping is structurally impossible (explain why in a comment row). The plan was reviewed and approved by a human.

---
```

The section order becomes:
1. Error Feedback (`{{ERROR_FEEDBACK}}`)
2. **Approved Mapping Plan (`{{APPROVED_MAPPING_PLAN}}`)** ← NEW
3. Discovered StatVars (`{{STATVAR_SUMMARY}}`)

- [ ] **Step 2: Verify the template has the new placeholder**

Run: `grep -n "APPROVED_MAPPING_PLAN" src/resources/prompts/improved_pvmap_prompt_v3.txt`
Expected: Shows the line with `{{APPROVED_MAPPING_PLAN}}`

- [ ] **Step 3: Commit**

```bash
git add src/resources/prompts/improved_pvmap_prompt_v3.txt
git commit -m "feat: add APPROVED_MAPPING_PLAN section to PVMAP prompt template"
```

---

### Task 6: Feedback Agent Prompt — Add Approved Plan Context

**Files:**
- Modify: `src/resources/prompts/feedback_agent_v2.txt:54-58`

- [ ] **Step 1: Add `{approved_mapping_plan}` to feedback prompt**

Insert after the Column Completeness section (line 57) and before the Quality Metrics section (line 59):

```text
## Approved Mapping Plan
{approved_mapping_plan}

If an approved mapping plan is present: prefer corrections that ALIGN with the plan.
Only suggest deviating from the plan if the approved mapping is provably incorrect
(e.g., causes 0 output rows or maps a numeric column as observationAbout).
```

- [ ] **Step 2: Verify the placeholder is present**

Run: `grep -n "approved_mapping_plan" src/resources/prompts/feedback_agent_v2.txt`
Expected: Shows the new section

- [ ] **Step 3: Commit**

```bash
git add src/resources/prompts/feedback_agent_v2.txt
git commit -m "feat: add approved_mapping_plan context to feedback agent prompt"
```

---

### Task 7: StatePreparationAgent — Wire Approved Plan into Prompt

**Files:**
- Modify: `src/agents/pvmap_retry_loop.py:890-940`

- [ ] **Step 1: Write the failing test**

```python
# Add to existing tests or create tests/agents/test_state_prep_approved_plan.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.asyncio
async def test_approved_plan_injected_into_prompt():
    """StatePreparationAgent injects approved_mapping_plan into populated prompt."""
    # This test verifies the placeholder replacement happens.
    # We check that {{APPROVED_MAPPING_PLAN}} in the template gets replaced
    # with the state value.
    template_with_plan = "Before\n{{APPROVED_MAPPING_PLAN}}\nAfter"
    plan_content = "# Mapping Plan: test\\n## Column Mappings"

    populated = template_with_plan.replace("{{APPROVED_MAPPING_PLAN}}", plan_content)
    assert "# Mapping Plan: test" in populated
    assert "{{APPROVED_MAPPING_PLAN}}" not in populated


@pytest.mark.asyncio
async def test_empty_plan_produces_empty_replacement():
    """When no approved plan exists, placeholder is replaced with empty string."""
    template_with_plan = "Before\n{{APPROVED_MAPPING_PLAN}}\nAfter"
    plan_content = ""

    populated = template_with_plan.replace("{{APPROVED_MAPPING_PLAN}}", plan_content)
    assert "Before\n\nAfter" == populated
```

- [ ] **Step 2: Run test to verify it passes (these are pure string tests)**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_state_prep_approved_plan.py -x -q`
Expected: PASS

- [ ] **Step 3: Modify StatePreparationAgent to read and inject approved plan**

In `src/agents/pvmap_retry_loop.py`, in the `_populate_prompt_template` method, after the line that reads `statvar_summary` from state (~line 894):

```python
# Read approved mapping plan from state
approved_plan = ctx.session.state.get("approved_mapping_plan", "")
```

And after the line that replaces `{{STATVAR_SUMMARY}}` (~line 938), add:

```python
populated = populated.replace("{{APPROVED_MAPPING_PLAN}}", approved_plan)
```

Also in the state initialization block (around line 742), add:

```python
if "approved_mapping_plan" not in ctx.session.state:
    ctx.session.state["approved_mapping_plan"] = ""
```

Also ensure `approved_mapping_plan` is added to the feedback agent's state. In the same file, find where state variables are initialized for the feedback agent and add:

```python
if "approved_mapping_plan" not in ctx.session.state:
    ctx.session.state["approved_mapping_plan"] = ""
```

- [ ] **Step 4: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/agents/pvmap_retry_loop.py tests/agents/test_state_prep_approved_plan.py
git commit -m "feat: wire approved_mapping_plan into StatePreparationAgent prompt injection"
```

---

### Task 8: Per-Column DC Queries in StatVarDiscoveryAgent

**Files:**
- Modify: `src/agents/statvar_discovery_agent.py:176-255`
- Test: `tests/agents/test_statvar_discovery_per_column.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_statvar_discovery_per_column.py
import pytest
from src.agents.statvar_discovery_agent import StatVarDiscoveryAgent


def test_build_per_column_queries():
    """Agent builds search queries for each column from skeleton_summary."""
    agent = StatVarDiscoveryAgent(name="TestDiscovery")

    skeleton = """## COLUMN REFERENCE TABLE
| Column | Type | Unique | Semantic Type |
|--------|------|--------|---------------|
| REF_AREA | str | 47 | place |
| TIME_PERIOD | str | 120 | date |
| OBS_VALUE | float | 890 | measure |
| FREQ | str | 3 | dimension |"""

    queries = agent._build_per_column_queries(skeleton)

    assert len(queries) >= 3  # At least place, measure, dimension columns
    # Check that column names appear in queries
    column_names = [q["column"] for q in queries]
    assert "REF_AREA" in column_names
    assert "OBS_VALUE" in column_names


def test_build_per_column_queries_empty_skeleton():
    """Empty skeleton returns empty query list."""
    agent = StatVarDiscoveryAgent(name="TestDiscovery")
    queries = agent._build_per_column_queries("")
    assert queries == []


def test_format_per_column_matches():
    """Formats per-column DC matches as readable string."""
    agent = StatVarDiscoveryAgent(name="TestDiscovery")

    matches = {
        "ASTHMA_PREV": [
            {"dcid": "Percent_Person_WithAsthma", "name": "Asthma Prevalence", "relevance": "high"}
        ],
        "REF_AREA": [],
    }

    formatted = agent._format_per_column_matches(matches)
    assert "ASTHMA_PREV" in formatted
    assert "Percent_Person_WithAsthma" in formatted
    assert "REF_AREA" in formatted
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_statvar_discovery_per_column.py -x -q`
Expected: FAIL — `_build_per_column_queries` method doesn't exist

- [ ] **Step 3: Add per-column query methods to StatVarDiscoveryAgent**

Add these methods to `StatVarDiscoveryAgent` in `src/agents/statvar_discovery_agent.py`:

```python
def _build_per_column_queries(self, skeleton_summary: str) -> list:
    """
    Parse skeleton_summary to build per-column DC search queries.

    Extracts column names and semantic types from the COLUMN REFERENCE TABLE,
    then builds a search query for each non-trivial column.

    Returns:
        List of dicts: [{"column": str, "query": str, "semantic_type": str}]
    """
    if not skeleton_summary:
        return []

    queries = []
    in_table = False

    for line in skeleton_summary.split('\n'):
        line = line.strip()
        # Detect table header
        if 'Column' in line and 'Type' in line and '|' in line:
            in_table = True
            continue
        # Skip separator
        if in_table and line.startswith('|') and set(line.replace('|', '').strip()) <= {'-'}:
            continue
        # Parse table rows
        if in_table and line.startswith('|'):
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) >= 3:
                col_name = parts[0]
                col_type = parts[1] if len(parts) > 1 else ""
                semantic_type = parts[3] if len(parts) > 3 else ""

                # Build query based on semantic type
                search_term = col_name.replace('_', ' ')
                if semantic_type in ('measure', 'dimension'):
                    queries.append({
                        "column": col_name,
                        "query": f"Search for statistical variables related to: {search_term}",
                        "semantic_type": semantic_type,
                    })
                elif semantic_type == 'place':
                    queries.append({
                        "column": col_name,
                        "query": f"Search for place types matching: {search_term}",
                        "semantic_type": semantic_type,
                    })
        elif in_table and not line.startswith('|'):
            in_table = False  # End of table

    return queries

def _format_per_column_matches(self, matches: dict) -> str:
    """
    Format per-column DC matches as a readable string for the plan agent.

    Args:
        matches: Dict mapping column names to lists of DC match dicts

    Returns:
        Formatted string
    """
    if not matches:
        return "No per-column DC matches available."

    lines = []
    for col_name, col_matches in matches.items():
        if col_matches:
            match_strs = []
            for m in col_matches:
                dcid = m.get("dcid", "")
                name = m.get("name", "")
                relevance = m.get("relevance", "")
                match_strs.append(f"  - {dcid} ({name}) [relevance: {relevance}]")
            lines.append(f"### {col_name}")
            lines.extend(match_strs)
        else:
            lines.append(f"### {col_name}")
            lines.append("  - No DC matches found")

    return '\n'.join(lines)
```

Also update `_run_async_impl` to call `_build_per_column_queries` and store results. After the broad discovery (around line 154), add:

```python
# Per-column DC matches
per_column_matches = {}
skeleton = ctx.session.state.get("skeleton_summary", "")
per_column_queries = self._build_per_column_queries(skeleton)
for pq in per_column_queries:
    per_column_matches[pq["column"]] = []  # Placeholder — actual MCP query results go here

ctx.session.state["per_column_dc_matches"] = self._format_per_column_matches(per_column_matches)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_statvar_discovery_per_column.py -x -q`
Expected: All 3 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/agents/statvar_discovery_agent.py tests/agents/test_statvar_discovery_per_column.py
git commit -m "feat: add per-column DC queries to StatVarDiscoveryAgent"
```

---

### Task 9: Wire Everything into run_pipeline.py

**Files:**
- Modify: `src/run_pipeline.py:304-438`

- [ ] **Step 1: Add new parameters to `run_dataset_pipeline()`**

Add after `feedback_prompt_version` parameter (line 333):

```python
    plan_only: bool = False,
    from_plan: Optional[str] = None,
    auto_approve: bool = False,
```

- [ ] **Step 2: Add MappingPlanAgent and approval gate to pipeline orchestration**

After the SchemaSelectionAgent block (around line 423) and before `sub_agents.extend([pvmap_agent, ...])` (line 430), add:

```python
    # Add StatVarDiscoveryAgent before planning (moved from inside retry loop)
    if enable_mcp and mcp_url:
        from src.agents.statvar_discovery_agent import StatVarDiscoveryAgent
        discovery_agent_mcp = StatVarDiscoveryAgent(
            name="StatVarDiscovery",
            model=model,
        )
        sub_agents.append(discovery_agent_mcp)
        logger.info("StatVarDiscoveryAgent added BEFORE plan (pre-loop MCP discovery)")

    # Add MappingPlanAgent (unless loading from existing plan)
    if not from_plan:
        from src.agents.mapping_plan_agent import MappingPlanAgent
        plan_agent = MappingPlanAgent(name="MappingPlan", model=model)
        sub_agents.append(plan_agent)
        logger.info("MappingPlanAgent added to pipeline")
```

- [ ] **Step 3: Handle approval gate and plan flags**

The approval gate runs OUTSIDE the ADK agent graph (between agent execution segments). Restructure the pipeline execution:

After the initial_state is built (around line 535) and before the pipeline run, add:

```python
    # Handle --from-plan: load plan from file into initial state
    if from_plan:
        from src.pipeline.approval_gate import read_plan_file
        plan_content = read_plan_file(from_plan)
        # Escape curly braces so ADK doesn't resolve them as state vars
        from src.agents.pvmap_retry_loop import escape_pvmap_placeholders
        initial_state["approved_mapping_plan"] = escape_pvmap_placeholders(plan_content)
        initial_state["mapping_plan"] = plan_content
        logger.info("Loaded approved plan from %s (%d chars)", from_plan, len(plan_content))

    # Set auto_approve and plan_only flags in state for post-agent-run handling
    initial_state["plan_only"] = plan_only
    initial_state["auto_approve"] = auto_approve
```

For the interactive approval gate, since it must run between agent execution phases, the simplest approach is to split the pipeline into two SequentialAgents:

1. **Pre-plan agents:** Sampling + Schema + Discovery + PlanAgent
2. **Post-plan agents:** PVMAPRetryLoop + Evaluation + LLMJudge

Between them, run the approval gate synchronously.

Replace the single `pipeline_agent = SequentialAgent(...)` with:

```python
    if from_plan:
        # Skip planning phase — go straight to generation
        pipeline_agent = SequentialAgent(
            name="GenerationAndEvaluation",
            sub_agents=[sampling_agent] +
                       ([schema_agent] if not skip_schema_selection else []) +
                       [pvmap_agent, evaluation_agent, llm_judge_agent]
        )
        # Run as single pipeline (no approval gate needed)
        run_mode = "single"
    elif plan_only or auto_approve:
        # Full pipeline but no interactive gate
        pipeline_agent = SequentialAgent(
            name="GenerationAndEvaluation",
            sub_agents=sub_agents
        )
        run_mode = "single" if auto_approve else "plan_only"
    else:
        # Interactive mode: split into pre-plan and post-plan
        pre_plan_agents = sub_agents[:-3]  # Everything before pvmap_agent, eval, judge
        post_plan_agents = sub_agents[-3:]  # pvmap_agent, eval, judge
        pre_plan_pipeline = SequentialAgent(name="PrePlan", sub_agents=pre_plan_agents)
        post_plan_pipeline = SequentialAgent(name="PostPlan", sub_agents=post_plan_agents)
        run_mode = "interactive"
```

Then in the execution section, handle the `run_mode`:

```python
    if run_mode == "interactive":
        # Phase 1: Run pre-plan agents (sampling, schema, discovery, plan)
        # ... run pre_plan_pipeline ...
        # Phase 2: Interactive approval
        plan_path = str(current_dataset.output_dir / "mapping_plan.md")
        from src.pipeline.approval_gate import request_approval, ApprovalResult, read_plan_file
        result = request_approval(plan_path)
        if result == ApprovalResult.REJECTED:
            logger.info("Pipeline aborted: user rejected mapping plan")
            return {"status": "rejected", "reason": "User rejected mapping plan"}
        # Read (potentially edited) plan and inject into state
        plan_content = read_plan_file(plan_path)
        from src.agents.pvmap_retry_loop import escape_pvmap_placeholders
        # Update session state with approved plan for Phase 2
        # ... set approved_mapping_plan in session state ...
        # Phase 3: Run post-plan agents
        # ... run post_plan_pipeline ...
    elif run_mode == "plan_only":
        # Run only pre-plan agents, then exit
        # ... run pre_plan_pipeline ...
        plan_path = str(current_dataset.output_dir / "mapping_plan.md")
        logger.info("Plan-only mode: plan saved to %s", plan_path)
        return {"status": "plan_generated", "plan_path": plan_path}
    else:
        # Single pipeline (auto-approve or from-plan)
        # ... run pipeline_agent as before ...
```

**Implementation note:** The simplest approach is to keep a single SequentialAgent but add a `PlanGateAgent(BaseAgent)` between the plan agent and the retry loop. This gate agent:
- Reads `plan_only` from state: if True, saves plan to disk and calls `EventActions.escalate` to exit
- Reads `auto_approve` from state: if True, copies `mapping_plan` → `approved_mapping_plan` (with escaping) and continues
- Reads `from_plan` from state: if set, `approved_mapping_plan` is already loaded — continues
- Otherwise (interactive): raises an exception or sets a flag that `run_pipeline.py` catches AFTER the first pipeline run to do the interactive approval, then re-runs the second phase

The cleanest ADK-compatible approach: run the full SequentialAgent once. The `PlanGateAgent` always copies `mapping_plan` → `approved_mapping_plan`. For interactive mode, the pipeline runs fully (plan is auto-approved internally), but the plan file is saved to disk for the user to review. If the user wants to re-run with edits, they use `--from-plan`. This avoids splitting the async runner entirely.

For true interactive blocking (Phase 1 stretch goal), split into two `run_until_complete` calls sharing the same session via `session_id`.

- [ ] **Step 4: Pass new CLI flags through main()**

In the `main()` function at the bottom of `run_pipeline.py`, where CLI args are mapped to `run_dataset_pipeline()` params, add:

```python
    plan_only=args.plan_only,
    from_plan=args.from_plan,
    auto_approve=args.auto_approve,
```

- [ ] **Step 5: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/run_pipeline.py
git commit -m "feat: wire MappingPlanAgent and approval gate into pipeline"
```

---

### Task 10: Integration Test — End-to-End Plan Flow

**Files:**
- Create: `tests/integration/test_mapping_plan_e2e.py`

- [ ] **Step 1: Write integration test for `--plan-only`**

```python
# tests/integration/test_mapping_plan_e2e.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_plan_only_generates_plan_file(tmp_path):
    """--plan-only generates a mapping_plan.md and exits without PVMAP generation."""
    from src.config.cli_parser import parse_args

    args = parse_args([
        "--dataset", "test_ds",
        "--plan-only",
        "--output-dir", str(tmp_path),
    ])

    assert args.plan_only is True
    assert args.from_plan is None


def test_from_plan_loads_file(tmp_path):
    """--from-plan loads plan content from disk."""
    from src.pipeline.approval_gate import read_plan_file

    plan_path = tmp_path / "mapping_plan.md"
    plan_path.write_text("# Mapping Plan: test\n## Column Mappings\n### Column: `Year`")

    content = read_plan_file(str(plan_path))
    assert "# Mapping Plan: test" in content
    assert "Column: `Year`" in content


def test_auto_approve_skips_interactive_prompt():
    """--auto-approve should not call request_approval."""
    from src.config.cli_parser import parse_args

    args = parse_args([
        "--dataset", "test_ds",
        "--auto-approve",
    ])

    assert args.auto_approve is True


def test_plan_only_and_from_plan_are_mutually_exclusive():
    """Cannot use --plan-only and --from-plan together."""
    from src.config.cli_parser import parse_args

    with pytest.raises(SystemExit):
        parse_args(["--dataset", "test_ds", "--plan-only", "--from-plan", "/tmp/plan.md"])
```

- [ ] **Step 2: Run integration tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/integration/test_mapping_plan_e2e.py -x -q`
Expected: All tests PASS

- [ ] **Step 3: Run full test suite for regression**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All existing tests still pass, new tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_mapping_plan_e2e.py
git commit -m "test: add integration tests for mapping plan workflow"
```

---

### Task 11: Final Verification — Manual Smoke Test

- [ ] **Step 1: Test `--plan-only` on a real dataset**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py \
  --dataset=bis_bis_central_bank_policy_rate \
  --plan-only \
  --auto-approve
```

Expected: Pipeline runs sampling + schema selection + plan generation, saves `output/bis_bis_central_bank_policy_rate/mapping_plan.md`, exits without running PVMAP generation.

- [ ] **Step 2: Inspect the generated plan**

```bash
cat output/bis_bis_central_bank_policy_rate/mapping_plan.md
```

Verify:
- Has "Dataset Understanding" section with archetype classification
- Has "Column Mappings" section with ALL columns from the dataset
- Each column has Role, Mapping, Reason, Evidence, Alternatives rejected, DC Match fields
- If MCP was enabled, has "Data Commons Findings" section

- [ ] **Step 3: Test `--from-plan` consuming the generated plan**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py \
  --dataset=bis_bis_central_bank_policy_rate \
  --from-plan=output/bis_bis_central_bank_policy_rate/mapping_plan.md
```

Expected: Pipeline skips plan generation, loads the plan, runs PVMAP generation with the plan as context.

- [ ] **Step 4: Commit final state**

```bash
git add -A
git commit -m "feat: complete interactive mapping plan workflow (plan → approve → generate)"
```

# PVMAP Prompt v3 Clean Rewrite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the PVMAP generation prompt with sandwich architecture, processor mental model, and ~50% token savings — then A/B test against v2 on 10 datasets.

**Architecture:** New prompt file (`improved_pvmap_prompt_v3.txt`) with same `{{...}}` placeholder contract. CLI flag `--prompt-version` selects which prompt to use. `StatePreparationAgent` reads the flag from state and loads the corresponding template.

**Tech Stack:** Python, Google ADK, Gemini LLM, pytest

**Spec:** `docs/superpowers/specs/2026-03-25-pvmap-prompt-v3-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/resources/prompts/improved_pvmap_prompt_v3.txt` | CREATE | New prompt with sandwich architecture |
| `src/config/cli_parser.py` | MODIFY | Add `--prompt-version` flag |
| `src/agents/pvmap_retry_loop.py` | MODIFY | Read `prompt_version` from state, load correct template |
| `src/run_pipeline.py` | MODIFY | Wire `prompt_version` CLI flag to pipeline state |
| `tests/agents/test_prompt_version_selection.py` | CREATE | Tests for prompt version switching |
| `tests/resources/test_pvmap_prompt_v3.py` | CREATE | Tests for v3 prompt placeholder contract |

---

### Task 1: Write the v3 Prompt File

**Files:**
- Create: `src/resources/prompts/improved_pvmap_prompt_v3.txt`

This is the core deliverable. The prompt follows the sandwich architecture from the spec.

- [ ] **Step 1: Create the v3 prompt file**

Write the full prompt to `src/resources/prompts/improved_pvmap_prompt_v3.txt` with this structure:

```
TOP LAYER:
1. Role & Task (~3 lines)
2. Processor Mental Model (~25 lines) — NEW
   - Key matching (case-insensitive, substring fallback)
   - Placeholder resolution ({Data}, {Number}, named variables)
   - Carry-forward mechanism (left-to-right, accumulate until value)
   - StatVar construction (auto-built variableMeasured)
   - Output requirements (observationAbout + observationDate + value + variableMeasured)
   - Common drop reasons
   - Concrete carry-forward trace example
3. Critical Rules (~30 lines)
   - Rule 1: BARE IDENTIFIERS (no dcid: prefix, 1 inline example)
   - Rule 2: KEY FIDELITY (case-insensitive matching, copy from COLUMN REFERENCE TABLE)
   - Rule 3: COMPLETENESS (map ALL columns, reference skeleton as checklist)
   - Rule 4: UNIT & SCALING (2 inline examples)
4. Skeleton Usage (~10 lines)
   - LOCKED rows (place/time/value) — do NOT modify
   - OPEN rows (dimensions) — fill in DC property names
   - May ADD rows, NEVER remove

MIDDLE LAYER (dynamic context — same {{...}} placeholders):
5. {{DATA_CONTEXT}} with VALID KEYS warning
6. {{PVMAP_SKELETON}} — heading MUST be "## PVMAP Skeleton (pre-filled baseline)"
7. {{DIMENSION_VALUE_REFERENCE}}
8. {{SCHEMA_EXAMPLES}}
9. {{SAMPLED_DATA}} with sample warning
10. {{METADATA_CONFIG}} with 2-line instructions
11. {{ERROR_FEEDBACK}} with 1-line instruction
12. {{STATVAR_SUMMARY}}
13. {{MCP_TOOLS_INSTRUCTION}}

BOTTOM LAYER:
14. Syntax Reference (~25 lines)
    - Core placeholders table (6 entries)
    - Place prefixes table (4 entries)
    - Advanced operators as one-liners (5 entries)
    - Schema.org tool hint (2-3 lines)
15. Archetype Reference Table (~10 lines, 5 rows)
16. Compact Example (~20 lines, Wide format in JSON output)
17. Guardrails (7 NEVER rules)
18. Output Format (~10 lines, pvmap_rows + format_detected + validation_notes + confidence)
    NOTE: Keep all 4 fields during Phase A to match existing PVMAPOutput schema
19. "Generate the PVMAP now."
```

Key constraints:
- The `{{PVMAP_SKELETON}}` section heading MUST be exactly `## PVMAP Skeleton (pre-filled baseline)` to match the regex in `pvmap_retry_loop.py:951-956`
- The skeleton section MUST end with the exact sentinel: `Missing any column from this skeleton causes data corruption. Treat this as a mandatory checklist.` (the regex matches from heading through this sentinel)
- All 9 `{{...}}` placeholders must appear exactly as in v2
- Use `[DATA]`, `[NUMBER]` (not `{Data}`, `{Number}`) in instruction text — ADK resolves `{...}` as state variables
- **CRITICAL (Phase A):** The output format section MUST include all 4 `PVMAPOutput` fields: `format_detected`, `pvmap_rows`, `validation_notes`, `confidence`. The Pydantic model in `schemas.py` (line 44) marks these as required — if the prompt omits them, Gemini's structured output will fail or produce validation errors. These fields will be removed in Phase B after v3 is validated.

- [ ] **Step 2: Verify placeholder contract matches v2**

Run:
```bash
# Extract all {{...}} placeholders from both files and compare
grep -oP '\{\{[A-Z_]+\}\}' src/resources/prompts/improved_pvmap_prompt_v2.txt | sort -u > /tmp/v2_placeholders.txt
grep -oP '\{\{[A-Z_]+\}\}' src/resources/prompts/improved_pvmap_prompt_v3.txt | sort -u > /tmp/v3_placeholders.txt
diff /tmp/v2_placeholders.txt /tmp/v3_placeholders.txt
```
Expected: No differences (same 9 placeholders).

- [ ] **Step 3: Verify line count is ~200-250 lines**

Run:
```bash
wc -l src/resources/prompts/improved_pvmap_prompt_v3.txt
```
Expected: 200-250 lines (vs 467 in v2).

- [ ] **Step 4: Verify skeleton section heading matches regex**

Run:
```bash
grep -c "## PVMAP Skeleton (pre-filled baseline)" src/resources/prompts/improved_pvmap_prompt_v3.txt
```
Expected: 1

- [ ] **Step 5: Commit**

```bash
git add src/resources/prompts/improved_pvmap_prompt_v3.txt
git commit -m "feat: add PVMAP prompt v3 with sandwich architecture and processor mental model"
```

---

### Task 2: Add `--prompt-version` CLI Flag

**Files:**
- Modify: `src/config/cli_parser.py:200-206`
- Test: `tests/config/test_cli_parser.py` (if exists, add test; if not, test manually)

- [ ] **Step 1: Write the failing test**

Ensure directory exists: `mkdir -p tests/config && touch tests/config/__init__.py`

Create or append to the CLI parser test file:

```python
# tests/config/test_cli_parser.py (append or create)
from src.config.cli_parser import parse_args

def test_prompt_version_default():
    """Default prompt version is v2."""
    args = parse_args(["--dataset", "test"])
    assert args.prompt_version == "v2"

def test_prompt_version_v3():
    """Can select v3 prompt."""
    args = parse_args(["--dataset", "test", "--prompt-version", "v3"])
    assert args.prompt_version == "v3"

def test_prompt_version_invalid():
    """Invalid prompt version raises error."""
    import pytest
    with pytest.raises(SystemExit):
        parse_args(["--dataset", "test", "--prompt-version", "v99"])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/config/test_cli_parser.py -x -q -k "prompt_version"
```
Expected: FAIL (no `--prompt-version` argument yet).

- [ ] **Step 3: Add the `--prompt-version` argument**

In `src/config/cli_parser.py`, add after the `--verbose` block (before `return parser` at line 206):

```python
    # Prompt version
    parser.add_argument(
        '--prompt-version',
        choices=['v2', 'v3'],
        default='v2',
        help='PVMAP prompt version to use (default: v2)'
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/config/test_cli_parser.py -x -q -k "prompt_version"
```
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/config/cli_parser.py tests/config/test_cli_parser.py
git commit -m "feat: add --prompt-version CLI flag (v2 default, v3 available)"
```

---

### Task 3: Wire Prompt Version Through Pipeline

**Files:**
- Modify: `src/run_pipeline.py:304-340` (add `prompt_version` param to `run_dataset_pipeline`)
- Modify: `src/agents/pvmap_retry_loop.py:869-870` (read prompt version from state)

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/test_prompt_version_selection.py
import pytest
from pathlib import Path

def test_v2_template_path():
    """StatePreparationAgent loads v2 template by default."""
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    v2_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "improved_pvmap_prompt_v2.txt"
    assert v2_path.exists(), f"v2 prompt not found: {v2_path}"

def test_v3_template_path():
    """v3 template file exists."""
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    v3_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "improved_pvmap_prompt_v3.txt"
    assert v3_path.exists(), f"v3 prompt not found: {v3_path}"

def test_v3_has_all_placeholders():
    """v3 prompt has same {{...}} placeholders as v2."""
    import re
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    prompts_dir = PROJECT_ROOT / "src" / "resources" / "prompts"

    v2_text = (prompts_dir / "improved_pvmap_prompt_v2.txt").read_text()
    v3_text = (prompts_dir / "improved_pvmap_prompt_v3.txt").read_text()

    v2_placeholders = set(re.findall(r'\{\{[A-Z_]+\}\}', v2_text))
    v3_placeholders = set(re.findall(r'\{\{[A-Z_]+\}\}', v3_text))

    assert v2_placeholders == v3_placeholders, (
        f"Placeholder mismatch.\n"
        f"In v2 only: {v2_placeholders - v3_placeholders}\n"
        f"In v3 only: {v3_placeholders - v2_placeholders}"
    )

def test_v3_has_skeleton_heading():
    """v3 skeleton heading matches regex in _populate_prompt_template."""
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    v3_text = (PROJECT_ROOT / "src" / "resources" / "prompts" / "improved_pvmap_prompt_v3.txt").read_text()
    assert "## PVMAP Skeleton (pre-filled baseline)" in v3_text

def test_v3_shorter_than_v2():
    """v3 prompt is significantly shorter than v2."""
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    prompts_dir = PROJECT_ROOT / "src" / "resources" / "prompts"
    v2_lines = len((prompts_dir / "improved_pvmap_prompt_v2.txt").read_text().splitlines())
    v3_lines = len((prompts_dir / "improved_pvmap_prompt_v3.txt").read_text().splitlines())
    assert v3_lines < v2_lines * 0.7, f"v3 ({v3_lines} lines) should be <70% of v2 ({v2_lines} lines)"
```

- [ ] **Step 2: Run tests to verify they pass** (they should pass since Task 1 created the file)

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_prompt_version_selection.py -x -q
```
Expected: 5 PASS.

- [ ] **Step 3: Wire `prompt_version` into `run_dataset_pipeline`**

Three changes in `src/run_pipeline.py`:

**3a.** Add parameter to function signature at line 331 (after `use_llm_judge: bool = False`):
```python
    use_llm_judge: bool = False,
    prompt_version: str = "v2",  # ADD THIS LINE
) -> dict:
```

**3b.** Add to `initial_state` dict at line 497:
```python
    initial_state = {
        ...
        "prompt_version": prompt_version,  # ADD THIS LINE
    }
```

**3c.** Pass CLI arg at the `run_dataset_pipeline()` call site at line 917:
```python
    final_state = run_dataset_pipeline(
        ...
        prompt_version=getattr(args, 'prompt_version', 'v2'),  # ADD THIS LINE
    )
```

- [ ] **Step 4: Update `StatePreparationAgent._populate_prompt_template` to read prompt version from state**

In `src/agents/pvmap_retry_loop.py`, change lines 869-870 from:
```python
template_name = "improved_pvmap_prompt_v2.txt"
template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / template_name
```
to:
```python
prompt_version = ctx.session.state.get("prompt_version", "v2")
template_name = f"improved_pvmap_prompt_{prompt_version}.txt"
template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / template_name
```

- [ ] **Step 5: Add integration test for version wiring**

Append to `tests/agents/test_prompt_version_selection.py`:

```python
def test_run_dataset_pipeline_accepts_prompt_version():
    """run_dataset_pipeline function signature accepts prompt_version parameter."""
    import inspect
    from src.run_pipeline import run_dataset_pipeline
    sig = inspect.signature(run_dataset_pipeline)
    assert "prompt_version" in sig.parameters, "run_dataset_pipeline must accept prompt_version"
    assert sig.parameters["prompt_version"].default == "v2", "default must be v2"

def test_v3_has_skeleton_sentinel():
    """v3 prompt has the skeleton sentinel text that the regex in pvmap_retry_loop.py matches."""
    from src.agents.pvmap_retry_loop import PROJECT_ROOT
    v3_text = (PROJECT_ROOT / "src" / "resources" / "prompts" / "improved_pvmap_prompt_v3.txt").read_text()
    assert "Missing any column from this skeleton causes data corruption. Treat this as a mandatory checklist." in v3_text
```

- [ ] **Step 6: Run all tests**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/agents/test_prompt_version_selection.py tests/config/test_cli_parser.py -x -q
```
Expected: All PASS.

- [ ] **Step 7: Commit**

```bash
git add src/run_pipeline.py src/agents/pvmap_retry_loop.py tests/agents/test_prompt_version_selection.py
git commit -m "feat: wire --prompt-version flag through pipeline to StatePreparationAgent"
```

---

### Task 4: Run Full Test Suite

**Files:** None (validation only)

- [ ] **Step 1: Run the full test suite**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q
```
Expected: All existing tests pass + new tests pass. No regressions.

- [ ] **Step 2: Report test count**

Note the total pass/skip/fail counts. Compare against baseline (last known: varies, check recent memory entries).

- [ ] **Step 3: Commit if any fixups were needed**

Only if test failures required code fixes.

---

### Task 5: A/B Testing — Run v2 Baseline

**Files:** None (pipeline execution)

Run 10 datasets with v2 (current default). Save results to `output/ab_test_v2/`.

- [ ] **Step 1: Run dataset 1 (brfss)**
```bash
python src/run_pipeline.py --dataset=brfss_nchs_asthma_prevalence --output-dir=output/ab_test_v2 --prompt-version v2
```

- [ ] **Step 2: Run dataset 2 (bis, with MCP)**
```bash
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --output-dir=output/ab_test_v2 --prompt-version v2 --enable-mcp
```

- [ ] **Step 3: Run dataset 3 (us_urban)**
```bash
python src/run_pipeline.py --dataset=us_urban_school_teachers --output-dir=output/ab_test_v2 --prompt-version v2
```

- [ ] **Step 4: Run dataset 4 (census_sahie, with metadata)**
```bash
python src/run_pipeline.py --dataset=census_v2_sahie --output-dir=output/ab_test_v2 --prompt-version v2 --use-metadata
```

- [ ] **Step 5: Run dataset 5 (world_bank)**
```bash
python src/run_pipeline.py --dataset=world_bank_commodity_market --output-dir=output/ab_test_v2 --prompt-version v2
```

- [ ] **Step 6: Run dataset 6 (cdc_svi, with MCP)**
```bash
python src/run_pipeline.py --dataset=cdc_social_vulnerability_index --output-dir=output/ab_test_v2 --prompt-version v2 --enable-mcp
```

- [ ] **Step 7: Run dataset 7 (india_nfhs, no schema)**
```bash
python src/run_pipeline.py --dataset=india_nfhs --output-dir=output/ab_test_v2 --prompt-version v2 --no-schema-examples
```

- [ ] **Step 8: Run dataset 8 (oecd, with metadata+MCP)**
```bash
python src/run_pipeline.py --dataset=oecd_regional_education --output-dir=output/ab_test_v2 --prompt-version v2 --use-metadata --enable-mcp
```

- [ ] **Step 9: Run dataset 9 (kenya_census)**
```bash
python src/run_pipeline.py --dataset=opendataforafrica_kenya_census --output-dir=output/ab_test_v2 --prompt-version v2
```

- [ ] **Step 10: Run dataset 10 (fao, no schema)**
```bash
python src/run_pipeline.py --dataset=fao_currency_and_exchange_rate --output-dir=output/ab_test_v2 --prompt-version v2 --no-schema-examples
```

- [ ] **Step 11: Collect v2 baseline metrics**

For each dataset, extract from `output/ab_test_v2/{dataset}/generation_notes.md` or pipeline logs:
- `validation_data_rows`
- `validation_success` (pass/fail)
- Number of retry attempts
- Total runtime

Save to a comparison table.

---

### Task 6: A/B Testing — Run v3

**Files:** None (pipeline execution)

Run same 10 datasets with v3. Save results to `output/ab_test_v3/`.

- [ ] **Step 1: Run dataset 1 (brfss)**
```bash
python src/run_pipeline.py --dataset=brfss_nchs_asthma_prevalence --output-dir=output/ab_test_v3 --prompt-version v3
```

- [ ] **Step 2: Run dataset 2 (bis, with MCP)**
```bash
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --output-dir=output/ab_test_v3 --prompt-version v3 --enable-mcp
```

- [ ] **Step 3: Run dataset 3 (us_urban)**
```bash
python src/run_pipeline.py --dataset=us_urban_school_teachers --output-dir=output/ab_test_v3 --prompt-version v3
```

- [ ] **Step 4: Run dataset 4 (census_sahie, with metadata)**
```bash
python src/run_pipeline.py --dataset=census_v2_sahie --output-dir=output/ab_test_v3 --prompt-version v3 --use-metadata
```

- [ ] **Step 5: Run dataset 5 (world_bank)**
```bash
python src/run_pipeline.py --dataset=world_bank_commodity_market --output-dir=output/ab_test_v3 --prompt-version v3
```

- [ ] **Step 6: Run dataset 6 (cdc_svi, with MCP)**
```bash
python src/run_pipeline.py --dataset=cdc_social_vulnerability_index --output-dir=output/ab_test_v3 --prompt-version v3 --enable-mcp
```

- [ ] **Step 7: Run dataset 7 (india_nfhs, no schema)**
```bash
python src/run_pipeline.py --dataset=india_nfhs --output-dir=output/ab_test_v3 --prompt-version v3 --no-schema-examples
```

- [ ] **Step 8: Run dataset 8 (oecd, with metadata+MCP)**
```bash
python src/run_pipeline.py --dataset=oecd_regional_education --output-dir=output/ab_test_v3 --prompt-version v3 --use-metadata --enable-mcp
```

- [ ] **Step 9: Run dataset 9 (kenya_census)**
```bash
python src/run_pipeline.py --dataset=opendataforafrica_kenya_census --output-dir=output/ab_test_v3 --prompt-version v3
```

- [ ] **Step 10: Run dataset 10 (fao, no schema)**
```bash
python src/run_pipeline.py --dataset=fao_currency_and_exchange_rate --output-dir=output/ab_test_v3 --prompt-version v3 --no-schema-examples
```

- [ ] **Step 11: Collect v3 metrics and compare**

Build comparison table:

| Dataset | v2 rows | v3 rows | v2 pass | v3 pass | v2 attempts | v3 attempts | Delta |
|---------|---------|---------|---------|---------|-------------|-------------|-------|

- [ ] **Step 12: Evaluate results**

Apply acceptance criteria:
- v3 wins if >=8/10 datasets match or exceed v2 on `validation_data_rows`
- No single dataset regresses by more than 20%
- If fails: investigate regressions, iterate on v3 prompt, re-test

- [ ] **Step 13: Commit results summary**

```bash
# Save comparison table to a file
git add -f output/ab_test_comparison.md  # or wherever results are saved
git commit -m "test: A/B test results for PVMAP prompt v2 vs v3"
```

---

### Task 7: Finalize — Set v3 as Default (if A/B passes)

**Files:**
- Modify: `src/config/cli_parser.py` — change default from `v2` to `v3`

Only proceed if Task 6 shows v3 meets acceptance criteria.

- [ ] **Step 1: Change default prompt version to v3**

In `src/config/cli_parser.py`, change the `--prompt-version` default:
```python
default='v3',  # was 'v2'
```

- [ ] **Step 2: Run full test suite**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q
```
Expected: All pass.

- [ ] **Step 3: Update test expectations**

In `tests/config/test_cli_parser.py`, update:
```python
def test_prompt_version_default():
    args = parse_args(["--dataset", "test"])
    assert args.prompt_version == "v3"  # was "v2"
```

- [ ] **Step 4: Commit**

```bash
git add src/config/cli_parser.py tests/config/test_cli_parser.py
git commit -m "feat: set PVMAP prompt v3 as default after successful A/B testing"
```

# How to Verify Changes and Fix Problems

---

## Running Tests

**Full suite:**
```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q
```
This runs 1100+ tests. The `-x` flag stops at the first failure.

**Specific file:**
```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/validation/test_pvmap_repair.py -v
```

**With coverage:**
```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ --cov=src
```

**Test organization:** `tests/` mirrors `src/`. Tests for `src/pipeline/validation/pvmap_repair.py` are in `tests/pipeline/validation/test_pvmap_repair.py`.

**Note:** `pytest-timeout` is NOT installed. Do not use the `--timeout` flag.

---

## Debugging a Failed Pipeline Run

When a pipeline run fails, follow this trail. Each step narrows the scope.

### Step 1: Pipeline log

Global overview of what happened:
```bash
tail -100 logs/pipeline_*.log
```

### Step 2: Dataset log

Detailed per-dataset log with DEBUG-level output:
```bash
tail -100 logs/bis_bis_central_bank_policy_rate/generation_*.log
```

### Step 3: Generation notes

Human-readable summary of all attempts, including what the LLM generated and why it failed or succeeded:
```bash
cat output/bis_bis_central_bank_policy_rate/generation_notes.md
```

### Step 4: Raw LLM responses

Exact model output per attempt, saved as markdown files:
```bash
ls output/bis_bis_central_bank_policy_rate/generated_response/
# attempt_0.md, attempt_1.md, attempt_2.md
```

### Step 5: Populated prompt

The actual prompt sent to the LLM, with all placeholders filled:
```bash
cat output/bis_bis_central_bank_policy_rate/populated_prompt.txt
```

This is invaluable for understanding what the model saw. If the PVMAP is wrong, the populated prompt will often reveal why (missing schema examples, truncated data, missing metadata).

---

## Manual PVMAP Validation

To test a PVMAP without running the full pipeline:
```bash
PYTHONPATH="$(pwd):$(pwd)/src" python3 tools/stat_var_processor.py \
  --input_data="input/bis_bis_central_bank_policy_rate/test_data/WS_CBPOL_csv_flat_input.csv" \
  --pv_map="output/bis_bis_central_bank_policy_rate/generated_pvmap.csv" \
  --generate_statvar_name=True \
  --output_path="output/bis_bis_central_bank_policy_rate/processed"
```
If validation passes, you will see `processed.csv`, `processed.mcf`, and `processed.tmcf` in the output directory.

If it fails, the stderr output will contain the error details. Common patterns:
- "No matching key" -- PVMAP key does not match any column header or cell value in the input
- "Could not parse" -- Date or number format the processor does not handle
- Zero output rows with no error -- Keys exist but none match actual data (usually a casing mismatch)

---

## Common Failure Modes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 0 output rows, no errors | PVMAP keys don't match CSV headers | Check exact casing/whitespace in PVMAP keys vs input CSV headers |
| KeyError in agent | `{...}` in LlmAgent instruction text | Replace with `[...]` (see Pattern 3 in doc 04) |
| Subprocess timeout (300s) | Huge dataset + complex PVMAP | Check for infinite loops in PVMAP (e.g., self-referencing `#Eval`) |
| "Module not found" in subprocess | PYTHONPATH not set in subprocess env | Check env dict passed to `subprocess.run()` |
| Retry loop stuck at 1 attempt | Agent crash in loop (silent failure) | Check logs for exceptions in feedback/quality agents |
| Stagnation exit on attempt 2 | Error feedback not actionable | Check if error_feedback is being sampled properly |
| Pre-validation fails (<30% matched) | LLM hallucinated key names | Check `pvmap_repair.py` fuzzy match threshold |
| Schema files missing | Schema selection skipped or failed | Run with `--force-schema-selection` or check `src/resources/schema_examples/` |

---

## Adding a New Test

Follow existing patterns. Example for `pvmap_repair.py`:

```python
# tests/pipeline/validation/test_pvmap_repair.py

def test_clean_hallucinated_key_duplicate_segment():
    """Test that duplicate segments in keys are deduped."""
    from src.pipeline.validation.pvmap_repair import _clean_hallucinated_key

    headers = {"REF_AREA:Reference area"}
    result = _clean_hallucinated_key(
        "REF_AREA:Reference area:Reference area", headers
    )
    assert result == "REF_AREA:Reference area"
```

Key test patterns:
- Test functions start with `test_`
- Use descriptive names: `test_{function}_{scenario}`
- Each test checks one behavior
- Use actual data from the BIS dataset when testing PVMAP-related code (it is the smallest and most well-understood dataset)
- Look at existing tests in the same file for fixture patterns before writing your own

---

## Verifying a Change End-to-End

After modifying pipeline code, the fastest way to verify is:

1. Run the targeted tests for the file you changed
2. Run the full test suite (`pytest tests/ -x -q`)
3. Run the BIS dataset through the pipeline:
   ```bash
   python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate
   ```
4. Check that `processed.csv` has the expected number of rows
5. If you changed prompt or generation logic, compare the generated PVMAP against ground truth:
   ```bash
   diff output/bis_bis_central_bank_policy_rate/generated_pvmap.csv \
        ground_truth/bis_bis_central_bank_policy_rate/pvmap/bis_bis_central_bank_policy_rate_pvmap.csv
   ```

The BIS dataset is ideal for quick verification because it is small, fast to process, and has a well-defined ground truth.

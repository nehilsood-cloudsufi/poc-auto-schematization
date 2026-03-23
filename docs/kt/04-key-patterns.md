# Patterns You Must Understand

These are the non-obvious patterns that take days to discover independently. Understanding them will save you significant debugging time.

---

## Pattern 1: Subprocess Validation

`stat_var_processor.py` is called via `subprocess.run()`, NOT imported as a Python module.

**Why:** Isolation (it has its own imports), timeout control (5 minutes), and PYTHONPATH management.

**The exact command:**
```python
cmd = [
    sys.executable,
    'tools/stat_var_processor.py',
    f'--input_data={input_file}',       # FULL dataset, NOT sampled
    f'--pv_map={dataset.pvmap_path}',   # Generated PVMAP
    f'--config_file={metadata_file}',   # Optional metadata
    '--generate_statvar_name=True',
    f'--output_path={output_dir}/processed'
]
result = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                        env={...PYTHONPATH...})
```

**Critical:** Validation MUST run on the full original dataset, not the sampled data. The sample might pass while the full dataset fails (e.g., edge case country names, date formats).

**Success criteria:** `result.returncode == 0` AND the output CSV has data rows (not just a header).

---

## Pattern 2: Error Sampling

LLM error logs can be 10KB+ (thousands of lines). Feeding all of this back would blow the token budget.

**Solution:** Sample the error output:
- Last 50 lines of error log (most recent context)
- Plus 10 random windows of 5 lines each (diverse error coverage)
- Total: ~300 lines max

This happens in `extract_log_samples()`. The sampled error becomes the `error_feedback` state variable for the next retry iteration.

---

## Pattern 3: ADK `{...}` Escaping (Critical Bug Story)

**The bug (2026-02-11):** The retry loop only ran 1 iteration instead of 3. The `ConditionalFeedbackAgent` crashed silently.

**Root cause:** The agent's instruction text contained `{Number}` (a PVMAP placeholder example). ADK's `LlmAgent` resolves ALL `{...}` patterns in instruction strings as state variable references. It tried to find `ctx.session.state["Number"]` -> `KeyError` -> agent crash -> loop thread dies.

**The fix:** Use `[NUMBER]` and `[DATA]` instead of `{Number}` and `{Data}` in any LlmAgent instruction text.

**Rule:** NEVER use `{...}` in LlmAgent instruction strings unless it is a real state variable reference. This applies to the instruction text itself, not to state variable values (which are escaped by `escape_pvmap_placeholders()`).

**Where this matters:**
- `src/agents/feedback_agent.py` -- instruction text
- `src/agents/pvmap_generator_agent.py` -- instruction text
- `src/agents/quality_evaluation_agent.py` -- instruction text
- Any new agent you create

---

## Pattern 4: Token Budget Compaction

The skeleton_summary can be huge (49KB for India NFHS dataset). The PVMAP prompt has a ~37.5K character budget.

**Two compaction levels:**
1. **Generator compaction** (`_compact_skeleton_for_generator()`) -- Light touch. Only triggers when skeleton > 40KB. Trims sample values.
2. **Feedback compaction** (`_compact_skeleton_for_feedback()`) -- Aggressive. Drops sections 6, 7, 9 entirely (generation-only content). Compacts sections 1.5 and 4. Achieves 60-70% reduction.

**Why different levels?** The generator needs full context to create the PVMAP. The feedback agent only needs diagnostic context to explain what went wrong.

Similarly, `_compact_vocab_for_feedback()` strips examples from schema vocabulary (50-75% reduction).

---

## Pattern 5: Schema.org Vocabulary Fallback Chain

Schema vocabulary (the valid DC property names) can come from multiple sources:

```
State (schema_vocab_content)
  -> Resource dir JSON (src/resources/schema_examples/{category}/schema_vocab.json)
    -> .txt file on disk (legacy)
```

The `property_vocabulary` (enum values for validation) is cached in session state by `StatePreparationAgent`. If `--skip-schema-selection` is used, `schema_category` is never set, and the caching block handles this gracefully (empty string check).

---

## Pattern 6: Environment Loading Order

Order matters. Getting this wrong causes subtle import failures:

```
1. Load .env file           <- API keys
2. Set BASE_DIR constant    <- Project root
3. Parse PYTHONPATH          <- Import resolution
4. Extend sys.path          <- Make imports work
5. Import application code  <- NOW it is safe
```

This sequence lives at the top of `src/run_pipeline.py`. If you rearrange it -- for example, importing application code before loading `.env` -- the Gemini client will initialize without an API key and fail at generation time, not at import time. The error message will not point you back to the load order.

Pipeline phases also have ordering dependencies:
```
Sampling BEFORE Schema Selection BEFORE PVMAP Generation
```
Each phase's output feeds the next phase's input. The sampled data feeds the schema selector's data preview. The selected schema files feed the PVMAP prompt's `{{SCHEMA_EXAMPLES}}` placeholder.

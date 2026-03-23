# Hands-On Exercises

8 exercises, progressive difficulty. Each builds on the previous.

---

## Exercise 1: Setup and First Run

**Goal:** Verify environment works and understand output structure.

1. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   export PYTHONPATH="$(pwd):$(pwd)/src"
   ```
2. Run the BIS dataset:
   ```bash
   python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate
   ```
3. Examine the output directory:
   ```bash
   ls -la output/bis_bis_central_bank_policy_rate/
   ```
4. Answer: What files were created? What is in `generated_pvmap.csv`? How many rows does `processed.csv` have?

**Expected:** You should see `generated_pvmap.csv`, `generation_notes.md`, `populated_prompt.txt`, `processed.csv`, `processed.mcf`, `processed.tmcf`, `generated_response/`, and optionally `eval_results/`.

---

## Exercise 2: Trace a PVMAP

**Goal:** Understand how a PVMAP transforms raw data.

Given this raw CSV row:
```
FREQ       = M: Monthly
REF_AREA   = AR: Argentina
TIME_PERIOD = 1993-04
OBS_VALUE  = 0.63
UNIT_MEASURE = 368: Per cent per year
```

And this PVMAP:
```csv
key,,,,,,
BIS:WS_CBPOL(1.0)...,measuredProperty,interestRate,populationType,FinancialInstrument,...
M: Monthly,measurementQualifier,Monthly,observationPeriod,P1M
REF_AREA:Reference area,observationAbout,{Data}
TIME_PERIOD:Time period or range,observationDate,{Data}
OBS_VALUE:Observation Value,value,{Number}
368: Per cent per year,unit,PercentPerAnnum
```

1. For each PVMAP row, identify which input column or value it matches
2. Write out the StatVar properties that would be generated
3. Write out the StatVarObservation (observationAbout, observationDate, variableMeasured, value)
4. Now run `stat_var_processor.py` manually and compare your prediction:
   ```bash
   PYTHONPATH="$(pwd):$(pwd)/src" python3 tools/stat_var_processor.py \
     --input_data="input/bis_bis_central_bank_policy_rate/test_data/WS_CBPOL_csv_flat_input.csv" \
     --pv_map="ground_truth/bis_bis_central_bank_policy_rate/pvmap/bis_bis_central_bank_policy_rate_pvmap.csv" \
     --generate_statvar_name=True \
     --output_path="/tmp/exercise2_output"
   ```

---

## Exercise 3: Read the Retry Loop

**Goal:** Understand the core pipeline mechanism.

1. Open `src/agents/pvmap_retry_loop.py`
2. Find the `create_pvmap_retry_loop()` function
3. List all agents in order. Write a one-sentence description for each.
4. Find every place that uses `EventActions.escalate` -- what triggers each escalation?
5. Answer: What is `max_retries`? How many total attempts does that allow?

**Hint:** The LoopAgent runs its sub-agents sequentially. An escalation from any sub-agent causes the loop to exit early.

---

## Exercise 4: Break and Fix a PVMAP

**Goal:** Understand validation and repair.

1. Copy a working PVMAP:
   ```bash
   cp ground_truth/bis_bis_central_bank_policy_rate/pvmap/bis_bis_central_bank_policy_rate_pvmap.csv /tmp/broken_pvmap.csv
   ```
2. Introduce errors:
   - Change `REF_AREA:Reference area` to `ref_area:reference area` (wrong case)
   - Change `{Data}` to `[DATA]` (wrong placeholder)
   - Add an extra row with a made-up key like `FAKE_COLUMN,fakeProperty,fakeValue`
3. Run validation manually:
   ```bash
   PYTHONPATH="$(pwd):$(pwd)/src" python3 tools/stat_var_processor.py \
     --input_data="input/bis_bis_central_bank_policy_rate/test_data/WS_CBPOL_csv_flat_input.csv" \
     --pv_map="/tmp/broken_pvmap.csv" \
     --generate_statvar_name=True \
     --output_path="/tmp/broken_output"
   ```
4. Read the error output. How many rows were produced vs the working version?
5. Look at `src/pipeline/validation/pvmap_repair.py` -- which of your errors would `repair_pvmap()` fix automatically?

**Expected findings:** The case error and placeholder error are both fixable by `repair_pvmap()`. The fake key would survive repair but produce zero matches (and get flagged in the key match report).

---

## Exercise 5: Add a New Dataset

**Goal:** Understand the input structure requirements.

1. Find a small CSV dataset (any public data with place + date + value columns). Good sources: World Bank Open Data, OECD.Stat, or simply create a 20-row CSV by hand.
2. Create the directory structure:
   ```bash
   mkdir -p input/my_test_dataset/test_data/
   cp your_data.csv input/my_test_dataset/test_data/my_test_data_input.csv
   ```
3. Run discovery only (dry run):
   ```bash
   python src/run_pipeline.py --dataset=my_test_dataset --dry-run
   ```
4. Run the full pipeline:
   ```bash
   python src/run_pipeline.py --dataset=my_test_dataset --skip-evaluation
   ```
5. Examine the generated PVMAP. Does it make sense for your data?

**Note:** Skip evaluation because you do not have a ground truth PVMAP for your new dataset. If you want to create one, you can hand-write a PVMAP based on the generated one and place it in `ground_truth/my_test_dataset/pvmap/`.

---

## Exercise 6: Trace the Sampling Pipeline

**Goal:** Understand how the sample and skeleton_summary are created.

1. Force-resample the BIS dataset:
   ```bash
   python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate \
     --force-resample --skip-schema-selection --skip-evaluation
   ```
2. Find the sampled CSV and check its row count:
   ```bash
   wc -l output/bis_bis_central_bank_policy_rate/agentic_sampled.csv
   ```
3. Find and read `data_context.json` -- what column classifications did the profiler assign?
   ```bash
   cat output/bis_bis_central_bank_policy_rate/data_context.json | python -m json.tool
   ```
4. Find the skeleton_summary (in pipeline logs or output). Identify:
   - Which section lists column names and types?
   - Which section describes dimensions?
   - Which section shows sample data?

**Key insight:** The skeleton_summary is what the PVMAP generation agent actually reads to understand the dataset. If the skeleton misclassifies a column (e.g., treats a dimension as a value), the generated PVMAP will be wrong.

---

## Exercise 7: Read and Modify a Prompt

**Goal:** Understand how the PVMAP prompt is constructed.

1. Open `src/resources/prompts/improved_pvmap_prompt.txt`
2. Find all `{{PLACEHOLDER}}` patterns. List them and describe what fills each one.
3. Open `output/bis_bis_central_bank_policy_rate/populated_prompt.txt` -- this is the actual prompt sent to the LLM. Compare with the template.
4. Make a small change to the prompt (e.g., add "Always include unit mappings when a unit column is present" to the instructions)
5. Re-run the BIS dataset and compare the generated PVMAP before and after:
   ```bash
   cp output/bis_bis_central_bank_policy_rate/generated_pvmap.csv /tmp/pvmap_before.csv
   python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --skip-sampling --skip-evaluation
   diff /tmp/pvmap_before.csv output/bis_bis_central_bank_policy_rate/generated_pvmap.csv
   ```

**Note:** Remember to revert your prompt change after the exercise.

---

## Exercise 8: Write a Test

**Goal:** Contribute to the test suite.

1. Open `src/pipeline/validation/pvmap_repair.py` and find `_clean_hallucinated_key()`
2. Read the existing tests in `tests/pipeline/validation/test_pvmap_repair.py` to understand the patterns
3. Think of an edge case not covered by existing tests. Some ideas:
   - A key with trailing whitespace
   - A key that is an exact match (should be returned unchanged)
   - A key with mixed Unicode characters
4. Write a test for your edge case
5. Run your test:
   ```bash
   PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest \
     tests/pipeline/validation/test_pvmap_repair.py -v -k "your_test_name"
   ```
6. Run the full suite to make sure you did not break anything:
   ```bash
   PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q
   ```

**Success criteria:** Your test passes, the full suite still passes, and your test would catch a real bug if someone broke the function.

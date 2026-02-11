# Appendix

This document contains detailed troubleshooting, architecture information, and evaluation metrics.

## Table of Contents

- [A. Detailed Troubleshooting Guide](#a-detailed-troubleshooting-guide)
- [B. Architecture & Workflow Details](#b-architecture--workflow-details)
- [C. Evaluation Metrics & Benchmarks](#c-evaluation-metrics--benchmarks)

---

# A. Detailed Troubleshooting Guide

## Common Errors and Solutions

### 1. ModuleNotFoundError: No module named 'file_util'

**Error:**
```
ModuleNotFoundError: No module named 'file_util'
```

**Cause:** Python cannot find the `util/` module directory.

**Solution:**
```bash
# Set PYTHONPATH before running the pipeline
export PYTHONPATH="$(pwd):$(pwd)/src"

# Verify you're in the project directory
pwd  # Should show: /path/to/poc-auto-schematization

# Run pipeline again
python src/run_pipeline.py
```

**Permanent fix:** Add to your shell profile:
```bash
# Add to ~/.bashrc or ~/.zshrc
cd /path/to/poc-auto-schematization
echo 'export PYTHONPATH="$PWD:$PWD/src"' >> ~/.zshrc
source ~/.zshrc
```

---

### 2. Claude Code CLI Not Found

**Error:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'claude'
```

**Cause:** Claude Code CLI is not installed or not in PATH.

**Solution:**
```bash
# Install Claude Code CLI
# Visit: https://github.com/anthropics/claude-code

# Verify installation
claude --version

# If installed but not found, check PATH
which claude
```

---

### 3. ANTHROPIC_API_KEY Not Set

**Error:**
```
Error: ANTHROPIC_API_KEY environment variable not set
```

**Solution:**
```bash
# Set API key for current session
export ANTHROPIC_API_KEY="your-api-key-here"

# Or add to your shell profile for persistence
echo 'export ANTHROPIC_API_KEY="your-api-key-here"' >> ~/.zshrc
source ~/.zshrc

# Verify it's set
echo $ANTHROPIC_API_KEY | head -c 10
```

---

### 4. Dataset Output Already Exists

**Behavior:** Pipeline skips datasets with existing output folders.

**Log Message:**
```
Output already exists for dataset_name, skipping...
```

**Solution:**
```bash
# To regenerate output for a specific dataset
rm -rf output/your_dataset_name
python src/run_pipeline.py --dataset=your_dataset_name

# To regenerate all outputs (CAUTION: deletes all results)
rm -rf output/*
python src/run_pipeline.py
```

---

### 5. Validation Failed After Max Retries

**Error in logs:**
```
Validation failed after 2 retries
ERROR: Dataset failed: your_dataset_name
```

**Cause:** Generated PVMAP has issues that stat_var_processor cannot handle.

**Investigation:**
```bash
# Check the generation log
cat logs/your_dataset/generation_*.log

# Check the validation error from last attempt
cat output/your_dataset/generated_response/attempt_2.md

# Manually inspect the PVMAP
cat output/your_dataset/generated_pvmap.csv
```

**Solutions:**
1. **Check metadata CSV** - Verify column mappings are correct:
   ```bash
   cat input/your_dataset/*_metadata.csv
   ```

2. **Verify sampled data** - Ensure it's representative:
   ```bash
   head -20 input/your_dataset/test_data/combined_sampled_data.csv
   ```

3. **Force regenerate samples**:
   ```bash
   python src/run_pipeline.py --force-resample --dataset=your_dataset
   ```

4. **Manually edit PVMAP** and re-run validation:
   ```bash
   python3 tools/stat_var_processor.py \
       --input_data=input/your_dataset/test_data/combined_sampled_data.csv \
       --pv_map=output/your_dataset/generated_pvmap.csv \
       --config_file=input/your_dataset/*_metadata.csv
   ```

---

### 6. Permission Denied Errors

**Error:**
```
PermissionError: [Errno 13] Permission denied: 'output/dataset'
```

**Cause:** Output directory or files have incorrect permissions.

**Solution:**
```bash
# Fix permissions for output directory
chmod -R u+w output/

# Or remove and recreate
rm -rf output/problematic_dataset
python src/run_pipeline.py --dataset=problematic_dataset
```

---

### 7. Ground Truth Not Found (Evaluation)

**Message in logs:**
```
Ground truth PVMAP not found, skipping evaluation
```

**Cause:** This is **expected behavior** if ground truth PVMAP doesn't exist.

**Notes:**
- Evaluation is **non-blocking** - pipeline continues successfully
- The system uses a three-tier precedence for finding ground truth
- Pipeline logs which discovery method is being used

**Three-Tier Ground Truth Discovery:**

1. **Tier 1 (Highest):** `--ground-truth-pvmap` - Explicit single file
2. **Tier 2 (Medium):** `--ground-truth-dir` - Directory search by dataset name
3. **Tier 3 (Lowest):** `--ground-truth-repo` - Auto-discovery from repository structure

**Verify ground truth exists:**

```bash
# Check logs to see which method is being used
grep "ground truth" logs/pipeline_*.log

# Tier 3: Bundled ground truth (default)
ls ground_truth//your_dataset/*_pvmap.csv

# Tier 2: Directory search
ls /path/to/ground_truth/*your_dataset*pvmap*.csv

# Tier 1: Explicit file
ls /path/to/explicit/file.csv
```

**Solutions:**

**Option 1: Skip evaluation entirely**
```bash
python src/run_pipeline.py --skip-evaluation
```

**Option 2: Provide explicit ground truth file (single dataset)**
```bash
python src/run_pipeline.py --dataset=bis \
    --ground-truth-pvmap=/path/to/bis_reference.csv
```

**Option 3: Use bundled ground truth (default)**
```bash
# Uses bundled ground truth in ground_truth//
python src/run_pipeline.py
```

**Option 4: Custom ground truth location**
```bash
# For custom ground truth structure
python src/run_pipeline.py \
    --ground-truth-repo=/path/to/custom/ground_truth
```

**Troubleshooting Precedence Issues:**

If multiple arguments are provided, check which one takes precedence:

```bash
# This will use explicit file (Tier 1, highest)
python src/run_pipeline.py \
    --ground-truth-pvmap=/path/file.csv \
    --ground-truth-dir=/path/dir/ \
    --ground-truth-repo=/path/repo/
```

**Check logs for:**
- "Using explicit ground truth PVMAP for {dataset}: {filename}"
- "Found ground truth: {filename}"
- "Source: {directory_path}"

**Common Issues:**

1. **Single file with multiple datasets:** Only first dataset is evaluated, rest are skipped
   - **Solution:** Use `--ground-truth-dir` instead for multiple datasets

2. **Wrong precedence used:** Lower-tier source is being used when higher-tier is provided
   - **Check:** Verify path exists and is accessible
   - **Check:** Look for warnings about conflicting arguments in logs

3. **Directory search finds wrong file:** Multiple matching files in directory
   - **Solution:** Use more specific naming or `--ground-truth-pvmap` for exact control

---

### 8. Pipeline Interrupted Mid-Execution

**Situation:** Pipeline stopped due to Ctrl+C or system issue.

**Solution:**
```bash
# Resume from the last incomplete dataset
python src/run_pipeline.py --resume-from=last_dataset_name

# Or resume from a specific dataset
python src/run_pipeline.py --resume-from=cdc_social_vulnerability_index
```

**Find last processed dataset:**
```bash
# Check the log file
tail -50 logs/pipeline_*.log | grep "Processing dataset"
```

---

### 9. Import Error for pandas/datacommons

**Error:**
```
ModuleNotFoundError: No module named 'pandas'
```

**Cause:** Dependencies not installed or wrong virtual environment.

**Solution:**
```bash
# Verify virtual environment is activated
which python  # Should show .venv path

# If not activated
source .venv/bin/activate

# Reinstall dependencies
uv sync

# Verify installation
python -c "import pandas, datacommons; print('Success!')"
```

---

### 10. Sampled Data Missing Columns

**Error in logs:**
```
KeyError: 'column_name' not found in sampled data
```

**Cause:** Sampler skipped important columns or sampling config is incorrect.

**Solutions:**

1. **Force regenerate sampled data:**
   ```bash
   python src/run_pipeline.py --force-resample --dataset=your_dataset
   ```

2. **Check sampler output:**
   ```bash
   head -5 input/your_dataset/test_data/*_sampled_data.csv
   ```

3. **Adjust sampler configuration** in metadata CSV:
   ```csv
   parameter,value
   sampler_smart_columns,False
   sampler_output_rows,200
   ```

---

### 11. Empty or Malformed PVMAP Generated

**Error in logs:**
```
Error: Generated PVMAP is empty or malformed
```

**Cause:** Claude generated invalid PVMAP format.

**Investigation:**
```bash
# Check Claude's response
cat output/your_dataset/generated_response/attempt_0.md

# Check the populated prompt
cat output/your_dataset/populated_prompt.txt

# Check schema examples
cat input/your_dataset/scripts_*_schema_examples_*.txt
```

**Solutions:**
1. Verify schema example files are present and valid
2. Check that metadata CSV has correct configuration
3. Try regenerating with more representative sampled data

---

### 12. Timeout Errors

**Error:**
```
TimeoutError: Command timed out after 900 seconds
```

**Cause:** PVMAP generation or validation taking too long.

**Solutions:**
1. **Reduce sampled data size** in metadata CSV:
   ```csv
   parameter,value
   sampler_output_rows,50
   ```

2. **Increase timeout** (edit `src/run_pipeline.py`):
   ```python
   GENERATION_TIMEOUT = 1800  # 30 minutes instead of 15
   ```

---

### 13. Schema Selection Failed

**Error:**
```
ERROR: Failed to select schema for dataset_name
ERROR: Schema base directory not found: schema_example_files/
```

**Causes:**
- Schema base directory missing or invalid
- Claude CLI invocation failed
- Missing or invalid metadata files
- No sampled data available for analysis

**Solutions:**

1. **Check schema directory exists:**
   ```bash
   ls src/resources/schema_examples/
   # Should show: Demographics, Economy, Education, Employment, Energy, Health, School
   ```

2. **Verify metadata files:**
   ```bash
   ls input/your_dataset/*_metadata.csv
   head -5 input/your_dataset/*_metadata.csv
   ```

3. **Check sampled data:**
   ```bash
   ls input/your_dataset/test_data/*_sampled_data.csv
   ```

4. **Run schema selector standalone with verbose output:**
   ```bash
   python3 src/pipeline/schema_selection/schema_selector.py --input_dir=input/your_dataset/ --dry_run
   ```

5. **Skip schema selection and manually copy files:**
   ```bash
   # Copy schema files for your category (e.g., Health)
   cp src/resources/schema_examples/Health/*.txt input/your_dataset/
   cp src/resources/schema_examples/Health/*.mcf input/your_dataset/

   # Run pipeline with schema selection skipped
   python src/run_pipeline.py --dataset=your_dataset --skip-schema-selection
   ```

6. **Force schema re-selection:**
   ```bash
   python src/run_pipeline.py --dataset=your_dataset --force-schema-selection
   ```

---

### Getting Help

If you encounter issues not covered here:

1. **Check the logs:**
   ```bash
   # Main pipeline log
   tail -100 logs/pipeline_*.log

   # Dataset-specific log
   tail -100 logs/your_dataset/generation_*.log
   ```

2. **Verify your setup:**
   ```bash
   # Check Python version (should be 3.12+)
   python --version

   # Check Claude CLI version
   claude --version

   # Verify PYTHONPATH
   echo $PYTHONPATH

   # Verify API key is set
   echo $ANTHROPIC_API_KEY | head -c 10
   ```

3. **Check GitHub repository issues:**
   - Search for similar problems
   - Open a new issue with logs and error messages

---

# B. Architecture & Workflow Details

## Pipeline Architecture

The PVMAP Pipeline is a fully automated system that generates Property-Value maps from source data using Claude Code CLI.

### Design Principles

1. **Full Automation** - One command processes entire dataset lifecycle
2. **Smart Sampling** - Automatically generates representative data samples
3. **Retry Logic** - Self-corrects validation errors with LLM feedback
4. **Non-Blocking Evaluation** - Gracefully handles missing ground truth
5. **Directory Flexibility** - Supports custom input/output directories

### Pipeline Phases

```
Phase 1: Auto-Sampling (Optional)
    ↓
Phase 1.5: Schema Selection (Optional)
    ↓
Phase 2: PVMAP Generation
    ↓
Phase 2.5: Metadata Generation (auto_config.csv)
    ↓
Phase 3: Validation (uses auto_config.csv)
    ↓ (retry up to 2 times if validation fails — regenerates PVMAP + auto_config each iteration)
Phase 4: Evaluation (Optional)
```

---

## Phase 1: Auto-Sampling

**Goal:** Prepare representative data samples for PVMAP generation

### How It Works

1. **Check for existing sampled files** matching pattern: `*_sampled_data.csv`
2. **If sampled file exists:**
   - WITHOUT `--force-resample`: Reuse existing file
   - WITH `--force-resample`: Regenerate sample
3. **If sampled file does NOT exist:**
   - Automatically calls `src/pipeline/sampling/data_sampler.py`
   - Generates `{input_filename_without_extension}_sampled_data.csv`
   - Creates `combined_sampled_data.csv` for pipeline

### Sampling Algorithm

**Smart Column Analysis:**
- Skips constant columns (same value everywhere)
- Skips derived columns (calculated from other columns)
- Recognizes ID/CODE/FIPS/KEY columns
- Focuses on meaningful data columns

**Categorical Coverage:**
- Ensures all categorical values are represented
- Balances rows per category (default: 5 rows per value)
- Avoids duplicate patterns

**Numeric Range Coverage:**
- Samples values across quartiles (min, q1, median, q3, max)
- Ensures numeric data spans the full range

**Aggregation Row Detection:**
- Deprioritizes total/summary rows
- Detects keywords: Total, All, Sum, Overall, National, etc.
- Limits aggregation rows based on configuration (default: 2)

### Configuration

Controlled via metadata CSV:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `sampler_output_rows` | 100 | Maximum rows in output |
| `sampler_rows_per_key` | 5 | Max rows per categorical value |
| `sampler_categorical_threshold` | 0.1 | Ratio threshold for categorical detection |
| `sampler_max_aggregation_rows` | 2 | Max total/summary rows |
| `sampler_ensure_coverage` | True | Ensure all categories covered |
| `sampler_smart_columns` | True | Skip constant/derived columns |
| `sampler_detect_aggregation` | True | Detect and limit total rows |

---

## Phase 1.5: Schema Selection

**Goal:** Automatically select the most appropriate schema category for each dataset

**Script:** `src/pipeline/schema_selection/schema_selector.py` (integrated into pipeline via `src/run_pipeline.py`)

### How It Works

1. **Check for existing schema files** matching patterns:
   - `scripts_*_schema_examples_*.txt`
   - `scripts_statvar_llm_config_vertical_*.mcf`
2. **If schema files exist:**
   - WITHOUT `--force-schema-selection`: Skip Phase 1.5 (use existing)
   - WITH `--force-schema-selection`: Proceed with re-selection
3. **If schema files do NOT exist:**
   - Validate input directory structure
   - Merge multiple metadata files if present
   - Generate data preview from sampled data
   - Build Claude prompt with context
   - Invoke Claude CLI to select category
   - Copy selected schema files to dataset directory

### Selection Algorithm

**Input Analysis:**
- Examines all metadata configuration files
- Generates data preview (first 20 rows of sampled data)
- Provides category descriptions and examples

**Claude Classification:**
- Reviews metadata fields (place_property, date_property, value_property, etc.)
- Analyzes sample data columns and values
- Compares against 7 category descriptions
- Selects best-matching category

**Schema Categories:**

| Category | Description | Indicators |
|----------|-------------|------------|
| Demographics | Population, age, gender, race, household, nativity | Person-level data, census variables, demographic breakdowns |
| Economy | GDP, business, revenue, trade, commodities | Financial metrics, economic indicators, business stats |
| Education | Enrollment, degrees, attainment, literacy | School/college data, education levels, academic performance |
| Employment | Labor force, jobs, wages, unemployment | Workforce statistics, occupational data, employment rates |
| Energy | Power generation, consumption, infrastructure | Energy production/usage, environmental metrics |
| Health | Disease, mortality, healthcare, medical conditions | Health outcomes, disease prevalence, medical surveys |
| School | School-specific metrics, performance, facilities | Institution-level data, school characteristics |

### Output

**Files Copied:**
```
input/{dataset_name}/
└── scripts_statvar_llm_config_schema_examples_dc_topic_{Category}.txt
```

**Logging:**
```
INFO: Phase 1.5: Selecting schema for india_nfhs...
INFO: Invoking Claude CLI to select schema category...
INFO: Selected schema category: Health
INFO: Successfully copied schema file:
INFO:   - scripts_statvar_llm_config_schema_examples_dc_topic_Health.txt
```

### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--skip-schema-selection` | False | Skip Phase 1.5 (use existing schema files) |
| `--force-schema-selection` | False | Force re-selection even if files exist |
| `--schema-base-dir` | `src/resources/schema_examples/` | Directory containing schema categories |

### Standalone Usage

The schema selector can be run independently:

```bash
# Automatic selection and copy
python3 src/pipeline/schema_selection/schema_selector.py --input_dir=input/your_dataset/

# Dry run (preview without copying)
python3 src/pipeline/schema_selection/schema_selector.py --input_dir=input/your_dataset/ --dry_run

# Force re-selection
python3 src/pipeline/schema_selection/schema_selector.py --input_dir=input/your_dataset/ --force

# Custom schema directory
python3 src/pipeline/schema_selection/schema_selector.py \
    --input_dir=input/your_dataset/ \
    --schema_base_dir=/path/to/schemas
```

---

## Phase 2: PVMAP Generation

**Goal:** Generate Property-Value mapping using Gemini LLM

### Input Preparation

The pipeline combines data from multiple sources:

| Placeholder | Source | Purpose |
|-------------|--------|---------|
| `{{SCHEMA_EXAMPLES}}` | `schema_vocab.json` (compressed) | Valid properties, DCIDs, enum values from schema category |
| `{{SAMPLED_DATA}}` | `agentic_sampled.csv` | Representative sample of input data (LLM-driven) |
| `{{SKELETON_SUMMARY}}` | Sampling agent output | Column classifications (place, time, dimension, value) |
| `{{METADATA_CONFIG}}` | `*_metadata.csv` (optional) | Configuration for processor (when `--use-metadata` enabled) |

### Prompt Template

The pipeline uses a structured prompt template (`src/resources/prompts/improved_pvmap_prompt.txt`):

1. **Task Description** - Explain PVMAP format and requirements
2. **Schema Vocabulary** - Compressed vocab with valid properties/DCIDs for the domain
3. **Sampled Data** - Representative sample with column analysis
4. **Skeleton Summary** - Column role classifications from sampling agent
5. **Metadata Configuration** - Column mappings (if `--use-metadata` enabled)
6. **Output Format** - Specify expected CSV format

### LLM Invocation

Uses Gemini API via Google ADK `LlmAgent` with structured output schema:

```python
# Default model: gemini-3-pro-preview (configurable via --model flag)
LlmAgent(
    model=model,
    output_schema=PVMAPOutput,
    output_key="pvmap_output",
)
```

### Output Files

- `generated_pvmap.csv` - The generated property-value mapping
- `generation_notes.md` - LLM analysis and reasoning (with attempt history)
- `populated_prompt.txt` - Full prompt sent to LLM
- `generated_response/attempt_0.md` - LLM response (with model info)
- `generated_response/attempt_0.json` - Attempt metadata (model, tokens, duration)

---

## Phase 2.5: Metadata Generation

**Goal:** Auto-generate enriched metadata config from the PVMAP for stat_var_processor

### How It Works

The `MetadataGenerationAgent` runs after PVMAP generation and before validation on **every iteration** of the retry loop:

1. **Extract PVMAP-derived parameters:**
   - `output_columns` — columns the PVMAP maps to (e.g., `observationAbout,observationDate,variableMeasured,value,unit,scalingFactor`)
   - `mapped_rows` — number of data rows the PVMAP maps
   - `mapped_columns` — number of columns the PVMAP maps
   - `header_rows` — number of header rows detected
   - `drop_statvars_without_svobs` — whether to drop orphan StatVars
   - `generate_statvar_name` — whether to auto-generate StatVar names

2. **Merge with existing metadata:**
   - Loads GT metadata or user metadata (if available)
   - Existing values override auto-generated ones (via `merge_with_existing()`)
   - Result is a strict superset: everything GT/user has, PLUS PVMAP-derived params

3. **Write `auto_config.csv`** to the output directory

4. **Set `generated_config_path`** in session state for the Validator

### Output

- `auto_config.csv` — enriched 2-column CSV (parameter, value)

---

## Phase 2.75: PVMAP Repair (Automatic)

**Goal:** Programmatically fix common PVMAP issues BEFORE running the expensive validation subprocess

**Module:** `src/pipeline/validation/pvmap_repair.py`

### Why It Exists

LLMs frequently produce PVMAPs with minor key mismatches (wrong case, extra whitespace, truncated names) that cause validation to fail. Rather than waste a 5-minute subprocess call + a retry iteration on fixable issues, the repair module catches and fixes them in milliseconds.

### How It Works

The repair module runs automatically inside `ValidationAgent` after PVMAP generation and before the subprocess call:

```
PVMAP Generated → repair_pvmap() → pre_validate_pvmap() → [subprocess or early return]
```

#### Step 1: Key Repair (`repair_pvmap`)

For each PVMAP key, attempts to match it to an actual input CSV column header using a 5-tier cascade:

| Tier | Method | Example |
|------|--------|---------|
| 1 | Exact match | `REF_AREA` → `REF_AREA` |
| 2 | Case-insensitive | `ref_area` → `REF_AREA` |
| 3 | Whitespace-normalized | `REF  AREA` → `REF_AREA` |
| 4 | Alphanumeric-only | `ref-area` → `REF_AREA` |
| 5 | Fuzzy match (≥0.85 cutoff) | `REF_AERA` → `REF_AREA` |

Also normalizes placeholder syntax: `[DATA]` → `{Data}`, `[NUMBER]` → `{Number}`.

#### Step 2: Pre-Validation (`pre_validate_pvmap`)

Fast structural checks that skip the 5-minute subprocess for obviously broken PVMAPs:

1. **Column match rate** — at least 50% of PVMAP keys must match input columns
2. **Required properties** — `observationAbout`, `observationDate`, and `value` must be present
3. **No unresolved placeholders** — no `[DATA]` or `[NUMBER]` remaining after normalization
4. **Non-empty** — PVMAP must have at least one data row

#### Step 3: Key Match Report (`generate_key_match_report`)

Generates a markdown report for the feedback agent:

```
## Key Match Report
- ✓ Matched: REF_AREA, TIME_PERIOD, OBS_VALUE (3/5)
- ✎ Auto-Fixed: ref_area → REF_AREA (case), obs value → OBS_VALUE (whitespace)
- ✗ UNMATCHED: InvalidColumn (no match found)
- ○ Unmapped input columns: FREQ, STATUS (suggestion: check if these should be mapped)
```

### State Keys

| Key | Set By | Used By |
|-----|--------|---------|
| `pvmap_repair_changes` | ValidationAgent | Feedback agent (repair log) |
| `key_match_report` | ValidationAgent | Feedback agent (targeted guidance) |

### Public API

```python
from src.pipeline.validation.pvmap_repair import repair_pvmap, pre_validate_pvmap, generate_key_match_report

pvmap_csv, changes = repair_pvmap(pvmap_csv_str, Path("input_data.csv"))
ok, errors = pre_validate_pvmap(pvmap_csv_str, Path("input_data.csv"))
report = generate_key_match_report(pvmap_csv_str, Path("input_data.csv"))
```

---

## Phase 3: Validation

**Goal:** Validate generated PVMAP using stat_var_processor and extract semantic analysis

### How It Works

1. **Run stat_var_processor** (via subprocess):
   ```bash
   python3 tools/stat_var_processor.py \
       --input_data=input/{dataset}/test_data/*_input.csv \
       --pv_map=output/{dataset}/generated_pvmap.csv \
       --config_file=output/{dataset}/auto_config.csv \
       --generate_statvar_name=True \
       --output_path=output/{dataset}/processed
   ```

   **Metadata priority for `--config_file`:**
   1. **Tier 1:** `auto_config.csv` (auto-generated, has PVMAP-derived params + merged GT/user values)
   2. **Tier 2:** User-provided metadata (fallback, when `--use-metadata` enabled)
   3. **Tier 3:** Ground truth metadata (last resort, for benchmarking only)

2. **Check validation result:**
   - **Success**: Extract StatVar MCF analysis, move to quality evaluation
   - **Failure**: Extract error feedback and retry

3. **StatVar MCF Analysis** (on success):
   After validation passes, `_extract_statvar_summary()` parses the generated `processed_stat_vars.mcf` to produce a semantic analysis:
   - Property→value distributions across all generated StatVars
   - Flags raw strings without `dcid:` prefix on dimension properties
   - Flags values with special characters ($, /, –) suggesting CSV parsing corruption
   - Flags single-value dimensions that may be missing category breakdowns
   - Summary capped at 40 lines to avoid prompt bloat

4. **Quality Evaluation:**
   - Heuristic scoring (structural quality)
   - Ground truth comparison (if available) — node accuracy, PV accuracy
   - Sets `quality_reject_reason`: `"pv_accuracy_low"` or `"quality_below_threshold"`

5. **Feedback Loop** (unified `ConditionalFeedbackAgent`):
   - **Path A (Validation Failed):** Structural error feedback from subprocess output
   - **Path B (Quality Low):** Context-aware feedback with schema vocab + StatVar analysis:
     - `"PV ACCURACY LOW"` mode: Semantic focus — cross-references StatVar analysis with schema vocabulary to identify property/value mismatches
     - `"QUALITY LOW"` mode: Structural focus — row coverage, column mappings, format

### Feedback Context

The feedback agent receives the same domain context as the generator:

| Context | Source | Purpose |
|---------|--------|---------|
| Schema vocabulary | `schema_vocab_content` state | Valid properties, DCIDs, enum values for the domain |
| Schema category | `schema_category` state | Domain classification (Health, Economy, etc.) |
| Skeleton summary | `skeleton_summary` state | Column roles (place, time, dimension, value) |
| StatVar analysis | `validation_statvar_analysis` state | MCF-parsed property distributions + issue flags |
| Counter summary | `validation_counter_summary` state | High-level validation metrics |
| Quality metrics | `quality_metrics` state | Heuristic scores + GT accuracy + reject reason |

### Anti-Regression Guidance

Feedback includes a "Rows to PRESERVE" section identifying correct PVMAP rows that should not be changed during retry, preventing regressions where fixing one issue breaks previously working mappings.

### Output Files

- `processed.csv` - Validated StatVarObservations
- `processed.tmcf` - Template MCF file
- `processed_stat_vars.mcf` - StatVar definitions (also parsed for feedback analysis)

---

## Phase 4: Evaluation

**Goal:** Compare generated PVMAP against ground truth

### Ground Truth Search

1. **Search in bundled ground-truth:**
   ```
   ground_truth//{dataset}/*_pvmap.csv
   ```

2. **If found:** Load both PVMAPs and compare
3. **If not found:** Log warning and skip (non-blocking)

### Comparison Method

Uses `mcf_diff.diff_mcf_nodes()` for node-by-node comparison:

1. **Load PVMAPs** using `property_value_mapper.load_pv_map()`
2. **Compare nodes** - Find matched, modified, added, deleted
3. **Calculate metrics** - Accuracy, coverage, precision, recall
4. **Generate diff report** - Detailed property-level differences

### Metrics Calculated

| Metric | Formula |
|--------|---------|
| Node Accuracy | `nodes-matched / nodes-ground-truth × 100%` |
| Node Coverage | `(nodes-matched + nodes-with-diff) / nodes-ground-truth × 100%` |
| PV Accuracy | `PVs-matched / (PVs-matched + pvs-modified + pvs-deleted) × 100%` |
| Precision | `(PVs-matched + pvs-modified) / (PVs-matched + pvs-modified + pvs-added) × 100%` |
| Recall | `PVs-matched / (PVs-matched + pvs-modified + pvs-deleted) × 100%` |

### Output Files

- `eval_results/diff_results.json` - Raw metrics in JSON format
- `eval_results/diff.txt` - Detailed property-level diff

---

## Retry Logic Design

### Why Retry?

PVMAP generation may fail for two distinct reasons:
1. **Validation failure** — stat_var_processor rejects the PVMAP (wrong column names, invalid formats, empty output)
2. **Quality below threshold** — Validation passes but quality evaluation detects issues:
   - Low PV accuracy (property-value pairs don't match expected patterns)
   - Low heuristic quality score (structural issues)

### Retry Strategy

**Attempt 0 (Initial):**
- Full prompt with schema examples, sampled data, and skeleton summary
- Schema vocabulary injected if available
- No prior feedback

**Attempt 1+ (Retries):**
- Includes accumulated error feedback from previous attempts
- Feedback is context-aware based on failure type:

| Failure Type | Feedback Mode | Context Provided |
|-------------|---------------|------------------|
| Validation failed | `VALIDATION FAILED` | Subprocess error output (sampled to ~300 lines) |
| PV accuracy low | `PV ACCURACY LOW` | Schema vocab + StatVar MCF analysis + GT metrics |
| General quality low | `QUALITY LOW` | Heuristic scores + counter summary + GT metrics |

**Max 3 attempts total** (configurable via `max_iterations` on LoopAgent).

### Retry Loop Architecture (ADK)

The retry loop uses Google ADK's `LoopAgent` with 7 sub-agents:

```
LoopAgent (max_iterations=6)
├── StatePreparationAgent        — Prepares state, logs feedback presence
├── PVMAPGenerationAgent         — Generates PVMAP with accumulated feedback
├── MetadataGenerationAgent      — Generates auto_config.csv from PVMAP (merged with GT/user)
├── ValidationAgent              — Runs stat_var_processor with auto_config, extracts StatVar analysis
├── QualityEvaluationAgent       — Heuristic + GT scoring, sets reject reason
├── ConditionalFeedbackAgent     — Unified feedback (validation-failed OR quality-low)
└── MaxRetriesCheckAgent         — Escalates after max attempts (EventActions.escalate)
```

**Key design:** The `MetadataGenerationAgent` runs on every iteration, so when the PVMAP changes during retry, `auto_config.csv` is regenerated with updated parameters. The `ConditionalFeedbackAgent` is a `BaseAgent` wrapper around an inner `LlmAgent` that determines the feedback path (A or B) and injects appropriate context before delegating to the LLM for analysis.

### Feedback Improvements (2026-02-10)

The feedback agent now receives full domain context:
- **Schema vocabulary** — valid properties, DCIDs, and enum values for the domain
- **Skeleton summary** — column classifications (place, time, dimension, value)
- **StatVar MCF analysis** — parsed property→value distributions from validation output
- **Anti-regression guidance** — identifies correct rows to preserve during retry

This enables semantic feedback (e.g., "income values need DCID mapping, not raw strings") instead of generic structural advice.

### Success Rate

Testing on 10 diverse datasets (2026-02-10):
- **Validation pass rate:** 80% (8/10 pass validation within 3 attempts)
- **New PV accuracy bests:** 2/10 datasets achieved new best PV accuracy scores
- **Key wins:** FBI Crime (+6.6% PV), US Urban School Teachers (+0.7% PV)

---

## Directory Structure Design

### Input Directory

```
input/{dataset_name}/
├── input_metadata/                         # Optional metadata (use with --use-metadata)
│   └── *_metadata.csv                      # Config (param,value rows)
├── schema/                                 # Auto-populated by SchemaSelectionAgent
│   ├── scripts_*_schema_examples_*.txt     # Schema examples
│   └── schema_vocab.json                   # Compressed schema vocabulary
└── test_data/
    ├── *_input.csv                         # Original full dataset (REQUIRED)
    └── *_agentic_sampled.csv               # Auto-generated by LLM-driven sampler
```

### Output Directory

```
output/{dataset_name}/
├── generated_pvmap.csv                # Main output
├── auto_config.csv                    # Auto-generated metadata config (PVMAP-derived + merged)
├── generation_notes.md                # LLM reasoning with attempt history
├── populated_prompt.txt               # Full prompt
├── generated_response/
│   ├── attempt_0.md                   # LLM response (with model info)
│   ├── attempt_0.json                 # Attempt metadata (model, tokens, duration)
│   ├── attempt_1.md                   # If retry
│   ├── attempt_1.json
│   └── attempt_2.md                   # If retry
├── processed.csv                      # Validation output
├── processed.tmcf
├── processed_stat_vars.mcf
└── eval_results/                      # If ground truth found
    ├── diff_results.json
    └── diff.txt
```

### Logging

```
logs/
├── pipeline_{timestamp}.log           # Main pipeline log
└── {dataset}/
    └── generation_{timestamp}.log     # Per-dataset log
```

---

## Key Design Decisions

### 1. Auto-Sampling Integration

**Decision:** Integrate sampling into main pipeline instead of requiring separate step

**Rationale:**
- Reduces manual steps
- Ensures samples are always up-to-date
- Allows reuse of existing samples for consistency

### 2. Non-Blocking Evaluation

**Decision:** Make evaluation optional and non-blocking

**Rationale:**
- Not all datasets have ground truth
- Pipeline should succeed even without evaluation
- Allows testing on new datasets without ground truth

### 3. Retry with Feedback

**Decision:** Provide detailed error feedback for retries instead of blind retries

**Rationale:**
- Claude can learn from specific errors
- Higher success rate on retry
- Faster convergence to valid PVMAP

### 4. Directory Flexibility

**Decision:** Support custom input/output directories via command-line flags

**Rationale:**
- Enable testing without affecting production data
- Allow multiple environments (dev, test, prod)
- Facilitate parallel experimentation

### 5. Intelligent Schema Selection

**Decision:** Automatically select schema category using AI analysis instead of requiring manual classification

**Rationale:**
- Reduces manual effort and human error
- Leverages Claude's understanding of dataset content
- Scales to large numbers of datasets
- Allows dynamic re-selection based on data changes
- Provides flexibility with skip/force options

**Implementation:**
- Phase 1.5 analyzes metadata + sampled data
- Claude CLI classifies into 7 predefined categories
- Schema files automatically copied to dataset directory
- Falls back gracefully if selection fails

### 6. Template Placeholder Escaping

**Decision:** Convert PVMAP `{Data}`/`{Number}` placeholders to `[DATA]`/`[NUMBER]` when passing through ADK instruction templates

**Rationale:**
ADK's `LlmAgent` interprets ALL `{word}` patterns in instruction strings as state variable references. PVMAP content uses `{Data}` and `{Number}` as value placeholders, causing `KeyError` when ADK tries to resolve them.

**Module:** `src/agents/template_utils.py`

**Functions:**

| Function | Purpose | Use When |
|----------|---------|----------|
| `escape_pvmap_placeholders(text)` | `{Data}` → `[DATA]`, `{Number}` → `[NUMBER]`, `{word}` → `[word]` | Before storing PVMAP content in state that will be injected into LlmAgent instructions |
| `sanitize_for_adk(instruction)` | Escape ALL `{word}` patterns (including `{{word}}`) | On fully-resolved instruction strings where all Python `.replace()` substitutions are done |
| `unescape_pvmap_placeholders(text)` | `[DATA]` → `{Data}`, `[NUMBER]` → `{Number}` | Before writing final PVMAP output to disk |
| `prepare_state_for_templating(ctx, keys)` | Batch escape multiple state variables | Convenience wrapper for escaping multiple state keys at once |

**Critical lesson:** `{{word}}` is NOT an escape in ADK — ADK's regex strips ALL braces, so `{{Data}}` resolves identically to `{Data}`. The only safe approach is bracket escaping: `[DATA]`.

### 7. LLM Metadata Capture (Artifact Plugin)

**Decision:** Capture model metadata (name, tokens, timing, thinking content) during LLM calls via an ADK plugin

**Rationale:**
- Attempt artifacts (`attempt_*.md`, `attempt_*.json`) need model info and token counts
- Thinking content (chain-of-thought reasoning) is valuable for debugging
- Plugin hooks are the only ADK mechanism to intercept model calls

**Module:** `src/utils/artifact_plugin.py`

**How it works:**

```
ArtifactLoggingPlugin (BasePlugin)
├── before_model_callback  → Start timer, extract request config, enable ThinkingConfig
└── after_model_callback   → Extract usage stats, thinking content, store as pvmap_llm_result
```

**State output:** `pvmap_llm_result` dict with keys:
- `model` — Model name (e.g., `gemini-3-pro-preview`)
- `temperature`, `max_output_tokens` — Request config
- `prompt_token_count`, `candidates_token_count`, `total_token_count` — Usage stats
- `thinking_content` — Chain-of-thought reasoning (if model supports it)
- `duration_seconds` — Wall-clock time for the model call

**Only captures calls from agents named** `"Generator"` or `"PVMAPGenerator"` — other agent calls are ignored.

---

# C. Evaluation Metrics & Benchmarks

## Evaluation Methodology

The pipeline uses diff-based evaluation to compare generated PVMAPs against human-created ground truth.

### Node-Level Metrics

| Metric | Description |
|--------|-------------|
| `nodes-ground-truth` | Total keys in human-created PVMAP (baseline) |
| `nodes-auto-generated` | Total keys in LLM-generated PVMAP |
| `nodes-matched` | Keys with IDENTICAL property-values in both (ideal: HIGH) |
| `nodes-with-diff` | Keys in both but with DIFFERENT property-values (ideal: LOW) |
| `nodes-missing-in-mcf2` | Keys in ground truth but NOT in LLM output (LLM missed) |
| `nodes-missing-in-mcf1` | Keys in LLM output but NOT in ground truth (extra keys) |

### Property-Value (PV) Level Metrics

| Metric | Description |
|--------|-------------|
| `PVs-matched` | Property-value pairs that match EXACTLY (ideal: HIGH) |
| `pvs-modified` | Properties in both but with DIFFERENT values (ideal: LOW) |
| `pvs-added` | Properties in LLM output but NOT in ground truth (ideal: LOW) |
| `pvs-deleted` | Properties in ground truth but NOT in LLM output (ideal: ZERO) |

### Key Formulas

```
Node Accuracy   = (nodes-matched / nodes-ground-truth) × 100%
Node Coverage   = ((nodes-matched + nodes-with-diff) / nodes-ground-truth) × 100%
PV Accuracy     = PVs-matched / (PVs-matched + pvs-modified + pvs-deleted) × 100%
Precision       = (PVs-matched + pvs-modified) / (PVs-matched + pvs-modified + pvs-added) × 100%
Recall          = PVs-matched / (PVs-matched + pvs-modified + pvs-deleted) × 100%
```

---

## Quality Benchmarks

| Metric | Excellent | Good | Needs Work | Poor |
|--------|-----------|------|------------|------|
| Node Accuracy | >80% | 50-80% | 20-50% | <20% |
| PV Accuracy | >70% | 40-70% | 20-40% | <20% |
| pvs-deleted | 0 | 1-5 | 6-20 | >20 |
| nodes-missing-in-mcf2 | 0 | 1-3 | 4-10 | >10 |

---

## Benchmark Comparison: Claude vs Gemini

### Overall Averages (27 Datasets)

| Metric | Gemini Baseline | Claude Results | Change |
|--------|-----------------|----------------|--------|
| **PV Accuracy** | 8.1% | 26.8% | **+18.7%** |
| **Node Accuracy** | 4.6% | 15.1% | **+10.5%** |

### Performance Summary

| Outcome | Count | Percentage |
|---------|-------|------------|
| **Improved (PV Acc)** | 22 | 81.5% |
| **Declined (PV Acc)** | 3 | 11.1% |
| **No Change** | 2 | 7.4% |

---

## Top Improvements

| Dataset | Gemini PV % | Claude PV % | Improvement |
|---------|-------------|-------------|-------------|
| bis_bis_central_bank_policy_rate | 0.0% | 73.1% | **+73.1%** |
| zurich_wir_2552_wiki | 17.9% | 64.3% | **+46.4%** |
| world_bank_commodity_market | 3.7% | 48.8% | **+45.1%** |
| inpe_fire | 0.0% | 44.3% | **+44.3%** |
| census_v2_sahie | 8.0% | 39.4% | **+31.4%** |

---

## Sample Evaluation Report

```
============================================================
DIFF REPORT: bis_central_bank_policy_rate
============================================================

NODE-LEVEL METRICS:
  Ground truth nodes: 7
  Auto-generated nodes: 20
  Nodes matched: 7
  Nodes with diff: 0
  Nodes missing in auto: 0
  Nodes missing in ground truth: 13

PROPERTY-VALUE METRICS:
  PVs matched: 19
  PVs modified: 0
  PVs added: 12
  PVs deleted: 7

ACCURACY: 100.0% (7/7 nodes exact match)
PV ACCURACY: 73.1% (19/26 PVs matched)
============================================================
```

---

## Interpreting Results

### High Node Accuracy (>80%)
- LLM correctly identified all major entities
- PVMAP structure matches ground truth
- Ready for production use

### High PV Accuracy (>70%)
- Property-value mappings are mostly correct
- Minor adjustments may be needed
- Good quality overall

### Low PV Accuracy (<40%)
- Significant differences from ground truth
- Review sampled data representativeness
- Check schema examples relevance
- Consider manual corrections

### High `pvs-deleted` Count
- LLM missed important properties
- May need more context or examples
- Review prompt and schema examples

### High `pvs-added` Count
- LLM added extra properties not in ground truth
- May be over-generalizing
- Could indicate improved mapping (validate manually)

---

## Using Evaluation Results

### For Research
- Compare different prompt strategies
- Analyze failure patterns
- Identify categories with low accuracy

### For Production
- Filter datasets by quality threshold
- Prioritize manual review for low-accuracy datasets
- Use high-accuracy PVMAPs directly

### For Improvement
- Analyze `diff.txt` for common errors
- Refine schema examples based on failures
- Adjust sampling strategy for better representation

---

## Limitations

### Ground Truth Availability
- Only ~50% of datasets have ground truth
- Evaluation limited to datasets with existing PVMAPs

### Diff-Based Comparison
- Assumes ground truth is correct
- May penalize valid alternative mappings
- Doesn't capture semantic equivalence

### Aggregation
- Averages can hide dataset-specific issues
- Some categories may perform better than others

---

## Back to Main Documentation

- [Setup Guide](SETUP.md)
- [Input Structure Guide](INPUT_GUIDE.md)
- [Usage Guide](USAGE.md)
- [Main README](README.md)

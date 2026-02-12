# Usage Guide

This guide explains how to use the PVMAP Pipeline to generate Property-Value maps.

## Quick Start

### Prerequisites

Before running the pipeline, ensure:
- [ ] Setup is complete (see [SETUP.md](SETUP.md))
- [ ] Virtual environment is activated
- [ ] PYTHONPATH is configured
- [ ] Input data is structured correctly (see [INPUT_GUIDE.md](INPUT_GUIDE.md))

### Your First Pipeline Run

Let's test the pipeline with a single dataset:

```bash
# Step 1: Ensure you're in the project directory
cd poc-auto-schematization

# Step 2: Set PYTHONPATH (required)
export PYTHONPATH="$(pwd):$(pwd)/src"

# Step 3: Activate virtual environment (if not already active)
source .venv/bin/activate

# Step 4: Run pipeline on a single dataset (BIS Central Bank Policy Rate)
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate
```

### Check Results

```bash
# View generated output
ls -la output/bis_bis_central_bank_policy_rate/

# Check the generated PVMAP
head -20 output/bis_bis_central_bank_policy_rate/generated_pvmap.csv

# View Claude's reasoning
cat output/bis_bis_central_bank_policy_rate/generation_notes.md
```

**Expected Output Files:**
- `generated_pvmap.csv` - The generated property-value mapping
- `processed.csv` - Validated StatVarObservations
- `processed.tmcf` - Template MCF file
- `processed_stat_vars.mcf` - StatVar definitions
- `generation_notes.md` - Claude's analysis and reasoning

---

## Running the Pipeline

### Basic Usage

```bash
# Process all datasets
python src/run_pipeline.py

# Process specific dataset (partial name match)
python src/run_pipeline.py --dataset=bis

# Preview what will be processed (dry run)
python src/run_pipeline.py --dry-run
```

### Command-Line Options

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| **Dataset Selection** |
| `--dataset` | Process specific dataset (partial name match) | All datasets | `--dataset=bis` |
| `--resume-from` | Resume from specific dataset (skip earlier ones) | None | `--resume-from=edu` |
| `--dry-run` | Show what would be processed without execution | False | `--dry-run` |
| **Directory Configuration** |
| `--input-dir` | Input directory containing datasets | `input/` | `--input-dir=test_input` |
| `--output-dir` | Output directory for generated PVMAPs | `output/` | `--output-dir=test_output` |
| **Phase Control** |
| `--skip-sampling` | Skip auto-sampling (use existing sampled data) | False | `--skip-sampling` |
| `--force-resample` | Force regenerate sampled data | False | `--force-resample` |
| `--skip-schema-selection` | Skip schema selection (use existing schema files) | False | `--skip-schema-selection` |
| `--force-schema-selection` | Force re-select schema files even if they exist | False | `--force-schema-selection` |
| `--schema-base-dir` | Path to schema files directory | `src/resources/schema_examples/` | `--schema-base-dir=/path/to/schemas` |
| `--skip-evaluation` | Skip evaluation phase | False | `--skip-evaluation` |
| `--no-schema-examples` | Skip schema vocab injection into PVMAP prompt | False | `--no-schema-examples` |
| **Input Modes** |
| `--input-file` | Standalone input file (no dataset folder required) | None | `--input-file=data.csv` |
| `--use-metadata` | Use metadata files for prompt building | False | `--use-metadata` |
| `--metadata-file-path` | Explicit metadata file (auto-enables `--use-metadata`) | None | `--metadata-file-path=meta.csv` |
| `--schema-file` | Explicit schema file override | None | `--schema-file=schema.txt` |
| **Model Selection** |
| `--model` or `-m` | Override default LLM model | `gemini-3-pro-preview` | `--model=gemini-2.5-pro` |
| **MCP Integration** |
| `--enable-mcp` | Enable MCP integration for StatVar discovery | False | `--enable-mcp` |
| **Evaluation Configuration** |
| `--ground-truth-pvmap` | Path to single ground truth PVMAP file (Tier 1 precedence) | None | `--ground-truth-pvmap=/path/to/file.csv` |
| `--ground-truth-dir` | Directory containing ground truth files (Tier 2 precedence) | None | `--ground-truth-dir=/path/to/ground_truth` |
| `--ground-truth-repo` | Path to ground truth repo (Tier 3 precedence) | `$GROUND_TRUTH_REPO` or `ground_truth/` | `--ground-truth-repo=/custom/path` |

---

## Pipeline Workflow

The pipeline runs six automated phases:

### Phase 1: Auto-Sampling (Optional)

**What it does:**
- Checks for existing `*_sampled_data.csv` files
- If not found: Automatically generates sampled data (max 100 rows) using LLM-driven agentic sampling
- Generates `skeleton_summary` (column classifications) and `data_context.json` for downstream agents

**Skip this phase:**
```bash
python src/run_pipeline.py --skip-sampling
```

**Force regenerate samples:**
```bash
python src/run_pipeline.py --force-resample
```

### Phase 1.5: Schema Selection (Optional)

**What it does:**
- Checks if schema files already exist in dataset's `schema/` subdirectory
- If not found: Analyzes skeleton_summary using Gemini to select best schema category
- Selects from 7 categories (Demographics, Economy, Education, Employment, Energy, Health, School)
- Copies schema files to `input/{dataset}/schema/` subdirectory
- Loads compressed `schema_vocab.json` for downstream PVMAP prompt injection

**Skip this phase:**
```bash
python src/run_pipeline.py --skip-schema-selection
```

**Force re-selection:**
```bash
python src/run_pipeline.py --force-schema-selection
```

**Use custom schema directory:**
```bash
python src/run_pipeline.py --schema-base-dir=/path/to/schemas
```

**Run schema selector standalone:**
```bash
# Automatically select and copy schema files
python3 src/pipeline/schema_selection/schema_selector.py --input_dir=input/your_dataset/

# Dry run (see what would be selected without copying)
python3 src/pipeline/schema_selection/schema_selector.py --input_dir=input/your_dataset/ --dry_run

# Force re-selection
python3 src/pipeline/schema_selection/schema_selector.py --input_dir=input/your_dataset/ --force
```

### Phase 2: PVMAP Generation

**What it does:**
- Populates prompt with schema vocab, sampled data, skeleton summary, and optional metadata
- Calls Gemini API to generate PVMAP (default model: `gemini-3-pro-preview`)
- Saves response, reasoning, and attempt metadata (model name, token counts)

**Output:**
- `generated_pvmap.csv`
- `generation_notes.md`
- `populated_prompt.txt`

### Phase 2.5: Metadata Generation

**What it does:**
- Automatically generates `output_metadata.csv` from the PVMAP on every iteration
- Extracts PVMAP-derived parameters: `output_columns`, `mapped_rows`, `mapped_columns`, `header_rows`, `drop_statvars_without_svobs`, `generate_statvar_name`
- Merges with any existing GT/user metadata (existing values override auto-generated)
- Sets `generated_config_path` in session state for the Validator

**Output:**
- `output_metadata.csv` — enriched metadata config used by stat_var_processor

### Phase 3: Validation

**What it does:**
- Runs `stat_var_processor.py` to validate generated PVMAP on the **full dataset**
- Passes `output_metadata.csv` as `--config_file` (preferred over GT/user metadata)
- Extracts StatVar MCF analysis for semantic feedback
- If validation fails: Provides error feedback for retry (up to 2 retries)

**Metadata Priority (for `--config_file`):**
1. **Tier 1:** Auto-generated config (`output_metadata.csv`) — has PVMAP-derived params + merged values
2. **Tier 2:** User-provided metadata (fallback, when `--use-metadata` enabled)
3. **Tier 3:** Ground truth metadata (last resort, for benchmarking only)

**Output:**
- `processed.csv`
- `processed.tmcf`
- `processed_stat_vars.mcf`

### Phase 4: Evaluation (Optional)

**What it does:**
- Searches for ground truth PVMAP using three-tier precedence system
- Compares generated vs ground truth using diff-based metrics
- Gracefully skips if ground truth not found (non-blocking)

**Ground Truth Discovery (Three-Tier Precedence):**

1. **Tier 1 (Highest):** Explicit file via `--ground-truth-pvmap`
2. **Tier 2 (Medium):** Directory search via `--ground-truth-dir`
3. **Tier 3 (Lowest):** Auto-discovery via `--ground-truth-repo`

**Output:**
- `eval_results/diff_results.json` - Raw metrics
- `eval_results/diff.txt` - Detailed diff

**Usage Examples:**

```bash
# Skip evaluation entirely
python src/run_pipeline.py --skip-evaluation

# Use explicit ground truth file (single dataset)
python src/run_pipeline.py --dataset=bis \
    --ground-truth-pvmap=/path/to/bis_pvmap.csv

# Search directory for ground truth files (multiple datasets)
python src/run_pipeline.py \
    --ground-truth-dir=ground_truth/

# Use custom ground truth repository
python src/run_pipeline.py \
    --ground-truth-repo=/path/to/custom/ground_truth
```

**Important Notes:**

- When using `--ground-truth-pvmap` with multiple datasets, only the **first dataset** is evaluated
- The system logs which ground truth source is being used for transparency
- Multiple arguments can be provided; highest tier takes precedence

---

## Common Usage Patterns

### Testing with Test Datasets

Use `test_input/` and `test_output/` directories for testing without affecting production data:

```bash
# Copy datasets to test_input (if not already there)
cp -r input/bis_bis_central_bank_policy_rate test_input/

# Run pipeline with test directories
python src/run_pipeline.py \
    --input-dir=test_input \
    --output-dir=test_output

# View test results
ls test_output/bis_bis_central_bank_policy_rate/
```

### Processing Multiple Datasets

```bash
# Process all datasets
python src/run_pipeline.py

# Process datasets matching a pattern
python src/run_pipeline.py --dataset=census

# Process all Economy category datasets
python src/run_pipeline.py --dataset=bis  # Example: BIS datasets
```

### Resume Interrupted Pipeline

If the pipeline was interrupted:

```bash
# Resume from specific dataset
python src/run_pipeline.py --resume-from=cdc_social_vulnerability_index

# The pipeline will skip all datasets before this one
```

### Regenerate Output

The pipeline skips datasets with existing output. To regenerate:

```bash
# Delete output for specific dataset
rm -rf output/your_dataset_name

# Run pipeline for that dataset
python src/run_pipeline.py --dataset=your_dataset_name
```

### Combine Multiple Options

```bash
# Example: Test with forced resampling and no evaluation
python src/run_pipeline.py \
    --dataset=bis \
    --input-dir=test_input \
    --output-dir=test_output \
    --force-resample \
    --skip-evaluation

# Example: Force schema re-selection and skip sampling
python src/run_pipeline.py \
    --dataset=india_nfhs \
    --force-schema-selection \
    --skip-sampling

# Example: Use custom schema directory
python src/run_pipeline.py \
    --schema-base-dir=/custom/path/to/schemas \
    --force-schema-selection
```

---

## Understanding Pipeline Output

### Output Directory Structure

```
output/{dataset_name}/
├── generated_pvmap.csv           # Main output: Property-Value mapping
├── output_metadata.csv               # Auto-generated metadata config (PVMAP-derived + merged)
├── generation_notes.md           # LLM analysis and reasoning
├── populated_prompt.txt          # Full prompt sent to LLM
├── generated_response/           # LLM response history
│   ├── attempt_0.md              # First attempt (with model info)
│   ├── attempt_0.json            # Attempt metadata (model, tokens, duration)
│   ├── attempt_1.md              # Retry (if validation failed)
│   ├── attempt_1.json
│   └── attempt_2.md              # Final retry (if needed)
├── processed.csv                 # Validated StatVarObservations
├── processed.tmcf                # Template MCF file
├── processed_stat_vars.mcf       # StatVar definitions
└── eval_results/                 # Evaluation metrics (if ground truth found)
    ├── diff_results.json         # Raw metrics
    └── diff.txt                  # Detailed diff
```

### Reading PVMAP Output

The `generated_pvmap.csv` file maps source data columns to Data Commons schema:

```csv
key,property1,value1,property2,value2,property3,value3
REF_AREA,dcid,{Data},,,,
TIME_PERIOD,observationDate,{Data},,,,
OBS_VALUE,value,{Number},,,,
StatVar,variableMeasured,dcid:PolicyInterestRate,observationAbout,{REF_AREA},observationDate,{TIME_PERIOD}
```

### Pipeline Logs

```bash
# Main pipeline log (summary for all datasets)
tail -100 logs/pipeline_*.log

# Dataset-specific log (detailed)
tail -100 logs/your_dataset/generation_*.log
```

---

## Pipeline Summary Output

After completion, the pipeline displays a summary:

```
======================================================================
Pipeline Summary
======================================================================
Total datasets: 4
Processed: 4
Successful: 4 (100%)
Failed: 0

Evaluation: 0 datasets evaluated (no ground truth found)

Completed: 2026-01-15T13:48:55
Log file: logs/pipeline_20260115_134545.log
======================================================================
```

### Understanding the Summary

| Field | Description |
|-------|-------------|
| **Total datasets** | Number of datasets found in input directory |
| **Processed** | Number of datasets processed (excluding skipped) |
| **Successful** | Datasets with successful PVMAP generation and validation |
| **Failed** | Datasets that failed after max retries |
| **Evaluation** | Number of datasets compared against ground truth |

---

## Configuration

### Default Settings

| Setting | Value |
|---------|-------|
| Max retries | 2 (3 total attempts) |
| Default model | `gemini-3-pro-preview` |
| Validation timeout | 5 minutes |
| Generation timeout | 15 minutes |
| Sampling max rows | 100 |
| Sampling rows per key | 5 |

### Modifying Configuration

Configuration is defined in:
- **Sampling:** `*_metadata.csv` (see [INPUT_GUIDE.md](INPUT_GUIDE.md#optional-parameters-sampling-configuration))
- **Pipeline:** `src/run_pipeline.py` (edit script directly)

---

## Monitoring Progress

### Real-Time Log Monitoring

In a separate terminal, monitor pipeline progress:

```bash
# Watch main pipeline log
tail -f logs/pipeline_*.log

# Watch dataset-specific log
tail -f logs/your_dataset/generation_*.log
```

### Check Completed Datasets

```bash
# List all completed datasets
ls output/

# Count completed datasets
ls output/ | wc -l
```

---

## Common Tasks

### Task: Dry Run Before Processing

Preview what will be processed:

```bash
python src/run_pipeline.py --dry-run
```

Output:
```
Found 39 datasets:
- bis_bis_central_bank_policy_rate
- cdc_social_vulnerability_index
- finland_census
...
```

### Task: Process Only Economy Datasets

```bash
# Process datasets with "bis" in name (Economy category)
python src/run_pipeline.py --dataset=bis

# Or process datasets one by one
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate
python src/run_pipeline.py --dataset=commerce_eda
python src/run_pipeline.py --dataset=commodity_market
```

### Task: Regenerate Failed Datasets

If some datasets failed:

```bash
# Check logs for failed datasets
grep "FAILED" logs/pipeline_*.log

# Regenerate specific failed dataset
rm -rf output/failed_dataset_name
python src/run_pipeline.py --dataset=failed_dataset_name
```

### Task: Compare Against Ground Truth

**Option 1: Use Explicit PVMAP File (Single Dataset)**

Best for testing one specific dataset with a known reference:

```bash
# Run pipeline with explicit ground truth file
python src/run_pipeline.py --dataset=bis \
    --ground-truth-pvmap=/path/to/bis_reference_pvmap.csv

# View evaluation results
cat output/bis_bis_central_bank_policy_rate/eval_results/diff.txt
```

**Option 2: Use Ground Truth Directory (Multiple Datasets)**

Best when you have organized ground truth files by dataset name:

```bash
# Directory structure example:
# ground_truth/
# ├── bis_pvmap.csv
# ├── cdc_social_vulnerability_pvmap.csv
# └── finland_census_pvmap.csv

# Run pipeline with ground truth directory
python src/run_pipeline.py \
    --ground-truth-dir=ground_truth/

# View evaluation results for each dataset
cat output/bis_bis_central_bank_policy_rate/eval_results/diff.txt
cat output/cdc_social_vulnerability_index/eval_results/diff.txt
```

**Option 3: Use Bundled Ground Truth (Default)**

The repository includes 81 ground truth datasets in `ground_truth//`:

```bash
# Run pipeline with bundled ground truth (default)
python src/run_pipeline.py

# Or specify custom ground truth repository path
python src/run_pipeline.py --ground-truth-repo=/path/to/custom/ground_truth

# View evaluation results
cat output/your_dataset/eval_results/diff.txt
```

**Understanding Evaluation Metrics:**

After evaluation, check the aggregate metrics in the pipeline summary:

```
Evaluation Metrics:
  Evaluated: 15/20 datasets
  Avg Node Accuracy: 24.5%    # Percentage of nodes that matched exactly
  Avg PV Accuracy: 38.2%      # Percentage of property-value pairs matched
```

---

## Next Steps

After running the pipeline:

1. **Review Output** - Check generated PVMAPs for quality
2. **Evaluate Results** - Compare against ground truth if available
3. **Troubleshooting** - If you encounter issues, see [APPENDIX.md](APPENDIX.md#a-detailed-troubleshooting-guide)
4. **Understand Architecture** - Learn about pipeline design in [APPENDIX.md](APPENDIX.md#b-architecture--workflow-details)

---

## Common Issues

### Issue: Pipeline Skips Datasets

**Behavior:** Pipeline shows "Output already exists, skipping"

**Solution:**
```bash
# Delete existing output to regenerate
rm -rf output/your_dataset_name
python src/run_pipeline.py --dataset=your_dataset_name
```

### Issue: Validation Failed After Max Retries

**Error in logs:** `Validation failed after 2 retries`

**Solution:**
```bash
# Check validation error
cat output/your_dataset/generated_response/attempt_2.md

# Manually inspect PVMAP
cat output/your_dataset/generated_pvmap.csv

# Check metadata configuration
cat input/your_dataset/*_metadata.csv
```

### Issue: Ground Truth Not Found

**Message in logs:** `Ground truth PVMAP not found, skipping evaluation`

**Note:** This is expected behavior if ground truth doesn't exist.

**To verify:**

```bash
# Check which discovery method is being used (check logs)
grep "ground truth" logs/pipeline_*.log

# If using bundled ground truth (default)
ls ground_truth//your_dataset/*_pvmap.csv

# If using --ground-truth-dir
ls /path/to/ground_truth/*your_dataset*pvmap*.csv

# If using --ground-truth-pvmap
ls /path/to/explicit/file.csv
```

**Solutions:**

1. **Skip evaluation** if you don't have ground truth:
   ```bash
   python src/run_pipeline.py --skip-evaluation
   ```

2. **Provide explicit ground truth file** if you have it elsewhere:
   ```bash
   python src/run_pipeline.py --dataset=bis \
       --ground-truth-pvmap=/path/to/known/reference.csv
   ```

3. **Check precedence** if multiple arguments provided:
   - `--ground-truth-pvmap` (highest priority)
   - `--ground-truth-dir` (medium priority)
   - `--ground-truth-repo` (lowest priority, default)

For more troubleshooting, see [APPENDIX.md](APPENDIX.md#a-detailed-troubleshooting-guide).

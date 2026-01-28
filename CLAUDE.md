# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **automated PVMAP (Property-Value Map) generation pipeline** that transforms raw CSV datasets into Data Commons-compatible schema mappings. The pipeline uses LLM-powered generation with validation and self-correction to achieve high accuracy.

**Core Purpose:** Generate PVMAPs that define how to transform source data columns/values into Data Commons StatVarObservations.

## Quick Start Commands

### Environment Setup

```bash
# Install dependencies (choose one)
uv sync                          # Recommended
pip install -r requirements.txt  # Alternative

# Activate virtual environment
source .venv/bin/activate        # uv
source venv/bin/activate         # pip

# Set required environment variables
export PYTHONPATH="$(pwd):$(pwd)/tools:$(pwd)/util"

# Optional: Set Anthropic API key (if not using Claude Code subscription)
export ANTHROPIC_API_KEY="your-api-key-here"

# Optional: Configure ground truth repository path
export GROUND_TRUTH_REPO=/path/to/datacommonsorg-data/ground_truth
```

### Running the Pipeline

```bash
# Process all datasets
python3 run_pvmap_pipeline.py

# Process specific dataset
python3 run_pvmap_pipeline.py --dataset=bis_bis_central_bank_policy_rate

# Test with test directories
python3 run_pvmap_pipeline.py --input-dir=test_input --output-dir=test_output

# Force regenerate samples
python3 run_pvmap_pipeline.py --force-resample

# Skip phases
python3 run_pvmap_pipeline.py --skip-schema-selection --skip-evaluation

# Resume from specific dataset
python3 run_pvmap_pipeline.py --resume-from=cdc_social_vulnerability_index

# Dry run (preview without execution)
python3 run_pvmap_pipeline.py --dry-run
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tools/data_sampler_test.py

# Run with verbose output
pytest -v

# Run tests with coverage
pytest --cov=tools --cov=util
```

### Validation & Debugging

```bash
# Manually validate a PVMAP
PYTHONPATH="$(pwd):$(pwd)/tools:$(pwd)/util" python3 tools/stat_var_processor.py \
  --input_data="input/dataset_name/test_data/input_data.csv" \
  --pv_map="output/dataset_name/generated_pvmap.csv" \
  --config_file="input/dataset_name/metadata.csv" \
  --generate_statvar_name=True \
  --output_path="output/dataset_name/processed"

# Check logs for specific dataset
tail -100 logs/dataset_name/generation_*.log

# Check pipeline logs
tail -100 logs/pipeline_*.log
```

### Schema Selection

```bash
# Run schema selector independently
python3 tools/schema_selector.py --input_dir=input/dataset_name/

# Dry run to see what would be selected
python3 tools/schema_selector.py --input_dir=input/dataset_name/ --dry_run

# Force re-selection
python3 tools/schema_selector.py --input_dir=input/dataset_name/ --force
```

### Data Sampling

```bash
# Run data sampler independently
python3 tools/data_sampler.py \
  --input="input/dataset_name/test_data/input_data.csv" \
  --output="input/dataset_name/test_data/input_data_sampled_data.csv"
```

## Architecture

### Pipeline Workflow

The pipeline consists of 5 phases executed sequentially:

```
Phase 1: Discovery → Phase 2: Sampling → Phase 2.5: Schema Selection
  → Phase 3: PVMAP Generation → Phase 4: Validation → Phase 5: Evaluation
```

**Main Entry Point:** `run_pvmap_pipeline.py` (1,698 lines)

#### Phase 1: Discovery
- Scans `input/` directory for datasets
- Discovers metadata, sampled data, input data, and schema files
- Returns `DatasetInfo` objects with file paths

#### Phase 2: Smart Sampling
- Calls `tools/data_sampler.py` to generate representative samples (max 100 rows)
- Ensures unique value coverage across categorical columns
- Samples numeric ranges across quartiles
- Detects and limits aggregation rows
- Skips if sampled files already exist (unless `--force-resample`)

#### Phase 2.5: Schema Selection
- AI-powered schema category selection from 7 predefined categories
- Uses Gemini API to analyze dataset and select best category
- Copies appropriate schema example files (.txt and .mcf) to dataset directory
- Skips if schema files already exist (unless `--force-schema-selection`)

**Schema Categories:**
- Demographics: Population, age, gender, race, household
- Economy: GDP, business establishments, revenue, trade
- Education: Enrollment, degrees, attainment, literacy
- Employment: Labor force, jobs, wages, unemployment
- Energy: Power generation, consumption, renewable energy
- Health: Disease prevalence, mortality, healthcare access
- School: School metrics, performance, facilities

#### Phase 3: PVMAP Generation
- Populates `tools/improved_pvmap_prompt.txt` template with dataset-specific content
- Replaces placeholders: `{{SCHEMA_EXAMPLES}}`, `{{SAMPLED_DATA}}`, `{{METADATA_CONFIG}}`
- Calls Gemini API to generate PVMAP
- Extracts CSV from response (handles multiple formats)
- Supports up to 3 attempts with error feedback

#### Phase 4: Validation
- Runs `tools/stat_var_processor.py` as subprocess on FULL dataset (not sampled)
- Validates that PVMAP correctly transforms all data
- Returns structured error messages on failure
- Integrated inline within retry loop

#### Phase 5: Evaluation (Optional)
- Compares generated PVMAP against ground truth files
- Calculates diff-based metrics (node accuracy, PV accuracy)
- Generates detailed diff reports
- Gracefully skips if ground truth not found

### Critical Architecture Patterns

#### 1. Retry Loop with Inline Validation (Lines 1340-1415)

**THIS IS THE MOST CRITICAL PATTERN** - understand deeply:

```python
for attempt in range(MAX_RETRIES + 1):  # 3 attempts: 0, 1, 2
    # Generate PVMAP with accumulated error feedback
    generate_pvmap(dataset, prompt, error_feedback, attempt)

    # INLINE VALIDATION - subprocess call
    valid, error = run_validation(dataset)

    if valid:
        # SUCCESS - proceed to evaluation
        evaluate_generated_pvmap(...)
        return True, metrics
    else:
        # FAILURE - sample error logs
        error_feedback = error  # Contains sampled subprocess output

        if attempt >= MAX_RETRIES:
            return False, None  # Max retries exceeded
        # Otherwise loop continues with error_feedback injected
```

**Key points:**
- MAX_RETRIES = 2 (so 3 total attempts)
- Error feedback accumulates across attempts
- Validation runs on FULL dataset, not sampled data
- Error logs are sampled to ~300 lines before feedback

#### 2. Subprocess Integration Pattern

**stat_var_processor.py is NOT imported as a module** - it's called via subprocess:

```python
cmd = [
    python_cmd,
    'tools/stat_var_processor.py',
    f'--input_data={input_file}',      # FULL dataset (not sampled)
    f'--pv_map={dataset.pvmap_path}',  # Generated PVMAP
    f'--config_file={metadata_file}',
    '--generate_statvar_name=True',
    f'--output_path={dataset.output_dir}/processed'
]

result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
```

**Critical requirements:**
- PYTHONPATH must include: BASE_DIR, tools/, util/
- Timeout: 5 minutes (300 seconds)
- Must validate both returncode==0 AND output file has data rows
- Captures both stdout and stderr for error feedback

#### 3. Error Sampling Pattern

Error logs can be 10KB+, so they're sampled before feedback:
- Last 50 lines of error log
- Plus 10 random samples of 5 lines each
- Limits total feedback to ~300 lines
- Keeps prompts within token budget

#### 4. Environment & Path Management

**CRITICAL ORDER** (lines 19-37 of run_pvmap_pipeline.py):
1. Load `.env` FIRST before any imports
2. Set BASE_DIR constant
3. Parse PYTHONPATH environment variable
4. Extend sys.path with parsed paths
5. Then import application code

This ensures:
- API keys loaded from `.env`
- Tool imports resolve correctly
- Relative paths work properly

### Key Components

#### Core Pipeline (`run_pvmap_pipeline.py`)

| Component | Purpose |
|-----------|---------|
| `DatasetInfo` class | Typed object tracking file paths for a dataset |
| `discover_datasets()` | Scan input directory, return list of DatasetInfo objects |
| `prepare_dataset()` | Orchestrate sampling & schema selection |
| `sample_dataset_files()` | Wrapper around data_sampler.py |
| `select_schema_for_dataset()` | Wrapper around schema_selector.py with Gemini |
| `populate_prompt()` | Replace template placeholders with dataset content |
| `generate_pvmap()` | Call Gemini API, save response |
| `extract_pvmap_csv()` | Parse PVMAP CSV from various response formats |
| `extract_log_samples()` | Sample error logs for retry feedback |
| `run_validation()` | Execute stat_var_processor subprocess |
| `evaluate_generated_pvmap()` | Compare vs ground truth, calculate metrics |
| `run_dataset()` | Main retry loop with inline validation |

#### Data Sampler (`tools/data_sampler.py`)

**Purpose:** Generate representative data samples from large CSV files

**Key features:**
- Smart column analysis (detects constant/derived columns)
- Categorical detection (ensures all values covered)
- Numeric coverage (samples across quartiles)
- Aggregation detection (limits total/summary rows)
- Target: 40-80 rows by default
- Highly configurable (50+ config flags)

**Public API:**
```python
from tools.data_sampler import sample_csv_file

sample_csv_file(
    input_path="input/dataset/test_data/input_data.csv",
    output_path="input/dataset/test_data/input_data_sampled_data.csv"
)
```

#### Schema Selector (`tools/schema_selector.py`)

**Purpose:** AI-powered schema category selection

**Key components:**
- `get_category_info()`: Returns descriptions for 7 schema categories
- `generate_data_preview()`: Creates CSV preview for Gemini (max 15 rows)
- `build_prompt()`: Constructs selection prompt
- `invoke_gemini()`: Calls Gemini API, parses response
- `copy_schema_files()`: Copies selected .txt and .mcf files
- `parse_category_response()`: Extracts category (fuzzy matching)

**Public API:**
```python
from tools import schema_selector

category = schema_selector.select_schema_for_directory(
    input_dir="input/dataset_name",
    schema_base_dir="schema_example_files",
    gemini_client=client
)
```

#### StatVar Processor (`tools/stat_var_processor.py`)

**Purpose:** Validate PVMAPs by processing full datasets

**NOT imported as module** - called via subprocess. See subprocess integration pattern above.

**Input:**
- CSV data (full dataset)
- PVMAP CSV (generated)
- Metadata config

**Output:**
- processed.csv (StatVarObservations)
- processed.mcf (StatVar definitions)
- processed.tmcf (Template MCF)

**On failure:** Returns error logs sampled for retry feedback

#### Gemini Client (`util/gemini_client.py`)

**Purpose:** Wrapper around google-genai library

**Key features:**
- Loads API key from `.env`
- Single public method: `generate_content(prompt, temperature, max_tokens) -> str`
- Used by: generate_pvmap(), schema_selector, evaluation

### File Structure Patterns

#### Input Structure

```
input/
├── {dataset_name}/
│   ├── *_metadata.csv              # Config (param,value rows)
│   ├── test_data/
│   │   ├── *_input.csv             # Original full dataset
│   │   └── *_sampled_data.csv      # Generated by data_sampler.py
│   ├── scripts_statvar_llm_config_schema_examples_dc_topic_*.txt  # Schema examples
│   └── scripts_*_vertical_*.mcf    # Schema MCF definitions
```

**Metadata CSV format:** (2-column: parameter, value)
```csv
datasetname,Central Bank Policy Rate
source,Bank for International Settlements
unit,Percent Per Annum
country,Multiple
```

#### Output Structure

```
output/
├── {dataset_name}/
│   ├── generated_pvmap.csv         # Final PVMAP output
│   ├── generation_notes.md         # Full reasoning + attempt history
│   ├── populated_prompt.txt        # Actual prompt sent to Gemini
│   ├── processed.csv               # Validation output (observations)
│   ├── processed.mcf               # MCF definitions
│   ├── processed.tmcf              # Template MCF
│   ├── generated_response/
│   │   ├── attempt_0.md            # First attempt response
│   │   ├── attempt_1.md            # Retry response (if needed)
│   │   └── attempt_2.md            # Final retry response (if needed)
│   └── eval_results/               # Evaluation (if ground truth found)
│       ├── diff_results.json       # Raw metrics
│       └── diff.txt                # Detailed diff
```

#### PVMAP CSV Format

```csv
key,property1,value1,property2,value2,...
State FIPS Code,StateFIPS,{Data},,
Year,observationDate,{Data},,
Population,populationType,Person,measuredProperty,count,value,{Number}
```

**Key points:**
- First column: data key (column header or cell value to match)
- Odd columns: property names
- Even columns: values
- `{Data}` = pass-through value from data
- `{Number}` = numeric value from data
- Special syntax: `COLUMN:VALUE` for column-specific mappings

### Google ADK Migration (In Progress)

**Status:** Planning phase - 709-line plan with 196 checklist items

**Target architecture:**
```
PipelineCoordinator (LlmAgent)
├── DiscoveryAgent
├── SamplingAgent
├── SchemaSelectionAgent
├── PVMAPGenerationAgent (with retry loop)
└── EvaluationAgent
```

**Key files:**
- `google_adk_python/plan.md` - Comprehensive migration plan
- `src/` - New ADK agent framework (in progress)
- `.claude/skills/google-adk/` - ADK skill definitions

**Critical requirement:** Preserve exact retry loop logic from lines 1374-1415 of run_pvmap_pipeline.py

## Important Patterns & Best Practices

### MUST-KNOW Patterns

1. **Order matters:**
   - Load .env BEFORE any imports
   - Set BASE_DIR BEFORE path manipulation
   - Run data_sampler BEFORE schema_selector
   - Run schema_selector BEFORE PVMAP generation

2. **Subprocess integration:**
   - stat_var_processor is NOT imported as module
   - Called via subprocess.run() with PYTHONPATH setup
   - TIMEOUT: 5 minutes (300 seconds)
   - Must validate both returncode==0 AND output file has data

3. **Error feedback must be sampled:**
   - Do NOT pass full 10KB+ error logs to LLM
   - Sample: last 50 lines + 10 random 5-line samples
   - Limits feedback to ~300 lines max

4. **Retry loop is stateful:**
   - error_feedback accumulates across attempts
   - Attempt counter increments and is logged
   - Generated responses saved per-attempt for debugging
   - Notes file updated with all attempts

5. **File path patterns are strict:**
   - Metadata: `*_metadata.csv`
   - Sampled data: `*_sampled_data.csv`
   - Input data: `*_input.csv`
   - Schema examples: `scripts_statvar_llm_config_schema_examples_dc_topic_*.txt`
   - Schema MCF: `scripts_*_vertical_*.mcf`

### Common Pitfalls to Avoid

1. **Don't run validation on sampled data** - Must use FULL original data
2. **Don't hardcode paths** - Use Path objects and BASE_DIR for portability
3. **Don't forget PYTHONPATH** - stat_var_processor subprocess needs proper paths
4. **Don't mix sampled/original data** - Keep files clearly separated
5. **Don't modify original input files** - Always write to output/ or temp locations
6. **Don't trust LLM category parsing** - Use fuzzy matching with validation
7. **Don't assume schema files exist** - Check existence first (e.g., School category may be missing)

### CSV Extraction from LLM Output

The pipeline supports multiple CSV formats from LLM responses:

1. Code block with marker: ` ```csv ... ``` `
2. Code block without marker: ` ``` ... ``` `
3. Inline CSV (raw CSV text)
4. Passthrough format (observationAbout, observationDate, variableMeasured, value)

**Passthrough detection:** If CSV contains `observationAbout` header, automatically injects `key,property,value` header if needed.

### Pre-Formatted Data Commons Data

**Critical:** The prompt template (`tools/improved_pvmap_prompt.txt`) includes explicit instructions for detecting pre-formatted Data Commons data.

**Detection criteria:**
- Has `variableMeasured` column with DCID values
- Has `observationAbout` column with place DCIDs
- Has `observationDate` column with standard formats
- Has `value` column with measurements

**If detected, use passthrough mapping:**
```csv
key,property,value
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
variableMeasured,variableMeasured,{Data}
value,value,{Number}
```

## Logging & Debugging

### Logging Strategy

**Two-level logging:**
- Global logger: `logs/pipeline_{timestamp}.log` (DEBUG level)
- Per-dataset logger: `logs/{dataset_name}/generation_{timestamp}.log` (DEBUG level)
- Console: INFO level only

**Key log locations:**
- `logs/` - Global pipeline logs
- `logs/{dataset_name}/` - Per-dataset generation logs
- `output/{dataset_name}/generation_notes.md` - Human-readable notes with all attempts
- `output/{dataset_name}/generated_response/` - Raw LLM responses per attempt

### Debugging Failed Runs

```bash
# 1. Check pipeline log
tail -100 logs/pipeline_*.log

# 2. Check dataset-specific log
tail -100 logs/{dataset_name}/generation_*.log

# 3. Check generation notes
cat output/{dataset_name}/generation_notes.md

# 4. Check LLM responses
ls output/{dataset_name}/generated_response/

# 5. Manually validate PVMAP
PYTHONPATH="$(pwd):$(pwd)/tools:$(pwd)/util" python3 tools/stat_var_processor.py \
  --input_data="input/{dataset}/test_data/*_input.csv" \
  --pv_map="output/{dataset}/generated_pvmap.csv" \
  --config_file="input/{dataset}/*_metadata.csv" \
  --generate_statvar_name=True \
  --output_path="output/{dataset}/processed"
```

## Configuration

### Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `PYTHONPATH` | Path resolution for imports | Yes |
| `ANTHROPIC_API_KEY` | Anthropic API key for LLM calls | If not using Claude Code subscription |
| `GROUND_TRUTH_REPO` | Path to ground truth repository | No (defaults to ../datacommonsorg-data/ground_truth) |

### Command-Line Flags

**Phase control:**
- `--skip-sampling` - Use existing sampled files
- `--force-resample` - Always re-run data sampler
- `--skip-schema-selection` - Use existing schema files
- `--force-schema-selection` - Always re-run schema selection
- `--skip-evaluation` - Skip evaluation phase

**Dataset selection:**
- `--dataset` - Process specific dataset
- `--resume-from` - Resume from specific dataset

**Directory overrides:**
- `--input-dir` - Override input directory (default: input/)
- `--output-dir` - Override output directory (default: output/)
- `--schema-base-dir` - Override schema directory (default: schema_example_files/)

**Ground truth:**
- `--ground-truth-pvmap` - Explicit single PVMAP file
- `--ground-truth-dir` - Directory with ground truth files
- `--ground-truth-repo` - Ground truth repository path

**Model selection:**
- `--model` or `-m` - Override default Gemini model (default: gemini-3-pro-preview)

**Other:**
- `--dry-run` - Preview without execution
- `--verbose` - Enable verbose logging

## Project Context

**Purpose:** POC for automated Data Commons schema generation using Claude Code CLI

**Status:** Production-ready with 100% success rate on test datasets

**Key metrics:**
- 39 datasets across 6 domains
- Average processing time: ~45 seconds per dataset
- PV Accuracy improvement: +18.7% vs Gemini baseline (26.8% vs 8.1%)

**Documentation:**
- README.md - Complete overview
- docs/SETUP.md - Installation guide
- docs/INPUT_GUIDE.md - Input file structure
- docs/USAGE.md - Usage guide
- docs/APPENDIX.md - Troubleshooting & architecture
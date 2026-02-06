# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **automated PVMAP (Property-Value Map) generation pipeline** that transforms raw CSV datasets into Data Commons-compatible schema mappings. The pipeline uses LLM-powered generation with validation and self-correction to achieve high accuracy.

**Core Purpose:** Generate PVMAPs that define how to transform source data columns/values into Data Commons StatVarObservations.

## Quick Start Commands

### Environment Setup

```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate

# Set required environment variables
export PYTHONPATH="$(pwd):$(pwd)/src"

# Optional: Set Anthropic API key (if not using Claude Code subscription)
export ANTHROPIC_API_KEY="your-api-key-here"

# Optional: Configure ground truth repository path (defaults to ground_truth/)
export GROUND_TRUTH_REPO=/path/to/ground_truth
```

### Running the Pipeline

**Primary Entry Point:** `src/run_pipeline.py` (ADK-based pipeline)

```bash
# Process specific dataset (recommended)
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate

# Process with structured output (deterministic CSV)
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --structured-output

# Skip sampling phase (use existing sampled files)
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --skip-sampling

# Skip schema selection phase
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --skip-schema-selection

# Skip evaluation phase (no ground truth comparison)
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --skip-evaluation

# Use explicit ground truth file
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate \
  --ground-truth-pvmap=ground_truth/bis_bis_central_bank_policy_rate/pvmap.csv

# Dry run (preview without execution)
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --dry-run

# Force resample data
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --force-resample

# Use different model
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --model=gemini-2.5-pro

# Enable MCP integration for StatVar discovery
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --enable-mcp
```


### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest src/pipeline/sampling/data_sampler_test.py

# Run with verbose output
pytest -v

# Run tests with coverage
pytest --cov=src
```

### Validation & Debugging

```bash
# Manually validate a PVMAP
PYTHONPATH="$(pwd):$(pwd)/src" python3 tools/stat_var_processor.py \
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

### Directory Structure

The codebase follows a domain-based organization under `src/`:

```
src/
├── agents/                          # Google ADK agents
├── config/                          # CLI parsing
├── state/                           # State management
│
├── infrastructure/                  # Core platform services
│   ├── io/                         # File I/O (file_util, gcs_file, download_util)
│   ├── logging/                    # Logging (log_util, logging_config)
│   ├── config/                     # Configuration (config_map, config_flags)
│   ├── metrics/                    # Metrics (counters, timer)
│   └── utils/                      # Utilities (aggregation_util)
│
├── data_commons/                    # Data Commons modules
│   ├── api/                        # DC API (gemini_client, dc_api_wrapper)
│   ├── mcf/                        # MCF utilities (mcf_dict_util, mcf_file_util, mcf_diff)
│   ├── schema/                     # Schema generation (schema_generator, schema_resolver, etc.)
│   ├── statvar/                    # StatVar utilities (statvar_dcid_generator)
│   ├── place/                      # Place resolution (place_resolver, place_name_matcher)
│   ├── geo/                        # Geographic coding (alpha2_to_dcid, county_to_dcid)
│   └── codes/                      # Industry/occupation codes (naics_codes, soc_codes_names)
│
├── pipeline/                        # Pipeline-specific tools
│   ├── sampling/                   # Data sampling (data_sampler, column_analyzer)
│   ├── schema_selection/           # Schema selection (schema_selector)
│   ├── validation/                 # Validation (stat_var_processor, validation_tool)
│   ├── evaluation/                 # Evaluation tools
│   │   └── scripts/               # CLI scripts (evaluate_pvmap_diff, generate_*_metrics)
│   └── logging/                    # Logging tools
│
├── processing/                      # Data processing
│   ├── mapping/                    # Property-value mapping (property_value_mapper)
│   ├── filtering/                  # Data filtering (filter_data_outliers)
│   ├── transformation/             # Data transformation (json_to_csv)
│   ├── evaluation/                 # Eval functions
│   └── matching/                   # Matching utilities
│
├── compatibility/                   # Backward compatibility layer
│   ├── util_compat.py              # Re-exports from old util/
│   └── tools_compat.py             # Re-exports from old tools/
│
└── resources/                       # Static resources
    ├── schema_examples/            # Schema example files by category
    │   ├── Demographics/
    │   ├── Economy/
    │   ├── Education/
    │   ├── Employment/
    │   ├── Energy/
    │   └── Health/
    ├── prompts/                    # Prompt templates
    │   └── improved_pvmap_prompt.txt
    └── test_data/                  # Shared test fixtures

ground_truth/                        # Ground truth PVMAPs for evaluation (81 datasets)
└── {dataset_name}/                  # One directory per dataset
```

**Note:** The legacy `util/` and `tools/` directories are preserved for backward compatibility during the transition period.

### Pipeline Workflow

The pipeline consists of 5 phases executed sequentially:

```
Phase 1: Discovery → Phase 2: Sampling → Phase 2.5: Schema Selection
  → Phase 3: PVMAP Generation → Phase 4: Validation → Phase 5: Evaluation
```

**Main Entry Point:** `src/run_pipeline.py` (ADK-based pipeline)

#### Phase 1: Discovery
- Scans `input/` directory for datasets
- Discovers metadata, sampled data, input data, and schema files
- Returns `DatasetInfo` objects with file paths

#### Phase 2: Smart Sampling
- Calls `src/pipeline/sampling/data_sampler.py` to generate representative samples (max 100 rows)
- Ensures unique value coverage across categorical columns
- Samples numeric ranges across quartiles
- Detects and limits aggregation rows
- Skips if sampled files already exist (unless `--force-resample`)

#### Phase 2.5: Schema Selection
- AI-powered schema category selection from 7 predefined categories
- Uses Gemini API to analyze dataset and select best category
- Copies appropriate schema example files (.txt and .mcf) to dataset directory
- Schema examples located in `src/resources/schema_examples/`
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
- Populates `src/resources/prompts/improved_pvmap_prompt.txt` template with dataset-specific content
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
- PYTHONPATH must include: BASE_DIR, src/
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

**CRITICAL ORDER** (in src/run_pipeline.py):
1. Load `.env` FIRST before any imports
2. Set BASE_DIR constant
3. Parse PYTHONPATH environment variable
4. Extend sys.path with parsed paths
5. Then import application code

This ensures:
- API keys loaded from `.env` (takes priority over environment variables)
- Tool imports resolve correctly
- Relative paths work properly

### Key Components

#### Core Pipeline (`src/run_pipeline.py`)

| Component | Purpose |
|-----------|---------|
| `DatasetInfo` class | Typed object tracking file paths for a dataset |
| `discover_datasets()` | Scan input directory, return list of DatasetInfo objects |
| `prepare_dataset()` | Orchestrate sampling & schema selection |
| `sample_dataset_files()` | Run agentic sampling via sampling_interface |
| `select_schema_for_dataset()` | Wrapper around schema_selector.py with Gemini |
| `populate_prompt()` | Replace template placeholders with dataset content |
| `generate_pvmap()` | Call Gemini API, save response |
| `extract_pvmap_csv()` | Parse PVMAP CSV from various response formats |
| `extract_log_samples()` | Sample error logs for retry feedback |
| `run_validation()` | Execute stat_var_processor subprocess |
| `evaluate_generated_pvmap()` | Compare vs ground truth, calculate metrics |
| `run_dataset()` | Main retry loop with inline validation |

#### Agentic Data Sampler (`src/pipeline/sampling/sampling_interface.py`)

**Purpose:** LLM-driven data sampling with skeleton_summary generation

**Key features:**
- LLM-driven column classification (place, time, dimension, value)
- Generates skeleton_summary for downstream PVMAP prompt
- Generates data_context.json with structural analysis
- Caches results for fast subsequent runs
- Target: 60-100 rows with intelligent sampling strategies

**Public API:**
```python
from src.pipeline.sampling.sampling_interface import sample_dataset, SamplingResult

result = sample_dataset(
    input_files=[Path("input/dataset/test_data/input_data.csv")],
    output_dir=Path("output/dataset")
)
# result.sampled_file - Path to agentic_sampled.csv
# result.skeleton_summary - Markdown for PVMAP prompts
# result.data_context - Structural analysis dict
```

#### Schema Selector (`tools/schema_selector.py`)

**Purpose:** AI-powered schema category selection

**Key components:**
- `get_category_info()`: Returns descriptions for 7 schema categories
- `generate_data_preview()`: Creates CSV preview for Gemini (max 15 rows)
- `build_prompt()`: Constructs selection prompt
- `invoke_gemini()`: Calls Gemini API, parses response
- `copy_schema_files()`: Copies selected .txt and .mcf files from `src/resources/schema_examples/`
- `parse_category_response()`: Extracts category (fuzzy matching)

**Public API:**
```python
from tools import schema_selector

category = schema_selector.select_schema_for_directory(
    input_dir="input/dataset_name",
    schema_base_dir="src/resources/schema_examples",
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

#### Gemini Client (`src/data_commons/api/gemini_client.py`)

**Purpose:** Wrapper around google-genai library

**Key features:**
- Loads API key from `.env` file (takes priority over environment variables)
- Single public method: `generate_content(prompt, temperature, max_tokens) -> str`
- Used by: generate_pvmap(), schema_selector, evaluation

**Public API:**
```python
from src.data_commons.api.gemini_client import GeminiClient

client = GeminiClient(model_name="gemini-2.5-flash")
response = client.generate_content(prompt, temperature=0)
```

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

### Google ADK Migration

**Status:** Migration 70% complete (Weeks 1-7 done)

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
- `.claude/plans/vectorized-cuddling-scone.md` - Comprehensive migration plan
- `src/agents/` - ADK agents (5/5 implemented)
- `src/state/` - State management (DatasetInfo, DatasetRegistry)
- `src/run_pipeline.py` - ADK pipeline runner

**Migration Progress:**
- ✅ Week 1: Resources moved to `src/resources/`
- ✅ Week 2: Infrastructure layer (`src/infrastructure/`)
- ✅ Week 3: Data Commons API (`src/data_commons/api/`, `mcf/`, `statvar/`, `codes/`)
- ✅ Week 4: Schema & Place (`src/data_commons/schema/`, `place/`)
- ✅ Week 5: Pipeline layer (`src/pipeline/sampling/`, `validation/`)
- ✅ Week 6: Processing modules (`src/processing/`)
- ✅ Week 7: Evaluation scripts moved to `src/pipeline/evaluation/scripts/`
- ⏳ Week 8-10: Test suite reorganization, documentation, cleanup

**Critical requirement:** Retry loop logic is implemented in `src/agents/pvmap_retry_loop.py`

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

6. **API key loading priority:**
   - `.env` file takes priority over environment variables
   - Ensures fresh keys from `.env` are used even if stale keys are in shell environment

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

**Critical:** The prompt template (`src/resources/prompts/improved_pvmap_prompt.txt`) includes explicit instructions for detecting pre-formatted Data Commons data.

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
PYTHONPATH="$(pwd):$(pwd)/src" python3 tools/stat_var_processor.py \
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
| `GEMINI_API_KEY` | Gemini API key (loaded from .env first) | Yes |
| `ANTHROPIC_API_KEY` | Anthropic API key for LLM calls | If not using Claude Code subscription |
| `GROUND_TRUTH_REPO` | Path to ground truth repository | No (defaults to ground_truth/) |

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
- `--schema-base-dir` - Override schema directory (default: src/resources/schema_examples/)

**Ground truth:**
- `--ground-truth-pvmap` - Explicit single PVMAP file
- `--ground-truth-dir` - Directory with ground truth files
- `--ground-truth-repo` - Ground truth repository path

**Model selection:**
- `--model` or `-m` - Override default Gemini model (default: gemini-3-pro-preview)

**Other:**
- `--dry-run` - Preview without execution
- `--verbose` - Enable verbose logging

## Key Import Path Changes

After the refactoring migration, use these new import paths:

| Old Import | New Import |
|------------|------------|
| `from util.gemini_client import GeminiClient` | `from src.data_commons.api.gemini_client import GeminiClient` |
| `from util.file_util import ...` | `from src.infrastructure.io.file_util import ...` |
| `from util.config_map import ConfigMap` | `from src.infrastructure.config.config_map import ConfigMap` |
| `from util.counters import Counters` | `from src.infrastructure.metrics.counters import Counters` |
| `from tools import schema_selector` | `from src.pipeline.schema_selection import schema_selector` |
| `from tools.property_value_mapper import ...` | `from src.processing.mapping.property_value_mapper import ...` |

**Sampling (Agentic-only):**
```python
from src.pipeline.sampling.sampling_interface import sample_dataset, SamplingResult

result = sample_dataset(
    input_files=[Path("input.csv")],
    output_dir=Path("output/")
)
```

**Note:** Legacy imports via `util/` still work via the compatibility layer. Legacy heuristic-based sampling has been removed in favor of agentic (LLM-driven) sampling.

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

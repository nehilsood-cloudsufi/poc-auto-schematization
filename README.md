# Auto-Schematization POC: Automated PVMAP Pipeline

## Overview

This repository implements an **end-to-end automated pipeline** for generating Property-Value Maps (PVMAPs) that transform source data into Data Commons schema using Google ADK with Gemini.

### What This Pipeline Does

```
Input CSV + Metadata → Auto-Sampling → Schema Selection → PVMAP Generation → Validation → Evaluation → StatVarObservations
```

**Key Features:**
- 🤖 **Fully Automated** - One command processes entire dataset lifecycle
- 📊 **Smart Sampling** - Automatically generates representative data samples
- 🧠 **Intelligent Schema Selection** - AI-powered category selection from 7 schema types
- 🔄 **Retry Logic** - Self-corrects validation errors with LLM feedback
- ✅ **Built-in Validation** - Automatic validation with stat_var_processor.py
- 📈 **Evaluation** - Compares against ground truth with diff-based metrics
- 🎯 **100% Success Rate** - Tested on 4 diverse datasets (BIS, CDC, Finland Census, WHO COVID-19)

### Quick Stats

| Metric | Value |
|--------|-------|
| **Total Datasets** | 39 (Economy, Health, Demographics, Education, Employment, Energy) |
| **Automated Phases** | 5 (Sampling → Schema Selection → Generation → Validation → Evaluation) |
| **Average Processing Time** | ~45 seconds per dataset |
| **Success Rate** | 100% on test datasets |
| **PV Accuracy vs Gemini** | +18.7% improvement (26.8% vs 8.1%) |

---

## Documentation

📚 **Complete documentation is organized into specialized guides:**

| Guide | Description | Use When |
|-------|-------------|----------|
| **[SETUP.md](docs/SETUP.md)** | Installation and environment setup | First-time setup, troubleshooting environment issues |
| **[INPUT_GUIDE.md](docs/INPUT_GUIDE.md)** | Input file structure and requirements | Preparing datasets, understanding metadata configuration |
| **[USAGE.md](docs/USAGE.md)** | Running the pipeline and common tasks | Running your first pipeline, daily usage |
| **[APPENDIX.md](docs/APPENDIX.md)** | Detailed troubleshooting and architecture | Debugging issues, understanding internals |
| **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** | Cloud Run deployment guide | Deploying the Streamlit UI to Google Cloud Run |
| **[mcp_integration.md](docs/mcp_integration.md)** | MCP integration details | Using Data Commons MCP for StatVar discovery |

---

## Quick Start (5 Minutes)

### Prerequisites

- Python 3.12+ installed
- **Gemini API key** (required for LLM calls via Google ADK)
- **uv** package manager ([installation guide](https://github.com/astral-sh/uv))

### Installation

```bash
# Clone repository
git clone <repository-url> poc-auto-schematization
cd poc-auto-schematization

# Install dependencies
uv sync --all-extras

# Activate virtual environment
source .venv/bin/activate

# Set environment variables
echo 'GEMINI_API_KEY=your-gemini-api-key-here' > .env
export PYTHONPATH="$(pwd):$(pwd)/src"
```

### Option A: Run via Command Line

```bash
# Process a dataset
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate

# Check results
ls output/bis_bis_central_bank_policy_rate/
```

### Option B: Run via Web UI

```bash
# Launch the Streamlit UI at http://localhost:8501
PYTHONPATH="$(pwd):$(pwd)/src" streamlit run src/ui/app.py
```

Upload your CSV, click "Generate PVMAP", and review results in the browser. See [Running the Web UI](#running-the-web-ui-streamlit) below for the full walkthrough.

### Common CLI Options

```bash
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --skip-sampling    # Use existing samples
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --skip-evaluation  # Skip GT comparison
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --dry-run          # Preview only
```

**See [USAGE.md](docs/USAGE.md) for all CLI options.**

---

## Project Configuration

**Selected Configuration:**
- **Primary Dataset:** BIS Central Bank Policy Rate (SDMX data)
- **Repository Location:** Isolated repository (`~/poc-auto-schematization`)
- **Evaluation Benchmark:** Metrics from Auto_Schematization_Evaluation_Benchmark.docx
- **LLM:** Gemini 3 Pro Preview (via Google ADK)
- **Comparison Baseline:** Gemini-based approach (from benchmark)

---

## Key Concepts

### What is a PVMAP?

A Property-Value map (`pvmap.csv`) defines how to transform source data columns/values into Data Commons schema:

```csv
key,property1,value1,property2,value2
State FIPS Code,StateFIPS,{Data},,
Year,observationDate,{Data},,
Population,populationType,Person,measuredProperty,count,value,{Number}
```

### What is Auto-Sampling?

The pipeline automatically generates representative data samples (max 100 rows) from large datasets:
- **Smart column analysis** - Skips constant/derived columns
- **Categorical coverage** - Ensures all values represented
- **Numeric range coverage** - Samples across quartiles
- **Aggregation detection** - Limits total/summary rows

**See [INPUT_GUIDE.md](docs/INPUT_GUIDE.md#5-sampled-data-files-auto-generated) for detailed scenarios.**

### What is StatVar Processor?

The main validation tool that:
- **Input:** CSV data + PV map + config
- **Output:** MCF files + observations CSV + TMCF template
- **Validates** that PV map correctly transforms all data

---

## Repository Structure

```
poc-auto-schematization/
├── src/                          # Source code
│   ├── agents/                   # Google ADK agents (10+ agents)
│   ├── config/                   # CLI configuration
│   ├── state/                    # State management (DatasetInfo, context)
│   ├── infrastructure/           # Core utilities (io, config, metrics, logging)
│   ├── data_commons/             # Data Commons modules (api, mcf, schema, place, codes)
│   ├── pipeline/                 # Pipeline operations (sampling, validation, evaluation)
│   ├── processing/               # Data processing (mapping, filtering, transformation)
│   ├── tools/                    # ADK tool wrappers
│   ├── ui/                       # Streamlit web UI (app, components, services)
│   ├── utils/                    # Shared utilities (artifact_plugin, template_utils)
│   └── resources/                # Static resources (prompts, schema_examples, schema_org)
├── tests/                        # Test suite (~982 tests)
├── input/                        # Datasets with input data & metadata
├── output/                       # Generated PVMAPs (created automatically)
├── ground_truth/                 # Ground truth PVMAPs for evaluation
├── deploy/                       # Cloud Run deployment scripts
├── tools/                        # Legacy processing tools (compatibility layer)
├── logs/                         # Pipeline logs (created automatically)
├── Dockerfile                    # Container image for Cloud Run
├── pyproject.toml                # Dependency definitions (source of truth)
├── src/run_pipeline.py           # Main pipeline script (ADK-based)
├── docs/                         # Documentation
│   ├── SETUP.md                  # Installation guide
│   ├── INPUT_GUIDE.md            # Input structure guide
│   ├── USAGE.md                  # Usage guide
│   ├── APPENDIX.md               # Troubleshooting & architecture
│   ├── DEPLOYMENT.md             # Cloud Run deployment
│   └── mcp_integration.md        # MCP integration details
└── README.md                     # This file
```

---
## Pipeline Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Auto-Sampling (Optional)                           │
│ • LLM-driven agentic sampling (max 100 rows)               │
│ • Generates skeleton_summary + data_context.json            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 1.5: Schema Selection (Optional)                      │
│ • Analyzes skeleton_summary using Gemini API                │
│ • Selects best schema category from 7 options               │
│ • Copies schema files to dataset's schema/ subdirectory     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: PVMAP Generation (via Google ADK LoopAgent)        │
│ • Populates prompt with schema vocab + sampled data         │
│ • Calls Gemini API via ADK LlmAgent                         │
│ • Generates property-value mapping                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2.5: Metadata Generation + PVMAP Repair               │
│ • Auto-generates output_metadata.csv from PVMAP             │
│ • Programmatic key repair (case, whitespace, fuzzy match)   │
│ • Pre-validation to skip obviously broken PVMAPs            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Validation + Quality Evaluation                    │
│ • Runs stat_var_processor.py on full dataset                │
│ • Quality evaluation (heuristic + ground truth metrics)     │
│ • Retries with context-aware feedback if quality is low     │
│ • Stagnation detection stops retries when no improvement    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: Evaluation (Optional)                              │
│ • Searches for ground truth PVMAP (three-tier precedence)   │
│ • Compares generated vs ground truth                        │
│ • Generates diff-based metrics (node + PV accuracy)         │
│ • Gracefully skips if ground truth not found                │
└─────────────────────────────────────────────────────────────┘
```

**See [APPENDIX.md](docs/APPENDIX.md#b-architecture--workflow-details) for detailed architecture.**

---

## SDMX Mode (optional)

Set when ingesting an **SDMX 2.1** dataset. The pipeline uses the DSD (Data Structure Definition) as authoritative context instead of re-inferring structure from the CSV.

### How to enable

- **Dashboard:** On the Upload step, switch the "Dataset Type" toggle to "SDMX" and attach the structure XML (downloaded with `references=all`) alongside the CSV.
- **API:** `POST /api/upload` with `sdmx_mode=true` + an `sdmx_metadata_xml` multipart field, or drop `input_metadata.xml` into the run's input directory and the pipeline auto-detects it.
- **Library:** `run_dataset_pipeline(..., sdmx_mode=True, sdmx_metadata_xml_path=...)`.

### What changes

| Stage | Normal mode | SDMX mode |
|---|---|---|
| Schema selection | Classifies into one of 7 DC categories | **Skipped** — SDMX has its own concept schemes |
| Skeleton | Derived from `data_context` (column roles, sample-inferred) | Derived from DSD (dimensions/attributes/measures + codelists) |
| Prompt | `improved_pvmap_prompt_v3.txt` | `improved_pvmap_prompt_sdmx_v1.txt` (trusts DSD; skips archetype classification) |
| Mapping plan | `mapping_plan_prompt_v2.txt` with Phase A analysis | `mapping_plan_prompt_sdmx_v1.txt` primed with the DSD |
| Sampling | ~100 rows | ~100 rows (unchanged — codelists cover enumeration separately) |

### Key files

- `src/tools/sdmx_metadata_extractor.py` — parses SDMX-ML 2.1 → simplified JSON (compatible with DC's `agentic_import` extractor schema, Apache 2.0).
- `src/agents/sdmx_context.py` — renders the JSON into the `{{SDMX_STRUCTURE}}` prompt block and a deterministic PVMAP skeleton.
- `src/resources/prompts/improved_pvmap_prompt_sdmx_v1.txt` — SDMX PVMAP generator prompt.
- `src/resources/prompts/mapping_plan_prompt_sdmx_v1.txt` — SDMX mapping plan prompt.

---

## Schema Selection (Phase 1.5)

The pipeline includes **automated schema selection** that intelligently analyzes your dataset and selects the most appropriate schema category from 7 predefined options.

### How It Works

1. **Analyze Dataset** - Examines skeleton_summary from sampling phase
2. **Invoke Gemini API** - Uses Gemini to intelligently classify dataset into one of 7 categories
3. **Copy Schema Files** - Copies the appropriate `.txt` and `.mcf` files to dataset's `schema/` subdirectory
4. **Skip if Exists** - Automatically skips if schema files already present

### Available Schema Categories

| Category | Description | Example Topics |
|----------|-------------|----------------|
| **Demographics** | Population, age, gender, race, household, nativity data | Census data, population statistics |
| **Economy** | GDP, business establishments, revenue, trade, commodities | Economic indicators, business metrics |
| **Education** | School enrollment, degrees, educational attainment, literacy | Educational statistics, enrollment data |
| **Employment** | Labor force, jobs, wages, unemployment, occupations | BLS data, labor statistics |
| **Energy** | Power generation, consumption, renewable energy, infrastructure | Energy production, consumption data |
| **Health** | Disease prevalence, mortality, healthcare access, medical conditions | Health indicators, disease data |
| **School** | School-specific metrics, performance, facilities, student-teacher ratios | School performance, facilities data |

### Usage

```bash
# Automatic schema selection (default)
python src/run_pipeline.py

# Skip schema selection (use existing schema files)
python src/run_pipeline.py --skip-schema-selection

# Force re-selection even if schema files exist
python src/run_pipeline.py --force-schema-selection

# Use custom schema directory
python src/run_pipeline.py --schema-base-dir=/path/to/schemas
```

### Standalone Usage

The schema selector can also be run independently:

```bash
# Run schema selector independently
python3 src/pipeline/schema_selection/schema_selector.py --input_dir=input/dataset_name/

# Dry run to see what would be selected
python3 src/pipeline/schema_selection/schema_selector.py --input_dir=input/dataset_name/ --dry_run

# Force re-selection
python3 src/pipeline/schema_selection/schema_selector.py --input_dir=input/dataset_name/ --force
```

### Output

After schema selection, your dataset directory will include:

```
input/dataset_name/
├── test_data/
│   └── *_input.csv
└── schema/                                                              # ← Added
    ├── scripts_statvar_llm_config_schema_examples_dc_topic_{Category}.txt
    └── schema_vocab.json
```

---

## Ground Truth Evaluation (Phase 5)

The pipeline includes **automated evaluation** that compares generated PVMAPs against ground truth files to measure accuracy.

### How It Works

The evaluation system uses a **three-tier precedence** for finding ground truth PVMAPs:

1. **Tier 1 (Highest)**: Explicit single file (`--ground-truth-pvmap`)
2. **Tier 2 (Medium)**: Directory search (`--ground-truth-dir`)
3. **Tier 3 (Lowest)**: Auto-discovery from repository structure (`--ground-truth-repo`)

### Ground Truth Options

| Option | Description | Use When |
|--------|-------------|----------|
| `--ground-truth-pvmap` | Path to a single ground truth PVMAP file | Testing one specific dataset with a known reference file |
| `--ground-truth-dir` | Path to directory containing multiple ground truth files | You have organized ground truth files by dataset name |
| `--ground-truth-repo` | Path to ground truth repository | Using bundled ground truth (default: ground_truth/) |
| `--skip-evaluation` | Skip evaluation phase entirely | You don't have ground truth files or don't need metrics |

### Default Configuration

The default ground truth repository path can be configured in three ways (in order of precedence):

1. **Command-line argument**: `--ground-truth-repo=/path/to/ground_truth`
2. **Environment variable**: `export GROUND_TRUTH_REPO=/path/to/ground_truth`
3. **Fallback default**: `ground_truth/` (bundled with repository)

**Example: Set via environment variable**
```bash
# Set for current session (optional - uses bundled ground truth by default)
export GROUND_TRUTH_REPO=/path/to/custom/ground_truth

# Or add to your shell profile for persistence
echo 'export GROUND_TRUTH_REPO=/path/to/custom/ground_truth' >> ~/.zshrc
source ~/.zshrc
```

### Usage Examples

```bash
# Use explicit PVMAP file for single dataset
python src/run_pipeline.py --dataset=bis \
    --ground-truth-pvmap=/path/to/bis_pvmap.csv

# Search directory for ground truth files (matches by dataset name)
python src/run_pipeline.py \
    --ground-truth-dir=ground_truth/

# Use custom ground truth repository
python src/run_pipeline.py \
    --ground-truth-repo=/path/to/custom/ground_truth

# Skip evaluation entirely
python src/run_pipeline.py --skip-evaluation

# Multiple datasets with single ground truth file
# (Warning: uses file for first dataset only, skips rest)
python src/run_pipeline.py \
    --ground-truth-pvmap=/path/to/reference.csv
```

### Precedence Behavior

When multiple ground truth arguments are provided, the system follows strict precedence:

```bash
# This will use the explicit file (highest precedence)
python src/run_pipeline.py \
    --ground-truth-pvmap=/path/to/file.csv \
    --ground-truth-dir=/path/to/dir/ \
    --ground-truth-repo=/path/to/repo/
```

**Warning:** The system will log which source is being used for transparency.

### Directory Search Details

When using `--ground-truth-dir`, the system searches for PVMAP files using:

1. **Direct file match**: Looks for files containing dataset name + "pvmap" + ".csv"
2. **Subdirectory match**: Searches one level deep for folders matching dataset name
3. **Preference**: Exact matches preferred over partial matches, shorter names preferred

Example directory structure:
```
ground_truth/
├── bis_pvmap.csv                           # Direct match
├── cdc_social_vulnerability_pvmap.csv      # Direct match
└── bis_central_bank/                       # Subdirectory match
    └── bis_central_bank_pvmap.csv
```

### Single File with Multiple Datasets

When using `--ground-truth-pvmap` without the `--dataset` flag:

```bash
# Warning: This will only evaluate the FIRST dataset
python src/run_pipeline.py --ground-truth-pvmap=/path/file.csv
```

**Behavior:**
- ✓ First dataset: Uses the provided file for evaluation
- ✗ Remaining datasets: Evaluation skipped with clear logging
- 📝 Warning logged at startup about this behavior

**Recommendation:** Use `--ground-truth-dir` for multiple datasets instead.

### Evaluation Output

When ground truth is found, evaluation results are saved:

```
output/{dataset_name}/
└── eval_results/
    ├── diff_results.json    # Raw metrics (nodes matched, PVs matched, etc.)
    └── diff.txt             # Human-readable detailed diff
```

**Metrics calculated:**
- **Node Accuracy**: Percentage of nodes that matched exactly
- **PV Accuracy**: Percentage of property-value pairs that matched
- Counts: nodes matched/total, PVs matched/modified/deleted

### Aggregate Reporting

At pipeline completion, aggregate metrics are displayed:

```
Evaluation Metrics:
  Evaluated: 15/20 datasets
  Avg Node Accuracy: 24.5%
  Avg PV Accuracy: 38.2%
```

---

## Common Commands

```bash
# ── Web UI ──
PYTHONPATH="$(pwd):$(pwd)/src" streamlit run src/ui/app.py   # Launch UI at localhost:8501

# ── CLI: Basic ──
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate   # Single dataset
python src/run_pipeline.py                                              # All datasets
python src/run_pipeline.py --dry-run                                    # Preview only

# ── CLI: Skip phases ──
python src/run_pipeline.py --dataset=bis --skip-sampling                # Re-use existing samples
python src/run_pipeline.py --dataset=bis --skip-schema-selection        # Re-use existing schema
python src/run_pipeline.py --dataset=bis --skip-evaluation              # No GT comparison

# ── CLI: Tuning ──
python src/run_pipeline.py --dataset=bis --enable-mcp                   # StatVar discovery via MCP
python src/run_pipeline.py --dataset=bis --thinking-level=medium        # Adjust LLM thinking
python src/run_pipeline.py --dataset=bis --prompt-version=v1            # Use v1 prompt template
python src/run_pipeline.py --dataset=bis --structured-output            # Deterministic CSV (default)
python src/run_pipeline.py --force-resample                             # Regenerate samples

# ── CLI: Ground truth ──
python src/run_pipeline.py --dataset=bis --ground-truth-pvmap=/path/to/bis_pvmap.csv
python src/run_pipeline.py --resume-from=cdc_social_vulnerability_index
```

**See [USAGE.md](docs/USAGE.md#command-line-options) for complete options.**

---

## Output Structure

```
output/{dataset_name}/
├── generated_pvmap.csv           # Main output: Property-Value mapping
├── output_metadata.csv           # Auto-generated metadata config (PVMAP-derived + merged)
├── generation_notes.md           # LLM reasoning with attempt history
├── populated_prompt.txt          # Full prompt sent to Gemini
├── agentic_sampled.csv           # Sampled data from agentic sampler
├── data_context.json             # Structural analysis cache
├── generated_response/           # LLM attempts
│   ├── attempt_0.md              # First attempt (with model info + thinking content)
│   ├── attempt_0.json            # Attempt metadata (model, tokens, duration)
│   ├── attempt_1.md              # Retry (if needed)
│   └── attempt_2.md              # Final retry (if needed)
├── processed.csv                 # Validated StatVarObservations
├── processed.tmcf                # Template MCF
├── processed_stat_vars.mcf       # StatVar definitions
└── eval_results/                 # Evaluation (if ground truth found)
    ├── diff_results.json         # Raw metrics
    └── diff.txt                  # Detailed diff
```

---

## Benchmark Results: Claude vs Gemini

**Overall Performance (27 Datasets Compared):**

| Metric | Gemini Baseline | Claude Results | Improvement |
|--------|-----------------|----------------|-------------|
| **PV Accuracy** | 8.1% | 26.8% | **+18.7%** |
| **Node Accuracy** | 4.6% | 15.1% | **+10.5%** |

**Performance Summary:**
- **Improved:** 22 datasets (81.5%)
- **Declined:** 3 datasets (11.1%)
- **No Change:** 2 datasets (7.4%)

**Top Improvements:**

| Dataset | Gemini | Claude | Improvement |
|---------|--------|--------|-------------|
| bis_bis_central_bank_policy_rate | 0.0% | 73.1% | **+73.1%** |
| zurich_wir_2552_wiki | 17.9% | 64.3% | **+46.4%** |
| world_bank_commodity_market | 3.7% | 48.8% | **+45.1%** |
| inpe_fire | 0.0% | 44.3% | **+44.3%** |
| census_v2_sahie | 8.0% | 39.4% | **+31.4%** |

**See [APPENDIX.md](docs/APPENDIX.md#c-evaluation-metrics--benchmarks) for detailed metrics.**

---

## Common Issues

### Issue: ModuleNotFoundError for 'file_util'

```bash
# Solution: Set PYTHONPATH
export PYTHONPATH="$(pwd):$(pwd)/src"
```

### Issue: Gemini API key not set

```bash
# Solution: Create .env file or export variable
echo 'GEMINI_API_KEY=your-api-key-here' > .env
# OR
export GEMINI_API_KEY="your-api-key-here"
```

### Issue: Dataset output already exists

```bash
# Solution: Delete and regenerate
rm -rf output/your_dataset_name
python src/run_pipeline.py --dataset=your_dataset_name
```

**See [APPENDIX.md](docs/APPENDIX.md#a-detailed-troubleshooting-guide) for complete troubleshooting.**

---

## Running the Web UI (Streamlit)

The pipeline includes a web UI for interactive use — upload a CSV, watch the pipeline run, review results, and iterate with feedback.

### Launch

```bash
# Make sure you've completed installation first (see Quick Start above)
source .venv/bin/activate
PYTHONPATH="$(pwd):$(pwd)/src" streamlit run src/ui/app.py
```

This opens the UI at **http://localhost:8501**.

### Step-by-Step Workflow

1. **Upload your CSV** — Drag or browse to upload your input CSV file. Optionally upload a metadata CSV (2-column `parameter,value` format). A data preview shows automatically.

2. **Name your dataset** — Enter a dataset name (auto-filled from filename). This names the output directory.

3. **Configure (sidebar)** — Adjust settings before running:
   - **Max Retries** — Number of retry attempts after initial generation (default: 1, meaning 2 total attempts)
   - **MCP** — Toggle Data Commons MCP for StatVar discovery
   - **Advanced** — Prompt version (v1/v2) and schema examples toggle

4. **Click "Generate PVMAP"** — The pipeline runs in the background. A real-time progress tracker shows each phase: Sampling → Schema Selection → Generation → Validation → Quality Evaluation → Feedback.

5. **Review results** — When complete, results appear in tabs:
   - **PVMAP** — The generated property-value mapping (editable in-browser)
   - **Metadata** — The auto-generated `output_metadata.csv` (also editable)
   - **Validation** — StatVar processor output and MCF files
   - **Logs** — Generation notes and LLM reasoning

6. **Provide feedback & re-run** — If the PVMAP needs improvement:
   - Edit the PVMAP or metadata directly in the table editors
   - Describe what should change in the feedback text box
   - Select a category (column mapping, property names, etc.) and severity
   - Click **"Re-run"** — the pipeline re-runs with your feedback injected as context
   - Previous output is versioned (`v1/`, `v2/`, etc.) so nothing is lost

7. **Download** — Download the final PVMAP and output files when satisfied.

### Sidebar Features

- **Status pill** — Shows pipeline state (Idle / Running / Complete / Error)
- **Run ID** — Unique identifier for each run (with GCS link on Cloud Run)
- **History** — Previous runs listed with pass/fail status; click to reload results
- **New Run** — Reset the UI to start fresh

### Cloud Run Deployment

The UI can be deployed to Google Cloud Run with GCS-backed storage. See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for setup instructions.

---

## Key Features (Recent)

- **Schema.org Integration** - Local vocabulary cache with type/property lookup and validation
- **PVMAP Repair Pipeline** - Programmatic key repair before validation (case, whitespace, fuzzy match)
- **Structured Output** - Deterministic CSV via Gemini structured output schema (default: on)
- **Prompt Versioning** - v1/v2 prompt templates (`--prompt-version`)
- **Quality-Based Exit** - Stops retrying when quality exceeds threshold or stagnates
- **Cloud Run Deployment** - Docker + GCS FUSE for production deployment
- **MCP Integration** - Live StatVar discovery via Data Commons MCP server

---

## Getting Help

1. **Check Documentation:**
   - [SETUP.md](docs/SETUP.md) - Environment setup issues
   - [INPUT_GUIDE.md](docs/INPUT_GUIDE.md) - Input data formatting
   - [USAGE.md](docs/USAGE.md) - Pipeline usage
   - [APPENDIX.md](docs/APPENDIX.md) - Troubleshooting & architecture

2. **Check Logs:**
   ```bash
   tail -100 logs/pipeline_*.log
   tail -100 logs/your_dataset/generation_*.log
   ```

3. **Verify Setup:**
   ```bash
   python --version              # Should be 3.12+
   python -c "from google.adk.agents import LlmAgent; print('ADK OK')"
   echo $PYTHONPATH              # Should include project root and src/
   echo $GEMINI_API_KEY | head -c 10  # Should show key
   ```

4. **GitHub Issues:**
   - Search for similar problems
   - Open a new issue with logs and error messages

---

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## License

[Add your license information here]

---

## Acknowledgments

- **Data Commons** - Schema and validation tools
- **Google Gemini** - LLM for PVMAP generation
- **Google ADK** - Agent Development Kit for pipeline orchestration
- **Anthropic Claude Code** - Development tool for codebase assistance

---

## Next Steps

1. **First-time users:** Start with [SETUP.md](docs/SETUP.md)
2. **Preparing datasets:** Read [INPUT_GUIDE.md](docs/INPUT_GUIDE.md)
3. **Running pipeline:** Follow [USAGE.md](docs/USAGE.md)
4. **Debugging issues:** Check [APPENDIX.md](docs/APPENDIX.md)

---

**Need help?** See documentation above or open an issue on GitHub.

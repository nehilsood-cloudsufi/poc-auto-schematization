# Auto-Schematization POC: Automated PVMAP Pipeline

## Overview

This repository implements an **end-to-end automated pipeline** for generating Property-Value Maps (PVMAPs) that transform source data into Data Commons schema using Claude Code CLI.

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

---

## Quick Start (5 Minutes)

### Prerequisites

- Python 3.12+ installed
- Claude Code CLI installed ([guide](https://github.com/anthropics/claude-code))
- **Anthropic API key** (required only if you don't have an active Claude Code subscription)
  - Currently, this pipeline only supports Claude CLI
  - If using API key: `export ANTHROPIC_API_KEY="your-api-key-here"`
  - If you have a Claude Code subscription, the CLI will use your subscription automatically

### Installation

```bash
# Clone repository
git clone <repository-url> poc-auto-schematization
cd poc-auto-schematization

# Install dependencies (choose one)
uv sync                          # Using uv (recommended)
# OR
pip install -r requirements.txt  # Using pip

# Activate virtual environment
source .venv/bin/activate        # uv
# OR
source venv/bin/activate         # pip

# Set environment variables
# NOTE: ANTHROPIC_API_KEY is only required if you don't have an active Claude Code subscription
export ANTHROPIC_API_KEY="your-api-key-here"  # Skip this if you have Claude Code subscription
export PYTHONPATH="$(pwd):$(pwd)/tools:$(pwd)/util"
```

### Run Your First Pipeline

```bash
# Test with a single dataset
python3 run_pvmap_pipeline.py --dataset=bis_bis_central_bank_policy_rate

# Check results
ls output/bis_bis_central_bank_policy_rate/
```

**See [USAGE.md](docs/USAGE.md) for complete usage instructions.**

---

## Project Configuration

**Selected Configuration:**
- **Primary Dataset:** BIS Central Bank Policy Rate (SDMX data)
- **Repository Location:** Isolated repository (`~/poc-auto-schematization`)
- **Evaluation Benchmark:** Metrics from Auto_Schematization_Evaluation_Benchmark.docx
- **LLM:** Claude Sonnet 4.5 (via Claude Code CLI)
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
├── input/                    # 39 datasets with input data & metadata
├── output/                   # Generated PVMAPs (created automatically)
├── test_input/               # Test datasets (optional)
├── test_output/              # Test output (optional)
├── tools/                    # Processing tools
│   ├── statvar_importer/     # Main processing tools
│   ├── agentic_import/       # LLM-based import tools
│   └── data_sampler.py       # Auto-sampling tool
├── util/                     # Utility modules
├── logs/                     # Pipeline logs (created automatically)
├── run_pvmap_pipeline.py     # Main pipeline script
├── SETUP.md                  # Installation guide
├── INPUT_GUIDE.md            # Input structure guide
├── USAGE.md                  # Usage guide
├── APPENDIX.md               # Troubleshooting & architecture
└── README.md                 # This file
```

---
Initially Dataset should be like:
input/dataset_name/
├── test_data/
│   ├── *_input.csv
├── *_metadata.csv
---
## Pipeline Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Auto-Sampling (Optional)                           │
│ • Checks for existing sampled files                         │
│ • Generates samples if missing (max 100 rows)               │
│ • Creates combined_sampled_data.csv                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 1.5: Schema Selection (Optional)                      │
│ • Analyzes metadata and sampled data                        │
│ • Uses Claude CLI to select schema category                 │
│ • Copies appropriate .txt and .mcf schema files             │
│ • Skips if schema files already exist                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: PVMAP Generation                                   │
│ • Populates prompt with schema examples + sampled data      │
│ • Calls Claude Code CLI                                     │
│ • Generates property-value mapping                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Validation                                         │
│ • Runs stat_var_processor.py                                │
│ • Validates PVMAP format and content                        │
│ • Retries up to 2 times with error feedback if failed       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: Evaluation (Optional)                              │
│ • Searches for ground truth PVMAP                           │
│ • Compares generated vs ground truth                        │
│ • Generates diff-based metrics                              │
│ • Gracefully skips if ground truth not found                │
└─────────────────────────────────────────────────────────────┘
```

**See [APPENDIX.md](docs/APPENDIX.md#b-architecture--workflow-details) for detailed architecture.**

---

## Schema Selection (Phase 1.5)

The pipeline includes **automated schema selection** that intelligently analyzes your dataset and selects the most appropriate schema category from 7 predefined options.

### How It Works

1. **Analyze Dataset** - Examines metadata configuration and sampled data preview
2. **Invoke Claude CLI** - Uses Claude to intelligently classify dataset into one of 7 categories
3. **Copy Schema Files** - Copies the appropriate `.txt` and `.mcf` files to dataset directory
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
python3 run_pvmap_pipeline.py

# Skip schema selection (use existing schema files)
python3 run_pvmap_pipeline.py --skip-schema-selection

# Force re-selection even if schema files exist
python3 run_pvmap_pipeline.py --force-schema-selection

# Use custom schema directory
python3 run_pvmap_pipeline.py --schema-base-dir=/path/to/schemas
```

### Standalone Usage

The schema selector can also be run independently:

```bash
# Run schema selector independently
python3 tools/schema_selector.py --input_dir=input/dataset_name/

# Dry run to see what would be selected
python3 tools/schema_selector.py --input_dir=input/dataset_name/ --dry_run

# Force re-selection
python3 tools/schema_selector.py --input_dir=input/dataset_name/ --force
```

### Output

After schema selection, your dataset directory will include:

```
input/dataset_name/
├── test_data/
│   ├── *_input.csv
│   └── *_sampled_data.csv
├── *_metadata.csv
├── scripts_statvar_llm_config_schema_examples_dc_topic_{Category}.txt  # ← Added
└── scripts_statvar_llm_config_vertical_dc_topic_{Category}_statvars.mcf # ← Added
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
| `--ground-truth-repo` | Path to datacommonsorg-data repository | Using standard Data Commons repository structure (default) |
| `--skip-evaluation` | Skip evaluation phase entirely | You don't have ground truth files or don't need metrics |

### Default Configuration

The default ground truth repository path can be configured in three ways (in order of precedence):

1. **Command-line argument**: `--ground-truth-repo=/path/to/ground_truth`
2. **Environment variable**: `export GROUND_TRUTH_REPO=/path/to/ground_truth`
3. **Fallback default**: `../datacommonsorg-data/ground_truth`

**Example: Set via environment variable**
```bash
# Set for current session
export GROUND_TRUTH_REPO=/Users/nehilsood/work/datacommonsorg-data/ground_truth

# Or add to your shell profile for persistence
echo 'export GROUND_TRUTH_REPO=/Users/nehilsood/work/datacommonsorg-data/ground_truth' >> ~/.zshrc
source ~/.zshrc
```

### Usage Examples

```bash
# Use explicit PVMAP file for single dataset
python3 run_pvmap_pipeline.py --dataset=bis \
    --ground-truth-pvmap=/path/to/bis_pvmap.csv

# Search directory for ground truth files (matches by dataset name)
python3 run_pvmap_pipeline.py \
    --ground-truth-dir=/Users/nehilsood/work/datacommonsorg-data/ground_truth

# Use custom repository structure (auto-discovery)
python3 run_pvmap_pipeline.py \
    --ground-truth-repo=/path/to/datacommonsorg-data

# Skip evaluation entirely
python3 run_pvmap_pipeline.py --skip-evaluation

# Multiple datasets with single ground truth file
# (Warning: uses file for first dataset only, skips rest)
python3 run_pvmap_pipeline.py \
    --ground-truth-pvmap=/path/to/reference.csv
```

### Precedence Behavior

When multiple ground truth arguments are provided, the system follows strict precedence:

```bash
# This will use the explicit file (highest precedence)
python3 run_pvmap_pipeline.py \
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
python3 run_pvmap_pipeline.py --ground-truth-pvmap=/path/file.csv
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
# Process all datasets
python3 run_pvmap_pipeline.py

# Process specific dataset
python3 run_pvmap_pipeline.py --dataset=bis_bis_central_bank_policy_rate

# Test with test directories
python3 run_pvmap_pipeline.py --input-dir=test_input --output-dir=test_output

# Force regenerate samples
python3 run_pvmap_pipeline.py --force-resample

# Skip schema selection (use existing schema files)
python3 run_pvmap_pipeline.py --skip-schema-selection

# Force re-selection of schema files
python3 run_pvmap_pipeline.py --force-schema-selection

# Skip evaluation
python3 run_pvmap_pipeline.py --skip-evaluation

# Use explicit ground truth PVMAP file
python3 run_pvmap_pipeline.py --dataset=bis --ground-truth-pvmap=/path/to/bis_pvmap.csv

# Use ground truth directory (searches by dataset name)
python3 run_pvmap_pipeline.py --ground-truth-dir=/Users/nehilsood/work/datacommonsorg-data/ground_truth

# Use custom ground truth repository
python3 run_pvmap_pipeline.py --ground-truth-repo=/path/to/datacommonsorg-data

# Resume from specific dataset
python3 run_pvmap_pipeline.py --resume-from=cdc_social_vulnerability_index

# Dry run (preview without execution)
python3 run_pvmap_pipeline.py --dry-run
```

**See [USAGE.md](USAGE.md#command-line-options) for complete options.**

---

## Output Structure

```
output/{dataset_name}/
├── generated_pvmap.csv           # Main output: Property-Value mapping
├── generation_notes.md           # Claude's reasoning
├── populated_prompt.txt          # Full prompt sent to Claude
├── generated_response/           # Claude's attempts
│   ├── attempt_0.md              # First attempt
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
export PYTHONPATH="$(pwd):$(pwd)/tools:$(pwd)/util"
```

### Issue: Claude Code CLI not found

```bash
# Solution: Install Claude Code CLI
# Visit: https://github.com/anthropics/claude-code
claude --version
```

### Issue: Dataset output already exists

```bash
# Solution: Delete and regenerate
rm -rf output/your_dataset_name
python3 run_pvmap_pipeline.py --dataset=your_dataset_name
```

**See [APPENDIX.md](docs/APPENDIX.md#a-detailed-troubleshooting-guide) for complete troubleshooting.**

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
   claude --version              # Should show version
   echo $PYTHONPATH              # Should include project, tools, util
   echo $ANTHROPIC_API_KEY | head -c 10  # Should show key
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
- **Anthropic Claude** - LLM for PVMAP generation
- **Claude Code CLI** - Automation framework

---

## Next Steps

1. **First-time users:** Start with [SETUP.md](docs/SETUP.md)
2. **Preparing datasets:** Read [INPUT_GUIDE.md](docs/INPUT_GUIDE.md)
3. **Running pipeline:** Follow [USAGE.md](docs/USAGE.md)
4. **Debugging issues:** Check [APPENDIX.md](docs/APPENDIX.md)

---

**Need help?** See documentation above or open an issue on GitHub.

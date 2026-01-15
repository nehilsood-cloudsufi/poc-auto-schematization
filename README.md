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
- Anthropic API key

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
export ANTHROPIC_API_KEY="your-api-key-here"
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
   python --version              # Should be 3.9+
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

# Input Structure Guide

This guide explains how to structure your input data for the PVMAP Pipeline.

## Overview

Each dataset requires a specific file structure with both **required** and **optional/auto-generated** files.

---

## Required Files

Every dataset must have these files:

```
input/{dataset_name}/
├── test_data/
│   └── *_input.csv              # Your source data (REQUIRED)
├── *_metadata.csv                # Configuration file (REQUIRED)
├── scripts_*_schema_examples_*.txt  # Schema examples (REQUIRED or AUTO-SELECTED)
└── scripts_*_statvars.mcf        # StatVar definitions (REQUIRED or AUTO-SELECTED)
```

**Note:** Schema files (`.txt` and `.mcf`) can be automatically selected by the pipeline using Phase 1.5: Schema Selection (see below).

---

## 1. Input Data Files (`*_input.csv`)

Your source CSV data file(s).

### Requirements

- **Format:** Standard CSV with headers
- **Encoding:** UTF-8 recommended
- **Multiple files:** Supported - will be automatically combined
- **Location:** Must be in `test_data/` subdirectory

### Example

```csv
REF_AREA,TIME_PERIOD,OBS_VALUE,FREQ
US,2023-01,5.25,M
GB,2023-01,4.50,M
JP,2023-01,-0.10,M
```

### Multiple Input Files

If you have multiple input files, they will be combined automatically:

```
test_data/
├── dataset_part1_input.csv
├── dataset_part2_input.csv
└── dataset_part3_input.csv

→ Combined into: combined_input.csv (auto-generated)
```

---

## 2. Metadata Configuration (`*_metadata.csv`)

Controls how the pipeline processes your data.

### Format

```csv
parameter,value
header_rows,1
output_columns,"observationAbout,observationDate,value"
place_property,REF_AREA
date_property,TIME_PERIOD
value_property,OBS_VALUE
```

### Required Parameters

| Parameter | Description | Example Value |
|-----------|-------------|---------------|
| `header_rows` | Number of header rows to skip | `1` |
| `output_columns` | StatVarObservation columns to generate | `"observationAbout,observationDate,value"` |
| `place_property` | Column containing place identifiers (e.g., FIPS, country codes) | `REF_AREA` |
| `date_property` | Column containing dates or time periods | `TIME_PERIOD` |
| `value_property` | Column containing observation values | `OBS_VALUE` |

### Optional Parameters (Sampling Configuration)

| Parameter | Description | Default | Valid Range |
|-----------|-------------|---------|-------------|
| `sampler_output_rows` | Maximum rows in sampled data | `100` | 10-1000 |
| `sampler_rows_per_key` | Maximum rows per categorical value | `5` | 1-50 |
| `sampler_categorical_threshold` | Ratio threshold for categorical detection | `0.1` | 0.01-0.5 |
| `sampler_max_aggregation_rows` | Max total/summary rows to include | `2` | 0-10 |
| `sampler_ensure_coverage` | Ensure all categorical values are covered | `True` | True/False |
| `sampler_smart_columns` | Skip constant/derived columns | `True` | True/False |
| `sampler_detect_aggregation` | Detect and limit total/summary rows | `True` | True/False |

### Example with Sampling Configuration

```csv
parameter,value
header_rows,1
output_columns,"observationAbout,observationDate,value,unit"
place_property,FIPS_Code
date_property,Year
value_property,Population_Count
sampler_output_rows,150
sampler_rows_per_key,7
sampler_categorical_threshold,0.15
```

---

## 3. Schema Example Files (`scripts_*_schema_examples_*.txt`)

Sample PVMAPs from similar data categories that serve as examples for Claude.

### Purpose

These files provide context to help Claude understand:
- How similar data has been mapped before
- What properties and values to use
- Data Commons schema patterns

### Two Options for Schema Files

#### Option A: Automatic Schema Selection (Recommended) ⭐

The pipeline can automatically select the best schema category for your dataset using **Phase 1.5: Schema Selection**.

**How it works:**
1. Pipeline analyzes your metadata and sampled data
2. Uses Claude CLI to intelligently classify your dataset
3. Automatically copies appropriate schema files from `schema_example_files/`
4. Proceeds with PVMAP generation

**No manual schema selection needed!**

```bash
# Just run the pipeline - schema selection happens automatically
python3 run_pvmap_pipeline.py --dataset=your_dataset
```

**Forcing re-selection:**
```bash
# If schema files exist but you want to re-select
python3 run_pvmap_pipeline.py --dataset=your_dataset --force-schema-selection
```

**Skipping schema selection:**
```bash
# Use existing schema files (skip Phase 1.5)
python3 run_pvmap_pipeline.py --dataset=your_dataset --skip-schema-selection
```

#### Option B: Manual Schema Selection

If you prefer to manually copy schema files:

**Step 1:** Determine your dataset's category from the table below
**Step 2:** Copy the corresponding `.txt` and `.mcf` files to your dataset directory

```bash
# Example: Copy Economy schema files
cp schema_example_files/Economy/*.txt input/your_dataset/
cp schema_example_files/Economy/*.mcf input/your_dataset/
```

### Available Schema Categories

| Category | Description | Example Topics | Use When |
|----------|-------------|----------------|----------|
| **Demographics** | Population, age, gender, race, household, nativity | Census data, population statistics, demographic surveys | Dataset contains population characteristics, household data, demographic breakdowns |
| **Economy** | GDP, business establishments, revenue, trade, commodities | Economic indicators, business metrics, financial data | Dataset tracks economic activity, financial rates, trade, commodities |
| **Education** | School enrollment, degrees, educational attainment, literacy | Educational statistics, enrollment data, degree conferrals | Dataset includes education levels, school enrollment, academic performance |
| **Employment** | Labor force, jobs, wages, unemployment, occupations | BLS data, labor statistics, workforce metrics | Dataset contains employment data, wages, labor force statistics |
| **Energy** | Power generation, consumption, renewable energy, infrastructure | Energy production, consumption, environmental metrics | Dataset tracks energy production/consumption, power infrastructure |
| **Health** | Disease prevalence, mortality, healthcare access, medical conditions | Health indicators, disease data, medical surveys | Dataset includes health outcomes, disease rates, medical conditions |
| **School** | School-specific metrics, performance, facilities, student-teacher ratios | School performance, facilities data, institutional metrics | Dataset is about specific schools/institutions, not aggregated education stats |

### File Naming Convention

```
scripts_statvar_llm_config_schema_examples_dc_topic_{Category}.txt
```

Examples:
- `scripts_statvar_llm_config_schema_examples_dc_topic_Economy.txt`
- `scripts_statvar_llm_config_schema_examples_dc_topic_Health.txt`

---

## 4. StatVar Definition Files (`scripts_*_statvars.mcf`)

StatVar (Statistical Variable) definitions for the data category.

### Purpose

These files provide:
- Variable definitions and metadata
- Property relationships
- Value constraints and types

### Automatic Selection

These files are **automatically copied** along with schema example files during Phase 1.5: Schema Selection. You don't need to manually copy them when using automatic schema selection.

### File Naming Convention

```
scripts_statvar_llm_config_vertical_dc_topic_{Category}_statvars.mcf
```

Examples:
- `scripts_statvar_llm_config_vertical_dc_topic_Economy_statvars.mcf`
- `scripts_statvar_llm_config_vertical_dc_topic_Health_statvars.mcf`

---

## 5. Sampled Data Files (Auto-Generated)

The pipeline can automatically generate sampled data files.

### Two Scenarios

#### Scenario 1: Without Pre-Existing Sampled Files (Auto-Generation)

**When you run the pipeline without sampled files:**

**Step 1:** Pipeline detects missing samples
```
INFO: No sampled data found for bis_bis_central_bank_policy_rate
INFO: Auto-generating sampled data from input files...
```

**Step 2:** Auto-samples each input file
```
Input:  WS_CBPOL_csv_flat_input.csv (1,234 rows)
Output: WS_CBPOL_csv_flat_input_sampled_data.csv (31 rows)
```

**Step 3:** Creates combined file for pipeline
```
Generated: combined_sampled_data.csv
```

**File Naming Convention:**
```
Input file:   WS_CBPOL_csv_flat_input.csv
Sampled file: WS_CBPOL_csv_flat_input_sampled_data.csv

Input file:   Finland_Census_input.csv
Sampled file: Finland_Census_input_sampled_data.csv
```

The sampler appends `_sampled_data.csv` to the input filename (without `.csv` extension).

**Directory Structure (Auto-Generated):**
```
input/bis_bis_central_bank_policy_rate/
├── test_data/
│   ├── WS_CBPOL_csv_flat_input.csv              # Original (1,234 rows)
│   ├── WS_CBPOL_csv_flat_input_sampled_data.csv # ✅ Auto-generated (31 rows)
│   └── combined_sampled_data.csv                 # ✅ Auto-generated (31 rows)
├── central_bank_policy_rate_metadata.csv
├── scripts_statvar_llm_config_schema_examples_dc_topic_Economy.txt
└── scripts_statvar_llm_config_vertical_dc_topic_Economy_statvars.mcf
```

**Force Re-Sampling:**

If you want to regenerate samples:
```bash
python3 run_pvmap_pipeline.py --force-resample
```

---

#### Scenario 2: With Pre-Existing Sampled Files (Reuse)

**If `*_sampled_data.csv` files already exist in `test_data/`:**

**Step 1:** Pipeline detects existing samples
```
INFO: Using existing sampled data: ['WS_CBPOL_csv_flat_input_sampled_data.csv']
```

**Step 2:** Skips sampling, uses existing files
- No re-sampling unless `--force-resample` flag used
- Combined file regenerated from existing samples
- Faster pipeline execution

**When to Use Pre-Existing Samples:**
- You've manually curated sample data
- You want consistent samples across runs
- You've run the pipeline before and don't need new samples

**Directory Structure (With Pre-Existing Samples):**
```
input/bis_bis_central_bank_policy_rate/
├── test_data/
│   ├── WS_CBPOL_csv_flat_input.csv              # Original data (1,234 rows)
│   ├── WS_CBPOL_csv_flat_input_sampled_data.csv # ✅ Pre-existing (31 rows)
│   └── combined_sampled_data.csv                 # ✅ Regenerated (31 rows)
├── central_bank_policy_rate_metadata.csv
├── scripts_statvar_llm_config_schema_examples_dc_topic_Economy.txt
└── scripts_statvar_llm_config_vertical_dc_topic_Economy_statvars.mcf
```

---

## 6. Complete Directory Structure Example

Here's a complete example of a properly structured dataset:

### Before Pipeline Runs

```
input/bis_bis_central_bank_policy_rate/
├── test_data/
│   └── WS_CBPOL_csv_flat_input.csv              # REQUIRED: Input data
├── central_bank_policy_rate_metadata.csv         # REQUIRED: Metadata
├── scripts_statvar_llm_config_schema_examples_dc_topic_Economy.txt  # REQUIRED: Schema examples
└── scripts_statvar_llm_config_vertical_dc_topic_Economy_statvars.mcf  # REQUIRED: StatVar defs
```

### After Pipeline Runs (Auto-Generated Files)

```
input/bis_bis_central_bank_policy_rate/
├── test_data/
│   ├── WS_CBPOL_csv_flat_input.csv              # Original input data
│   ├── WS_CBPOL_csv_flat_input_sampled_data.csv # ✅ Auto-generated sample
│   └── combined_sampled_data.csv                 # ✅ Auto-generated combined
├── central_bank_policy_rate_metadata.csv
├── scripts_statvar_llm_config_schema_examples_dc_topic_Economy.txt
└── scripts_statvar_llm_config_vertical_dc_topic_Economy_statvars.mcf

output/bis_bis_central_bank_policy_rate/
├── generated_pvmap.csv           # ✅ Main output: Property-Value mapping
├── generation_notes.md           # ✅ Claude's reasoning
├── populated_prompt.txt          # ✅ Full prompt sent to Claude
├── generated_response/           # ✅ Claude's attempts
│   ├── attempt_0.md              # First attempt
│   ├── attempt_1.md              # Retry (if validation failed)
│   └── attempt_2.md              # Final retry (if needed)
├── processed.csv                 # ✅ Validated StatVarObservations
├── processed.tmcf                # ✅ Template MCF
├── processed_stat_vars.mcf       # ✅ StatVar definitions
└── eval_results/                 # ✅ Evaluation (if ground truth found)
    ├── diff_results.json
    └── diff.txt
```

---

## Sample Data Features

The auto-sampler intelligently selects representative data:

### Smart Column Analysis
- Skips constant columns (same value everywhere)
- Skips derived columns (calculated from other columns)
- Focuses on meaningful data columns

### Aggregation Row Detection
- Deprioritizes total/summary rows
- Detects keywords: Total, All, Sum, Overall, National, etc.
- Limits aggregation rows based on configuration

### Numeric Range Coverage
- Samples values across quartiles (min, q1, median, q3, max)
- Ensures numeric data spans the full range

### Categorical Coverage
- Ensures all categorical values are represented
- Balances rows per category
- Avoids duplicate patterns

### ID Column Detection
- Recognizes ID/CODE/FIPS/KEY columns
- Excludes from categorical analysis

---

## Validation

Before running the pipeline, verify your input structure:

```bash
# Check required files exist
ls input/your_dataset/test_data/*_input.csv
ls input/your_dataset/*_metadata.csv
ls input/your_dataset/scripts_*_schema_examples_*.txt
ls input/your_dataset/scripts_*_statvars.mcf

# Check metadata format
head -10 input/your_dataset/*_metadata.csv

# Check input data format
head -5 input/your_dataset/test_data/*_input.csv
```

---

## Next Steps

Once your input structure is ready:

1. **Run the Pipeline** - See [USAGE.md](USAGE.md) for instructions
2. **Review Output** - Check the generated PVMAP in `output/{dataset_name}/`
3. **Evaluate Results** - Compare against ground truth if available

---

## Common Issues

### Issue: Metadata CSV Not Found

**Error:** `FileNotFoundError: No such file or directory: 'metadata.csv'`

**Solution:** Ensure metadata file is in dataset root directory (not in test_data/)

```
✅ Correct: input/your_dataset/metadata.csv
❌ Wrong:   input/your_dataset/test_data/metadata.csv
```

### Issue: Schema Files Not Found

**Error:** `FileNotFoundError: No such file or directory: 'scripts_*_schema_examples_*.txt'`

**Solution 1: Use Automatic Schema Selection (Recommended)**

```bash
# Let the pipeline auto-select schema files for you
python3 run_pvmap_pipeline.py --dataset=your_dataset

# Or run schema selector standalone
python3 tools/schema_selector.py --input_dir=input/your_dataset/
```

**Solution 2: Manually Copy Schema Files**

```bash
# Example: Economy category
cp schema_example_files/Economy/scripts_statvar_llm_config_schema_examples_dc_topic_Economy.txt input/your_dataset/
cp schema_example_files/Economy/scripts_statvar_llm_config_vertical_dc_topic_Economy_statvars.mcf input/your_dataset/
```

### Issue: Sampled Data Has Wrong Columns

**Error:** `KeyError: 'column_name' not found in sampled data`

**Solution:** Force regenerate sampled data

```bash
python3 run_pvmap_pipeline.py --force-resample --dataset=your_dataset
```

For more troubleshooting, see [APPENDIX.md](APPENDIX.md#a-detailed-troubleshooting-guide).

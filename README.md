# POC Implementation Plan: Isolated Auto-Schematization Repository

## Overview

**Selected Configuration:**
- **Starting Dataset:** BIS Central Bank Policy Rate (SDMX data)
- **Repository Location:** New directory outside repo (`~/poc-auto-schematization`)
- **Evaluation Benchmark:** Using metrics from Auto_Schematization_Evaluation_Benchmark.docx

---

## Understanding the Transcript

1. **Create an isolated repository** with only the necessary code (stat processor + related tools)
2. **Use Claude Code CLI** (not Gemini) to generate PV maps from sample data + sample schema
3. **Human-in-the-loop validation** - run stat processor manually, fix errors with Claude, iterate
4. **Evaluate results** - compare generated PV maps against ground truth using existing evaluation scripts
5. **Benchmark comparison** - compare (Claude vs Ground Truth) against (Gemini vs Ground Truth) from the evaluation benchmark document

### Key Insight

The current approach might not be leveraging **sample schema files** (existing PV maps from similar data categories like population, demographics, etc.) to guide the LLM. The POC should use these sample schemas as context.

---

## Workflow Explained (Step-by-Step)

### Phase 1: Setup Isolated Repository [COMPLETED]

**Goal:** Create a clean repo with minimal necessary code

**Repository Structure:**
```
poc-auto-schematization/
├── tools/                          # Copied from datacommonsorg-data/tools/
│   ├── statvar_importer/           # Main processing tools
│   └── agentic_import/             # LLM-based import tools
├── util/                           # Copied from datacommonsorg-data/util/
├── input/                          # Dataset folders (39 total)
│   ├── {dataset_name}/
│   │   ├── test_data/
│   │   │   ├── *_input.csv                    # Input data file(s)
│   │   │   └── {input_file}_sampled_data.csv  # Sampled data (max 100 rows)
│   │   ├── *_metadata.csv          # Metadata configuration file(s)
│   │   ├── scripts_*_schema_examples_*.txt  # Schema examples for category
│   │   └── scripts_*_statvars.mcf  # StatVar definitions for category
│   └── ...
├── output/                         # Generated output folders per dataset
├── Schema Example Files/           # Sample schemas organized by DC topic
│   ├── Demographics/
│   ├── Economy/
│   ├── Education/
│   ├── Employment/
│   ├── Energy/
│   ├── Health/
│   └── School/
├── copy_datasets.sh                # Script to copy datasets from source
├── map_schema_to_datasets.sh       # Script to map and copy schema files
├── eval_metrics.py                 # PV map evaluation script
├── evaluate_pvmap_diff.py          # Detailed PV map comparison
└── README.md
```

**Dataset Copy Script:** `copy_datasets.sh`

The script automatically copies datasets from `datacommonsorg-data/statvar_imports/` with these rules:
- Only copies datasets that have BOTH `*_input.csv` (in test_data/) AND `*_metadata.csv` files
- Skips datasets missing either file
- Preserves the folder structure: `{dataset}/test_data/*_input.csv` + `{dataset}/*_metadata.csv`

**Source Locations (from datacommonsorg-data repo):**
| Component | Source Path |
|-----------|-------------|
| Tools | `tools/statvar_importer/`, `tools/agentic_import/` |
| Utilities | `util/` |
| Input Data | `statvar_imports/{dataset}/test_data/*_input.csv` |
| Metadata | `statvar_imports/{dataset}/*_metadata.csv` |
| Schema Examples | `scripts/statvar_llm_config/` |

---

**Schema Mapping Script:** `map_schema_to_datasets.sh`

This script maps each dataset to its appropriate Data Commons topic category and copies the corresponding schema files (`.txt` and `.mcf`) to each dataset folder.

**Category Mapping (based on content analysis):**

| Category | Datasets | Description |
|----------|----------|-------------|
| Demographics | 14 | Population, census, mortality, vulnerability data |
| Economy | 7 | Financial rates, poverty, commodities, insurance |
| Health | 6 | Disease prevalence, health surveys, COVID data |
| Education | 6 | School enrollment, performance, teachers |
| Employment | 4 | BLS employment statistics, workforce data |
| Energy | 2 | Environmental/infrastructure data |

**Dataset to Category Assignments:**

| Category | Datasets |
|----------|----------|
| Demographics | bev_3240_wiki, bev_3903_age10_wiki, bev_3903_hel_wiki, bev_3903_sex_wiki, bev_4031_hel_wiki, bev_4031_sex_wiki, bev_4031_wiki, finland_census, us_census_pep_asrh, kenya_census, ncses_demographics_seh_import, social_vulnerability_index, fars_crashdata, fbigovcrime |
| Economy | bis_central_bank_policy_rate, commerce_eda, commodity_market, sahie, ndap, wir_2552_wiki, undata |
| Health | india_nfhs, india_nss_health_ailments, ny_diabetes, who_covid19, texas, single_race |
| Employment | bls_ces, bls_ces_state, doctoratedegreeemployment, teachers |
| Education | education, school_algebra1, enrollment, maths_and_science_enrollment, new_york_education, covid_directional_indicators |
| Energy | wastewater_treatment, inpe_fire |

**Schema Files Copied:**

| Category | .txt File | .mcf File |
|----------|-----------|-----------|
| Demographics | `scripts_statvar_llm_config_schema_examples_dc_topic_Demographics.txt` | `scripts_statvar_llm_config_vertical_dc_topic_Demographics_statvars.mcf` |
| Economy | `scripts_statvar_llm_config_schema_examples_dc_topic_Economy.txt` | `scripts_statvar_llm_config_vertical_dc_topic_Economy_statvars.mcf` |
| Health | `scripts_statvar_llm_config_schema_examples_dc_topic_Health.txt` | `scripts_statvar_llm_config_vertical_dc_topic_Health_statvars.mcf` |
| Employment | `scripts_statvar_llm_config_schema_examples_dc_topic_Employment.txt` | `scripts_statvar_llm_config_vertical_dc_topic_Employment_statvars.mcf` |
| Education | `scripts_statvar_llm_config_schema_examples_dc_topic_Education.txt` | `scripts_statvar_llm_config_vertical_dc_topic_Education_statvars.mcf` |
| Energy | `scripts_statvar_llm_config_schema_examples_dc_topic_Energy.txt` | `scripts_statvar_llm_config_vertical_dc_topic_Energy_statvars.mcf` |

### Phase 2: Data Preparation [COMPLETED]

**Goal:** Prepare input data, samples, and schema context for each dataset

**Each input folder now contains:**

| File | Description | Status |
|------|-------------|--------|
| `test_data/*_input.csv` | Input data file(s) from source | ✅ Copied |
| `test_data/{input_file_name}_sampled_data.csv` | Sampled data (max 100 rows) for LLM processing | ✅ Generated |
| `*_metadata.csv` | Processor configuration from source repo | ✅ Copied |
| `scripts_*_schema_examples_*.txt` | Sample schema examples for the topic | ✅ Mapped & Copied |
| `scripts_*_statvars.mcf` | Sample StatVar definitions for the topic | ✅ Mapped & Copied |

**Data Sampling:**

Ran `run_data_sampler.sh` using `tools/data_sampler.py` for all 36 datasets:
- **Total datasets:** 36
- **Successfully sampled:** 36
- **Total sampled files:** 47 (1:1 mapping with input files)
- **Output naming:** `{input_file_name}_sampled_data.csv`

**Sampler Configuration:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `sampler_output_rows` | 100 | Maximum rows in sampled output |
| `sampler_rows_per_key` | 5 | Max rows per unique value |
| `sampler_categorical_threshold` | 0.1 | Ratio threshold for categorical detection |
| `sampler_max_aggregation_rows` | 2 | Max total/summary rows to include |

**Sampling Features:**
- 

- **Smart Column Analysis** - Skips constant, derived, and redundant columns to focus on meaningful data
- **Aggregation Row Detection** - Deprioritizes total/summary rows (keywords: Total, All, Sum, Overall, National, etc.)
- **Numeric Range Coverage** - Samples values across quartiles (min, q1, median, q3, max) for numeric columns
- **Duplicate Pattern Detection** - Avoids selecting rows with identical categorical signatures
- **ID Column Detection** - Recognizes ID/CODE/FIPS/KEY columns and excludes from categorical analysis


### Phase 3 & 4: Automated PVMAP Generation & Validation Pipeline [COMPLETED]

**Goal:** Fully automated pipeline that generates PV maps and validates them with retry logic

**Script:** `run_pvmap_pipeline.py`

**Usage:**
```bash
# Process all datasets
python3 run_pvmap_pipeline.py

# Process specific dataset
python3 run_pvmap_pipeline.py --dataset=bis

# Resume from a specific dataset
python3 run_pvmap_pipeline.py --resume-from=edu

# Dry run (show what would be processed)
python3 run_pvmap_pipeline.py --dry-run
```

**Pipeline Workflow:**

1. **Dataset Discovery** - Automatically discovers all datasets in `input/` folder
2. **File Combination** - Merges multiple input/metadata files if dataset has multiple sources
3. **Prompt Population** - Populates `tools/improved_pvmap_prompt.txt` with:
   | Placeholder | Source |
   |-------------|--------|
   | `{{SCHEMA_EXAMPLES}}` | `input/{dataset}/scripts_*_schema_examples_*.txt` |
   | `{{SAMPLED_DATA}}` | `input/{dataset}/test_data/combined_sampled_data.csv` |
   | `{{METADATA_CONFIG}}` | `input/{dataset}/{dataset}_combined_metadata.csv` |
4. **Claude Code CLI Generation** - Calls `claude --print --model sonnet` to generate PVMAP
5. **Automated Validation** - Runs `stat_var_processor.py` to validate the generated PVMAP
6. **Retry with Error Feedback** - If validation fails, retries up to 2 times with error context

**Output Structure (per dataset):**
```
output/{dataset}/
├── generated_pvmap.csv           # Final PVMAP output
├── generation_notes.md           # Claude's reasoning and analysis
├── populated_prompt.txt          # Full prompt sent to Claude
├── generated_response/           # Claude response history
│   ├── attempt_0.md              # First attempt response
│   ├── attempt_1.md              # Retry response (if needed)
│   └── attempt_2.md              # Final retry (if needed)
└── processed/                    # StatVar processor output
    ├── processed.csv
    ├── statvar.mcf
    └── observations.tmcf
```

**Logging:**
```
logs/
├── pipeline_{timestamp}.log           # Main pipeline log
└── {dataset}/
    └── generation_{timestamp}.log     # Per-dataset detailed log
```

**Key Features:**
- **Retry Logic** - Up to 2 retries with validation error feedback
- **Smart Log Sampling** - Extracts meaningful error samples (last 50 lines + 10 random samples)
- **Multi-file Support** - Combines multiple input/metadata files automatically
- **Resume Capability** - Can resume from specific dataset if interrupted

**Configuration:**
- Max retries: 2
- Claude model: `sonnet`
- Validation timeout: 5 minutes
- Generation timeout: 15 minutes

### Phase 5: Diff-Based Evaluation [COMPLETED]

**Goal:** Compare generated PV maps against ground truth using diff-based metrics

**Script:** `evaluate_pvmap_diff.py`

**Usage:**
```bash
# Evaluate a single dataset (finds ground truth automatically)
python evaluate_pvmap_diff.py --dataset_path=../statvar_imports/bis/bis_central_bank_policy_rate

# Use existing auto-generated pvmap
python evaluate_pvmap_diff.py --dataset_path=<path> --auto_pvmap=output/bis/generated_pvmap.csv

# Specify output directory
python evaluate_pvmap_diff.py --dataset_path=<path> --output_dir=results/
```

**Batch Evaluation Script:** `run_bis_evaluation.py`
```bash
# Run evaluation for all datasets with ground truth
python run_bis_evaluation.py
```

**How It Works:**

1. **Find Files** - Locates input CSV and ground truth PVMAP in the dataset folder
2. **Load PVMAPs** - Loads both auto-generated and ground truth PVMAPs using `property_value_mapper.load_pv_map()`
3. **Run Diff** - Uses `mcf_diff.diff_mcf_nodes()` to compare node-by-node
4. **Generate Metrics** - Calculates accuracy, coverage, precision, recall

**Output Files (per dataset):**
```
output/{dataset}/eval_results/{subfolder}/
├── diff_results.json    # Raw metrics JSON
└── diff.txt             # Detailed property-level diff
```

**Metrics Calculated:**

| Metric | Formula |
|--------|---------|
| Node Accuracy | `nodes-matched / nodes-ground-truth × 100%` |
| Node Coverage | `(nodes-matched + nodes-with-diff) / nodes-ground-truth × 100%` |
| PV Accuracy | `PVs-matched / (PVs-matched + pvs-modified + pvs-deleted) × 100%` |
| Precision | `(PVs-matched + pvs-modified) / (PVs-matched + pvs-modified + pvs-added) × 100%` |
| Recall | `PVs-matched / (PVs-matched + pvs-modified + pvs-deleted) × 100%` |

**Sample Output:**
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

### Phase 6: Benchmark Comparison [COMPLETED]

**Goal:** Compare Claude results against Gemini baseline from evaluation benchmark document

**Generated Analysis Files:**
```
analysis/
├── Auto_Schematization_Evaluation_Analysis.md   # Main comprehensive report
├── Benchmark_Comparison.md                       # Comparison vs Gemini baseline
├── dataset_summaries/                            # Individual dataset reports (38 files)
│   ├── undata_analysis.md
│   ├── bis_analysis.md
│   └── ...
└── raw_data/
    └── all_metrics.json                          # Aggregated metrics JSON
```

**Benchmark Comparison Results (27 datasets compared):**

| Metric | Value |
|--------|-------|
| Datasets Compared | 27 |
| Improved (PV Acc) | 22 (81.5%) |
| Declined (PV Acc) | 3 (11.1%) |
| No Change | 2 (7.4%) |
| Avg PV Accuracy Change | **+18.7%** |
| Avg Node Accuracy Change | **+10.5%** |

**Top Improvements vs Gemini Baseline:**

| Dataset | Gemini PV % | Claude PV % | Improvement |
|---------|-------------|-------------|-------------|
| bis_bis_central_bank_policy_rate | 0.0% | 73.1% | +73.1% |
| zurich_wir_2552_wiki | 17.9% | 64.3% | +46.4% |
| world_bank_commodity_market | 3.7% | 48.8% | +45.1% |
| inpe_fire | 0.0% | 44.3% | +44.3% |
| census_v2_sahie | 8.0% | 39.4% | +31.4% |

**Claude vs Gemini Overall Averages:**

| Metric | Gemini Baseline | Claude Results | Change |
|--------|-----------------|----------------|--------|
| PV Accuracy | 8.1% | 26.8% | +18.7% |
| Node Accuracy | 4.6% | 15.1% | +10.5% |

---

## Evaluation Metrics (from Benchmark Document)

### Node-Level Metrics
| Metric | Description |
|--------|-------------|
| `nodes-ground-truth` | Total keys in human-created pvmap (baseline) |
| `nodes-auto-generated` | Total keys in LLM-generated pvmap |
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

### Quality Benchmarks
| Metric | Excellent | Good | Needs Work | Poor |
|--------|-----------|------|------------|------|
| Node Accuracy | >80% | 50-80% | 20-50% | <20% |
| PV Accuracy | >70% | 40-70% | 20-40% | <20% |
| pvs-deleted | 0 | 1-5 | 6-20 | >20 |
| nodes-missing-in-mcf2 | 0 | 1-3 | 4-10 | >10 |

### Current Gemini Baseline (49 Datasets)
| Metric | Value |
|--------|-------|
| Average Node Accuracy | 4.6% |
| Average Node Coverage | 45.8% |
| Average PV Accuracy | 8.1% |
| Average Precision | 22.5% |
| Average Recall | 8.1% |
| Best Dataset | undata (88.8% Node Accuracy, 87.1% PV Accuracy) |

### BIS Dataset Gemini Baseline
| Metric | Value |
|--------|-------|
| Node Accuracy | 0.0% |
| Node Coverage | 100.0% |
| PV Accuracy | 0.0% |
| Precision | 11.9% |
| Recall | 0.0% |

**Goal:** Beat these Gemini baseline metrics with Claude + sample schema approach.

---

## Key Concepts Explained

### What is a PV Map?
A Property-Value map (`pvmap.csv`) defines how to transform source data columns/values into Data Commons schema:

```csv
key,property1,value1,property2,value2
State FIPS Code,StateFIPS,{Data},,
Year,observationDate,{Data},,
Population,populationType,Person,measuredProperty,count,value,{Number}
```

### What is a Sample Schema?
An existing PV map from a similar data category that serves as an example/template for the LLM. For example:
- Population data → use existing population PV map as context
- Demographics data → use demographics PV map as context
- Health data → use health PV map as context

### What is StatVar Processor?
The main tool that:
- **Input:** CSV data + PV map + config
- **Output:** MCF files + observations CSV + TMCF template
- Validates that PV map correctly transforms all data

---


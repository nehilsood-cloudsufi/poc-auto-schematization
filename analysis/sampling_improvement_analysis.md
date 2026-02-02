# Data Sampling Pipeline: Complete Analysis & Improvement Recommendations

## Executive Summary

This document provides a comprehensive analysis of the data sampling pipeline in the ADK-based PVMAP generation system. It includes:

1. **Complete understanding of the current sampling process** - How data flows through the three-layer architecture
2. **Expert feedback analysis** - Insights from a PVMAP specialist (Sanika Prasad) on StatVar uniqueness
3. **Gap identification** - Where the current approach falls short
4. **Concrete evidence** - Real datasets showing the problem
5. **Proposed improvements** - Actionable recommendations

**The Core Issue:** The current sampler tracks coverage of individual categorical **values**, but PVMAP generation requires understanding dimension **combinations** that define unique StatVars.

---

## Table of Contents

1. [Understanding the Current Data Sampling Process](#part-1-understanding-the-current-data-sampling-process)
   - [Architecture Overview](#11-architecture-overview)
   - [The Coverage-First Algorithm](#12-the-coverage-first-algorithm-explained)
   - [Layer-by-Layer Breakdown](#13-layer-by-layer-breakdown)
   - [Configuration & Defaults](#14-configuration--defaults)
   - [Integration with Pipeline](#15-integration-with-pipeline)
2. [Expert Conversation Analysis](#part-2-expert-conversation-analysis-pvmap-specialist-feedback)
   - [Full Conversation Summary](#21-full-conversation-summary)
   - [Key Concepts Explained](#22-key-concepts-explained)
   - [The "Skeleton" of Data](#23-the-skeleton-of-data)
3. [Gap Analysis: Current vs Required](#part-3-gap-analysis-current-vs-required)
   - [Values vs Combinations](#31-values-vs-combinations)
   - [Visual Comparison](#32-visual-comparison)
4. [Research: Concrete Evidence](#part-4-research-concrete-evidence)
   - [India NFHS Dataset](#41-india-nfhs-dataset)
   - [INPE Fire Dataset](#42-inpe-fire-dataset-brazil)
5. [Root Cause Analysis](#part-5-root-cause-analysis)
6. [Proposed Improvements](#part-6-proposed-improvements)
7. [Implementation Considerations](#part-7-implementation-considerations)

---

# Part 1: Understanding the Current Data Sampling Process

## 1.1 Architecture Overview

The data sampling pipeline uses a **three-layer architecture**:

```
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 4: Pipeline Orchestration                                 │
│ src/agents/coordinator.py - SequentialAgent chains agents       │
│ - Chains: Discovery → Sampling → Schema → PVMAP → Evaluation    │
└──────────────────────────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────┐
│ LAYER 3: ADK Agent                                              │
│ src/agents/sampling_agent.py::SamplingAgent                     │
│ - Checks skip_sampling & force_resample flags                   │
│ - Discovers input files from DatasetInfo                        │
│ - Calls tool for each file, updates state                       │
│ - Pattern: Simple BaseAgent (deterministic, no LLM)             │
└──────────────────────────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────┐
│ LAYER 2: Tool Wrapper                                           │
│ src/tools/data_sampler_tool.py::sample_data()                   │
│ - Path-based API (input/output file paths)                      │
│ - Returns structured Dict with success, rows_sampled, error     │
│ - Bakes in default config from run_pvmap_pipeline.py            │
└──────────────────────────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼──────────────────────────────┐
│ LAYER 1: Core Sampling Engine                                   │
│ src/pipeline/sampling/data_sampler.py::DataSampler              │
│ - 1444 lines, 50+ config parameters                             │
│ - Coverage-first sampling algorithm                             │
│ - Categorical detection, aggregation filtering                  │
│ - Smart column analysis via ColumnAnalyzer                      │
└─────────────────────────────────────────────────────────────────┘
```

### Key Files

| File | Lines | Purpose |
|------|-------|---------|
| `src/agents/sampling_agent.py` | 210 | ADK agent orchestration |
| `src/tools/data_sampler_tool.py` | 136 | Tool wrapper with defaults |
| `src/pipeline/sampling/data_sampler.py` | 1444 | Core sampling engine |
| `src/pipeline/sampling/column_analyzer.py` | ~500 | Column type detection |
| `src/state/dataset_info.py` | ~100 | Dataset state object |

---

## 1.2 The Coverage-First Algorithm Explained

### The Problem Being Solved

When you have a large CSV with 10,000+ rows, you can't send it all to an LLM. But random sampling might miss important categories. For example:
- If 95% of rows are "California" and 5% are other states
- Random sampling might miss rare states entirely
- The LLM wouldn't know those states exist in the data

### The Solution: Coverage-First Sampling

```
┌─────────────────────────────────────────────────────────────────┐
│                    SAMPLING ALGORITHM FLOW                       │
└─────────────────────────────────────────────────────────────────┘

INPUT: Large CSV (e.g., 10,000 rows)
OUTPUT: Small sample (40-100 rows) with ALL categorical values covered

PHASE 1: EARLY EXIT CHECK
─────────────────────────
  If dataset ≤ 40 rows:
    → Copy entire file (no sampling needed)
    → DONE

PHASE 2: PRESCAN (Read ALL rows first)
──────────────────────────────────────
  │
  ├─ Detect CATEGORICAL columns:
  │    • Calculate: unique_values / total_rows
  │    • If ratio ≤ 10% → it's categorical
  │    • Example: "State" column with 50 states in 10,000 rows = 0.5% → categorical
  │
  ├─ Detect ID columns (by name pattern):
  │    • Patterns: "ID", "CODE", "FIPS", "KEY"
  │    • These are EXCLUDED from coverage tracking
  │
  ├─ Smart Column Analysis (skip unhelpful columns):
  │    • CONSTANT columns: all same value (e.g., Country="USA")
  │    • DERIVED columns: percentages, calculated values
  │    • METADATA columns: long text descriptions
  │    • REDUNDANT pairs: 1:1 mapping (FIPS ↔ County Name)
  │
  ├─ Build "uncovered_values" map:
  │    • State → {CA, TX, NY, FL, ...all 50 states}
  │    • Year → {2020, 2021, 2022, 2023}
  │
  └─ Calculate numeric ranges (for quartile coverage):
       • Find min, Q1, median, Q3, max for numeric columns

PHASE 3: MAIN SAMPLING LOOP
───────────────────────────
  For each row in input:
    │
    ├─ FILTER 1: Is it a duplicate pattern?
    │    • Get "signature" = values of key columns
    │    • If already have row with same signature → SKIP
    │
    ├─ FILTER 2: Is it an aggregation/total row?
    │    • Check first 5 columns for keywords:
    │      "Total", "All", "Sum", "Overall", "National"
    │    • Allow max 2 aggregation rows, then SKIP extras
    │
    ├─ PRIORITY 1: Does it cover NEW categorical values?
    │    • Check each categorical column
    │    • If row has State="Wyoming" and Wyoming is uncovered:
    │      → SELECT (mark Wyoming as covered)
    │
    ├─ PRIORITY 2: Does it extend numeric range?
    │    • Check if value falls in uncovered quartile
    │    • Example: Have Q1,Q2,Q3 covered, need Q4
    │      → SELECT if row has Q4-range value
    │
    ├─ FALLBACK: Random sampling (after coverage complete)
    │    • If all categorical values covered
    │    • Apply random rate (e.g., 1%) for diversity
    │
    └─ When row is SELECTED:
         • Write to output file
         • Mark categorical values as "covered"
         • Track row signature (for duplicate detection)
         • Update numeric coverage

PHASE 4: MINIMUM ROW GUARANTEE
──────────────────────────────
  After coverage loop:
    │
    ├─ If selected_rows < 40:
    │    → Add random rows to reach 40
    │
    └─ Elif selected_rows < 80:
         → Add more random rows to approach 80

OUTPUT: Sampled CSV with 40-100 rows
```

### Concrete Example

```
INPUT DATA (5,000 rows):
┌──────────┬──────┬────────────┬─────────┐
│ State    │ Year │ Population │ Growth% │
├──────────┼──────┼────────────┼─────────┤
│ CA       │ 2020 │ 39538223   │ 1.2     │  ← Row 1
│ CA       │ 2021 │ 39538223   │ 0.8     │  ← Row 2
│ CA       │ 2022 │ 39029342   │ -1.3    │  ← Row 3
│ ... (4000 more CA rows) ...              │
│ WY       │ 2020 │ 576851     │ 0.5     │  ← Row 4500 (rare!)
│ WY       │ 2021 │ 578759     │ 0.3     │  ← Row 4501
│ Total    │ All  │ 331449281  │ 0.7     │  ← Row 5000 (aggregation)
└──────────┴──────┴────────────┴─────────┘

PRESCAN DETECTS:
  • State is CATEGORICAL (50 unique / 5000 rows = 1%)
  • Year is CATEGORICAL (3 unique / 5000 rows = 0.06%)
  • Population is NUMERIC (track quartiles)
  • Growth% is DERIVED → SKIP tracking

UNCOVERED VALUES:
  • State: {CA, TX, NY, FL, ..., WY} (50 states)
  • Year: {2020, 2021, 2022}

SAMPLING DECISIONS:
  Row 1: State=CA uncovered → SELECT (CA now covered)
  Row 2: State=CA already covered, Year=2021 uncovered → SELECT
  Row 3: State=CA covered, Year=2022 uncovered → SELECT
  Row 4-4499: CA covered, Years covered → SKIP most, random few
  Row 4500: State=WY uncovered → SELECT (WY now covered!)
  Row 4501: WY covered → SKIP (duplicate pattern)
  Row 5000: "Total" detected → SELECT (but only 1 allowed more)

OUTPUT (example 52 rows):
  • 1 row for each of 50 states (coverage)
  • 2 aggregation rows (limited)
  • All 3 years covered
```

---

## 1.3 Layer-by-Layer Breakdown

### Layer 3: SamplingAgent (ADK Orchestration)

**File:** `src/agents/sampling_agent.py`

**Pattern:** Simple BaseAgent (deterministic logic, no LLM needed)

**Execution Flow:**
```
_run_async_impl(ctx)
│
├─ 1. Check skip_sampling flag (lines 64-75)
│  └─ If True: return early with success
│
├─ 2. Get current_dataset from state (lines 77-89)
│  └─ If missing: return error
│
├─ 3. Check for existing sampled files (lines 91-123)
│  └─ If exist AND not force_resample: reuse existing
│
├─ 4. Discover input files (lines 133-151)
│  └─ Pattern: *_input.csv (excluding *sampled*)
│
├─ 5. Sample each file (lines 153-176)
│  ├─ output = {input_stem}_sampled_data.csv
│  └─ Call sample_data(input, output)
│
└─ 6. Update state (lines 191-202)
   ├─ ctx.session.state["sampled_data_files"]
   ├─ ctx.session.state["combined_sampled_data"]
   ├─ ctx.session.state["sampling_success"]
   └─ current_dataset.sampled_data_files (direct object update)
```

**State Inputs:**

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `current_dataset` | DatasetInfo | Required | Dataset being processed |
| `skip_sampling` | bool | False | Skip sampling entirely |
| `force_resample` | bool | False | Ignore existing files |

**State Outputs:**

| Key | Type | Purpose |
|-----|------|---------|
| `sampled_data_files` | List[str] | Paths to sampled files |
| `combined_sampled_data` | str | Primary sampled file path |
| `sampling_success` | bool | Success indicator |
| `error` | str | Error message if failed |

**Dual Update Pattern:**
The agent updates BOTH ADK session state AND the DatasetInfo object directly. This handles ADK InMemorySessionService reliability issues.

### Layer 2: Tool Wrapper (sample_data)

**File:** `src/tools/data_sampler_tool.py`

**Function Signature:**
```python
def sample_data(
    input_file: str,      # Required: path to input CSV
    output_file: str      # Required: path to write sampled CSV
) -> Dict[str, Any]:      # Return structure
```

**Return Structure:**
```python
{
    "success": bool,           # True if sampling succeeded
    "output_file": str,        # Path to generated sampled CSV (or empty)
    "rows_sampled": int,       # Number of rows in output (including headers)
    "error": str               # Error message if failed (or empty string)
}
```

**Baked-in Config (lines 54-65):**
```python
sampler_config = {
    'sampler_output_rows': 100,
    'sampler_rows_per_key': 5,
    'sampler_categorical_threshold': 0.1,
    'sampler_max_aggregation_rows': 2,
    'sampler_ensure_coverage': True,
    'sampler_smart_columns': True,
    'sampler_detect_aggregation': True,
    'sampler_auto_detect_categorical': True,
}
```

### Layer 1: Core Sampling Engine (DataSampler)

**File:** `src/pipeline/sampling/data_sampler.py`

**Key Data Structures:**
```python
# Categorical column tracking
self._categorical_columns = {}  # col_index -> set of all unique values
self._uncovered_values = {}     # col_index -> set of uncovered values
self._id_column_indices = set() # indices of detected ID columns
self._headers_list = []         # list of header names by index

# Smart column analysis
self._skip_columns = set()      # columns to skip for uniqueness tracking
self._column_analysis = None    # ColumnAnalysisResult from analyzer
self._numeric_ranges = {}       # col_index -> {min, max, q1, q2, q3}
self._numeric_coverage = {}     # col_index -> set of covered quartiles

# Aggregation row tracking
self._aggregation_keywords = ['total', 'all', 'sum', 'overall', 'national', ...]
self._selected_aggregation_rows = 0
self._max_aggregation_rows = 2

# Duplicate pattern tracking
self._selected_signatures = set()  # signatures of already selected rows
```

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `_prescan_for_categorical_columns()` | Read ALL rows, detect categorical columns |
| `_detect_categorical_columns()` | Calculate cardinality ratio, identify categorical |
| `_run_smart_column_analysis()` | Use ColumnAnalyzer to skip constant/derived columns |
| `select_row()` | **CRITICAL** - Decide if row should be sampled |
| `_covers_new_categorical_value()` | Check if row covers uncovered categorical value |
| `_is_aggregation_row()` | Detect Total/Sum rows |
| `_get_row_signature()` | Generate signature for duplicate detection |
| `sample_csv_file()` | Main entry point - orchestrates all phases |

---

## 1.4 Configuration & Defaults

### Key Configuration Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `sampler_output_rows` | 100 | Hard max rows |
| `sampler_min_rows` | 40 | Minimum output (will add random if below) |
| `sampler_max_rows` | 80 | Soft target for output size |
| `sampler_header_rows` | 1 | Number of header rows to skip |
| `sampler_rows_per_key` | 5 | Max rows per unique value |
| `sampler_categorical_threshold` | 0.1 | 10% unique ratio → categorical |
| `sampler_ensure_coverage` | True | Enable coverage-first logic |
| `sampler_detect_aggregation` | True | Filter Total/Sum rows |
| `sampler_max_aggregation_rows` | 2 | Max total rows to include |
| `sampler_smart_columns` | True | Skip constant/derived columns |
| `sampler_auto_detect_categorical` | True | Auto-detect categorical columns |
| `sampler_auto_detect_headers` | True | Auto-detect header row count |

### File Patterns

**Input Discovery:**
```python
# Matches: *_input.csv (excluding *sampled*)
if f.suffix == '.csv' and 'input' in f.name.lower() and 'sampled' not in f.name.lower()
```

**Output Naming:**
```python
output_file = input_file.parent / f"{input_file.stem}_sampled_data.csv"
# Example: cdc_input.csv → cdc_input_sampled_data.csv
```

**Reuse Detection:**
```python
# Matches: *sampled*.csv
if file.suffix == '.csv' and 'sampled' in file.name.lower()
```

---

## 1.5 Integration with Pipeline

```
Discovery → populates current_dataset with input_data_files
    ↓
Sampling → reads input_data_files
         → writes sampled_data_files
         → updates current_dataset
    ↓
Schema Selection → reads combined_sampled_data
                 → generates preview for Gemini
                 → picks schema category
    ↓
PVMAP Generation → uses sampled data in prompt
                 → validates on FULL data (not sampled!)
    ↓
Evaluation → compares vs ground truth
```

**Key Insight:** Sampling creates small sample for LLM prompt, but validation runs on FULL dataset. This is critical for catching issues.

---

# Part 2: Expert Conversation Analysis (PVMAP Specialist Feedback)

## 2.1 Full Conversation Summary

The following is a detailed analysis of the conversation with **Sanika Prasad (xWF)**, a PVMAP expert, discussing best practices for data sampling and PVMAP creation.

### Context: The Dataset

Sanika introduced a dataset concerning **average monthly wages of salaried employees**, segregated by:
- Country
- State
- Gender (Male/Female)
- Rural/Urban population
- Quarter (time period)

Values are in INR (Indian Rupees).

### Topic 1: Data Overview and PV Map Preparation

**Sanika's Key Point:**
> "To create a PV map, the first row should be designated as key/property and value."

**Interpretation:** The PVMAP structure requires understanding which columns are keys (dimensions that define the observation) vs values (the measurements being recorded).

### Topic 2: StatVar and Data Stat Uniqueness

**Sanika's Explanation:**
> "Every value in the output CSV should be a unique entry without duplicates. Each row in the dataset represents a unique combination of properties (e.g., gender, rural/urban, quarter), and the statware must capture these major elements to denote the data point's perfect meaning."

**Nehil's Clarification:** "This means distinct values must be present."

**Key Insight:** The StatVar (statistical variable) for each data point must contain ALL differentiating properties. Missing any property would create duplicate or ambiguous StatVars.

### Topic 3: Identifying Unique Data Characteristics for PV Mapping

**Discussion:**
Sanika and Nehil discussed that identifying which columns provide a **complete and unique picture** of the data is crucial for PV mapping.

**Sanika's Explanation:**
> "We are more interested in the 'stat' created for a value rather than the value itself. The statware (SV) should denote the specific conditions like average salary for male, rural residents during a specific quarter."

**Nehil's Summary:** "This process involves extracting the meaning of each unique row of data."

### Topic 4: Data Understanding and PV Map Creation Strategy

**Sanika's Emphasis:**
> "Thoroughly understanding the data reduces the time required to create the PV map. This understanding helps in capturing all necessary property values to ensure every data point is accounted for."

**Nehil's Confirmation:** "Understanding the data's essence makes map creation easier and helps provide the necessary context to the LLM."

### Topic 5: Practical Demonstration

**Sanika demonstrated extracting meaning from a row:**

For the first row of the wages data:
> "The value for the quarter April-June in 2017 to 2018 quarter for male in rural sector in India is 1,423. Correct, their average salary."

This breaks down as:
```
Observation:
  - observationAbout: India (country)
  - observationDate: Apr-Jun 2017-2018
  - value: 1423 (INR)

StatVar Components:
  - measuredProperty: averageWage
  - populationType: Person
  - gender: Male
  - placeOfResidenceClassification: Rural
  - measurementQualifier: Salaried employees
```

---

## 2.2 Key Concepts Explained

### Concept 1: StatVar Must Denote "Perfect Meaning"

**Expert Quote:**
> "The statware for a value must consist of all main key elements to denote the value's perfect meaning"

**What This Means:**

For a wages dataset, each StatVar must capture:
- **Gender:** Male/Female
- **Sector:** Rural/Urban
- **Salary Type:** That it is the monthly salary/average wage
- **Time/Quarter:** The year and quarter

**Example StatVar Structure:**
```
dcid:Mean_WageOrSalary_Worker_Male_Rural_Quarterly

Components:
  - Mean (aggregation type)
  - WageOrSalary (measured property)
  - Worker (population type)
  - Male (gender constraint)
  - Rural (place classification constraint)
  - Quarterly (measurement period)
```

### Concept 2: No Duplicates from Same Source

**Expert Quote:**
> "Every value in the output CSV should be a unique entry, and no duplicates should be formed from the same source for the same entry."

**What This Means:**

If the data has:
- 2 genders × 2 sectors × 4 quarters × 30 states = 480 unique observations
- Each observation must map to a UNIQUE StatVar
- Missing any dimension would cause collisions

**Example of What Goes Wrong:**

If Quarter is skipped:
```
Row 1: Male, Rural, Q1, Maharashtra → StatVar: Wage_Male_Rural_Maharashtra
Row 5: Male, Rural, Q2, Maharashtra → StatVar: Wage_Male_Rural_Maharashtra  ← DUPLICATE!
```

The two rows would create the same StatVar, losing the temporal dimension.

### Concept 3: The "Skeleton" of Data

**Expert Quote:**
> "Understanding the data's skeleton determines which columns are important to capture to ensure all differentiating elements are covered."

**What This Means:**

Before sampling, we need to understand:
1. **Key columns:** Define what entity this observation is about (State, Country)
2. **Dimension columns:** Categorical constraints that differentiate StatVars (Gender, Sector, Quarter)
3. **Value columns:** The actual measurements (AvgWage, Count)

**The "skeleton" is the combination of dimension columns.**

---

## 2.3 The "Skeleton" of Data

### Extracting Meaning from Each Row

**Expert's Demonstration:**
> "De taking out the meaning of each row... The value for the quarter April-June in 2017 to 2018 quarter for male in rural sector in India is 1,423."

**Breaking Down the Row:**

```csv
Country,State,Gender,Sector,Quarter,AvgWage
India,Maharashtra,Male,Rural,Apr-Jun 2017,1423
```

**Semantic Interpretation:**
```
WHAT is being measured?
  → Average wage/salary

WHO is being measured?
  → Salaried employees (implicit from dataset context)
  → Male (gender constraint)
  → Rural residents (sector constraint)

WHERE?
  → India → Maharashtra (geographic hierarchy)

WHEN?
  → April-June 2017 (quarter)

VALUE?
  → 1423 INR
```

**Resulting StatVar Pattern:**
```
Mean_WageOrSalary_SalariedWorker_Male_Rural

Applied to:
  - observationAbout: wikidataId/Q1191 (Maharashtra)
  - observationDate: 2017-Q2
  - value: 1423
```

### Why This Matters for Sampling

The sampler must ensure that the LLM sees enough examples to understand:

1. **All dimension values exist:** Male AND Female, Rural AND Urban, Q1 AND Q2 AND Q3 AND Q4
2. **Combinations matter:** (Male, Rural, Q1) is different from (Male, Urban, Q1)
3. **The structure is consistent:** Every row follows the same skeleton

**If sampling misses combinations**, the LLM might:
- Not realize (Male, Urban, Q3) is a valid combination
- Generate a PVMAP that only handles seen combinations
- Fail validation when processing full dataset with unseen combinations

---

# Part 3: Gap Analysis: Current vs Required

## 3.1 Values vs Combinations

### Current Approach: Independent Column Coverage

```
INPUT: Dataset with State (50 values), Year (4 values), Gender (2 values)
       Total unique combinations: 50 × 4 × 2 = 400 StatVars

CURRENT TRACKING:
  State:  {CA, TX, NY, FL, ...} → Need 50 samples to cover
  Year:   {2020, 2021, 2022, 2023} → Need 4 samples to cover
  Gender: {Male, Female} → Need 2 samples to cover

RESULT: Once ~56 rows selected (covering all individual values),
        sampler stops prioritizing and uses random selection.

PROBLEM: 400 unique combinations exist, but sample might only show 56-80
         Many (State, Year, Gender) tuples never appear in sample!
```

### Expert's Required Approach: Combination Coverage

```
NEEDED TRACKING:
  (State, Year, Gender) combinations:
    {(CA, 2020, Male), (CA, 2020, Female), (CA, 2021, Male), ...}

RESULT: Track which COMBINATIONS are covered, not just individual values.
        Prioritize rows that cover NEW combinations.

GOAL: Sample shows representative cross-section of dimension space,
      so LLM understands the full uniqueness structure.
```

---

## 3.2 Visual Comparison

### Current Approach (Independent Column Coverage)

```
          State Coverage    Year Coverage     Gender Coverage
          ┌───────────┐     ┌───────────┐     ┌───────────┐
          │ CA ✓      │     │ 2020 ✓    │     │ Male ✓    │
          │ TX ✓      │     │ 2021 ✓    │     │ Female ✓  │
          │ NY ✓      │     │ 2022 ✓    │     └───────────┘
          │ ...50     │     │ 2023 ✓    │
          └───────────┘     └───────────┘

Tracked: 50 + 4 + 2 = 56 individual values
Combinations possible: 50 × 4 × 2 = 400
Combinations in sample: Unknown (not tracked)
```

### Required Approach (Combination Coverage)

```
          (State, Year, Gender) Combinations
          ┌────────────────────────────────┐
          │ (CA, 2020, Male) ✓             │
          │ (CA, 2020, Female) ✓           │
          │ (CA, 2021, Male) ✓             │
          │ (TX, 2020, Male) ✓             │
          │ (TX, 2020, Female) ✗ MISSING   │
          │ ...                            │
          │ 400 total combinations         │
          └────────────────────────────────┘

Tracked: All 400 dimension combinations
Coverage: Can calculate % of combinations represented
```

### The Expert's Concern in Practice

**Expert's Quote:**
> "If the quarter (e.g., April-June) were skipped, duplicate data for 'male' and 'rural' would be found further down the table"

**This means:**
- If Quarter is not tracked as part of the uniqueness key
- Rows for (Male, Rural, Q1) and (Male, Rural, Q2) would look like "duplicates"
- The sampler might skip Q2 thinking it's redundant
- The PVMAP would fail when Q2 data appears in full dataset

---

# Part 4: Research: Concrete Evidence

## 4.1 India NFHS Dataset

**Location:** `input/india_nfhs/test_data/`

**Dimensional Structure:**
- 34 unique States
- 701 unique Districts (fine-grained geographic hierarchy)
- 1 Year (2019)
- 704 unique State-District combinations (nested hierarchy)

**Sampling Results:**

| Metric | Full Dataset | Sampled | Gap |
|--------|--------------|---------|-----|
| Total rows | 729 | 125 (17%) | - |
| Unique States | 34 | 6 (17.6%) | 28 states missing |
| Unique Districts | 701 | 100 | 601 districts missing |
| **State-District combos** | 704 | 100 | **604 missing (85.8%)** |

**Analysis:**
The sampler achieves 100% coverage of individual district values (because district names are globally unique). However, it misses 85% of State-District dimension combinations.

**Impact on PVMAP:**
- LLM doesn't see the State→District hierarchy pattern
- A StatVar like `Median_Earnings_State_District_Gender` might incorrectly handle districts
- Districts from different states might be conflated

---

## 4.2 INPE Fire Dataset (Brazil)

**Location:** `input/inpe_fire/test_data/`

**Dimensional Structure:**
- 31 unique Years (1998-2025, plus summary rows)
- 27 unique Places (Brazilian states/regions)
- 837 unique Year-Place combinations (nearly complete cartesian product)

**Sampling Results:**

| Metric | Full Dataset | Sampled | Gap |
|--------|--------------|---------|-----|
| Total rows | 838 | 101 (12%) | - |
| Unique Years | 31 | 31 (100%) | ✓ Complete |
| Unique Places | 27 | 9 (33%) | 18 places missing |
| **Year-Place combos** | 837 | 100 | **737 missing (88%)** |

**Analysis:**
Year coverage is complete (100%) but place coverage is only 33%. The sample shows time-series data for only 1/3 of Brazilian regions.

**Impact on PVMAP:**
- LLM sees temporal patterns but only for 9 of 27 regions
- Regional StatVars might not generalize to all Brazilian states
- Dimension combinations like `(Year=2020, Place=Amazonas)` may not appear

---

## 4.3 Validation of Expert's Concern

The expert said:
> "If the quarter (e.g., April-June) were skipped, duplicate data for 'male' and 'rural' would be found further down the table"

**Confirmed in INPE Fire:** Year coverage is complete but Place coverage is incomplete. This means Year-Place combinations are systematically missing for 18 places.

**Key Insight:** The current sampler uses **independent column coverage** when the expert wants **cartesian product coverage**:

- **Independent:** Track `States={A,B,C}` and `Years={1,2,3}` separately
- **Cartesian:** Track `(State,Year)={(A,1),(A,2),(A,3),(B,1),...}` combinations

For a dataset with 50 states × 4 years × 2 genders = 400 unique StatVars, the current sampler might output only 56 rows (50 + 4 + 2 = individual values covered) while missing 344 combinations (86%).

---

# Part 5: Root Cause Analysis

## 5.1 Code Location

**File:** `src/pipeline/sampling/data_sampler.py`
**Lines:** 636-679 (coverage detection logic)

## 5.2 The Problematic Code

```python
def _covers_new_categorical_value(self, row: list[str]) -> bool:
    """Check if row covers any uncovered categorical value."""
    for col_idx, uncovered in self._uncovered_values.items():
        if col_idx < len(row) and row[col_idx] in uncovered:
            return True  # ← PROBLEM: Checks SINGLE columns only
    return False
```

**What this does:**
1. Iterates through categorical columns
2. Checks if ANY column has an uncovered value
3. Returns True if ANY single column has a new value

**What it misses:**
- Does NOT track combinations of column values
- Once all individual values are covered, stops prioritizing
- Remaining rows selected randomly, regardless of combination coverage

## 5.3 Selection Logic Flow

```python
# From select_row() method, lines 1039-1141

def select_row(self, row, sample_rate=-1):
    # ... duplicate and aggregation checks ...

    # Coverage-first logic
    if ensure_coverage and self._prescan_complete:
        if self._covers_new_categorical_value(row):  # ← Single-column check
            self._counters.add_counter('sampler-coverage-selected-rows', 1)
            return True

        # After all individual values covered, uses random sampling
        if self._all_categorical_covered():
            if sample_rate > 0 and random.random() <= sample_rate:
                return True
            return False

    # ... fallback logic ...
```

## 5.4 Data Structure Limitation

```python
# Current data structures in reset() method, lines 189-242

self._categorical_columns = {}  # col_index -> set of all unique values
self._uncovered_values = {}     # col_index -> set of uncovered values

# NO data structure for tracking combinations:
# self._uncovered_combinations = set()  # ← Missing
```

## 5.5 Impact Summary

| Aspect | Current Behavior | Required Behavior |
|--------|-----------------|-------------------|
| Tracking | Per-column values | Cross-column combinations |
| Coverage check | Any single column new | Any combination new |
| Stop condition | All individual values covered | Representative combinations covered |
| Randomness | After coverage, random fill | Strategic combination filling |

---

# Part 6: Proposed Improvements

## 6.1 Improvement 1: Detect Dimension Columns

**Purpose:** Identify columns that together define StatVar uniqueness

**Implementation:**
```python
def _detect_dimension_columns(self, headers: list[str], all_rows: list) -> set[int]:
    """
    Dimension columns are properties that, combined, make each row's StatVar unique.

    Heuristics:
    1. Categorical columns (already detected)
    2. NOT value columns (numeric columns that vary widely)
    3. NOT ID/key columns (unique per row)
    4. Common patterns: gender, age, sector, period, geographic level
    """
    dimension_cols = set()
    dimension_patterns = [
        'gender', 'sex', 'male', 'female',
        'sector', 'rural', 'urban',
        'age', 'age_group', 'agegroup',
        'quarter', 'period', 'year', 'month',
        'category', 'type', 'class',
        'race', 'ethnicity',
        'education', 'income_level',
        'state', 'country', 'region', 'district'
    ]

    for col_idx, header in enumerate(headers):
        header_lower = header.lower()
        if any(pattern in header_lower for pattern in dimension_patterns):
            dimension_cols.add(col_idx)

        # Also include categorical columns that aren't ID columns
        if col_idx in self._categorical_columns and col_idx not in self._id_column_indices:
            dimension_cols.add(col_idx)

    return dimension_cols
```

## 6.2 Improvement 2: Track Dimension Combinations

**Purpose:** Track which (State, Year, Gender, ...) tuples are covered

**Implementation:**
```python
def _build_dimension_combinations(self, all_rows: list, dimension_cols: set[int]) -> set[tuple]:
    """Build set of all unique dimension combinations in the data."""
    combinations = set()
    for row in all_rows:
        combo = tuple(row[col] for col in sorted(dimension_cols) if col < len(row))
        combinations.add(combo)
    return combinations

def _covers_new_combination(self, row: list[str]) -> bool:
    """Check if row covers a NEW dimension combination."""
    combo = tuple(row[col] for col in sorted(self._dimension_columns) if col < len(row))
    return combo in self._uncovered_combinations

def _mark_combination_covered(self, row: list[str]) -> None:
    """Mark a dimension combination as covered."""
    combo = tuple(row[col] for col in sorted(self._dimension_columns) if col < len(row))
    self._uncovered_combinations.discard(combo)
```

## 6.3 Improvement 3: Combination-First Selection Strategy

**Purpose:** Prioritize rows that cover NEW combinations

**Implementation:**
```python
def select_row(self, row: list[str], sample_rate: float = -1) -> bool:
    # ... existing filters (duplicate, aggregation) ...

    # NEW PRIORITY 1: Dimension combination coverage
    if self._dimension_columns and self._covers_new_combination(row):
        self._counters.add_counter('sampler-combination-selected-rows', 1)
        return True

    # PRIORITY 2: Categorical value coverage (existing)
    if ensure_coverage and self._prescan_complete:
        if self._covers_new_categorical_value(row):
            self._counters.add_counter('sampler-coverage-selected-rows', 1)
            return True

    # ... rest of existing logic ...
```

## 6.4 Improvement 4: Output Data Skeleton Summary

**Purpose:** Generate summary of the data's uniqueness structure for downstream use

**Implementation:**
```python
def get_data_skeleton_summary(self) -> dict:
    """
    Generate a summary of the data's uniqueness structure.

    Returns dict like:
    {
        "dimension_columns": ["Gender", "Sector", "Quarter", "State"],
        "value_columns": ["AvgWage", "Count"],
        "key_columns": ["ID"],
        "total_unique_combinations": 400,
        "sample_covers": 80,
        "coverage_percent": 20.0,
        "sample_combinations": [
            ("Male", "Rural", "Q1", "CA"),
            ("Male", "Rural", "Q2", "CA"),
            ...
        ]
    }
    """
    dimension_names = [self._headers_list[i] for i in sorted(self._dimension_columns)]

    total_combos = len(self._all_combinations)
    covered_combos = total_combos - len(self._uncovered_combinations)

    return {
        "dimension_columns": dimension_names,
        "value_columns": self._detect_value_columns(),
        "key_columns": [self._headers_list[i] for i in self._id_column_indices],
        "total_unique_combinations": total_combos,
        "sample_covers": covered_combos,
        "coverage_percent": (covered_combos / total_combos * 100) if total_combos > 0 else 0,
    }
```

## 6.5 Improvement 5: Enhanced Prompt Guidance

**Purpose:** Help LLM understand the dimension structure

**File:** `src/resources/prompts/improved_pvmap_prompt.txt`

**Addition:**
```
## DATA SKELETON ANALYSIS

The sampled data represents a dataset where each row is a UNIQUE statistical observation.

### Dimension Columns (define StatVar uniqueness):
{{DIMENSION_COLUMNS}}

### Value Columns (the measurements):
{{VALUE_COLUMNS}}

### Uniqueness Pattern:
Each unique combination of dimension values creates a DISTINCT StatVar.
Example: Average_Monthly_Wage_[Gender]_[Sector]_[Quarter]_[State]

### Coverage Summary:
- Total unique combinations in full data: {{TOTAL_COMBINATIONS}}
- Combinations shown in sample: {{SAMPLE_COMBINATIONS}}
- Coverage: {{COVERAGE_PERCENT}}%

IMPORTANT: Your PVMAP must handle ALL combinations of dimension values,
not just the specific combinations shown in the sample. The dimension
columns define the structure; the sample shows representative patterns.
```

---

# Part 7: Implementation Considerations

## 7.1 New Configuration Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `sampler_detect_dimensions` | True | Enable dimension column detection |
| `sampler_combination_coverage` | True | Track dimension combinations |
| `sampler_min_combination_coverage` | 0.2 | Minimum % of combinations to cover (20%) |
| `sampler_max_dimension_columns` | 5 | Limit dimension tracking to prevent explosion |
| `sampler_output_skeleton` | True | Generate skeleton summary |

## 7.2 Files to Modify

| File | Changes |
|------|---------|
| `src/pipeline/sampling/data_sampler.py` | Add dimension detection, combination tracking, skeleton output |
| `src/pipeline/sampling/column_analyzer.py` | Add dimension column classification |
| `src/tools/data_sampler_tool.py` | Return skeleton summary in result dict |
| `src/agents/sampling_agent.py` | Store skeleton summary in state |
| `src/resources/prompts/improved_pvmap_prompt.txt` | Add skeleton guidance section |

## 7.3 Complexity Considerations

**Cartesian Product Explosion:**
- If 5 dimension columns with 10 values each: 10^5 = 100,000 combinations
- Need to limit tracking to most important dimension pairs
- Or use sampling of combinations rather than full coverage

**Proposed Mitigation:**
```python
# Limit to top 3 most important dimension columns
if len(dimension_cols) > self._config.get('sampler_max_dimension_columns', 3):
    # Prioritize by: (1) known dimension patterns, (2) lowest cardinality
    dimension_cols = self._rank_and_limit_dimensions(dimension_cols, limit=3)
```

## 7.4 Testing Strategy

1. **Unit Tests:**
   - Dimension detection on known datasets
   - Combination tracking accuracy
   - Skeleton summary correctness

2. **Integration Tests:**
   - Full pipeline on wages-type dataset
   - Check PVMAP handles all combinations

3. **Regression Tests:**
   - Existing datasets still pass
   - No performance regression on large files

## 7.5 Implementation Phases

**Phase 1: Analysis & Design** (Current) ✓
- Document gap
- Research evidence
- Propose solution

**Phase 2: Prompt Enhancement** (Low Risk)
- Add skeleton analysis to PVMAP prompt
- No sampler changes required
- Quick win for LLM understanding

**Phase 3: Sampler Enhancement** (Medium Complexity)
- Add dimension detection
- Add combination tracking
- Add skeleton output

**Phase 4: Validation & Tuning**
- Test on problem datasets (India NFHS, INPE Fire)
- Tune combination coverage thresholds
- Measure PVMAP accuracy improvement

---

## Appendix A: Expert Conversation - Full Excerpts

### On StatVar Uniqueness
> "Every value in the output CSV should be a unique entry without duplicates. Each row in the dataset represents a unique combination of properties (e.g., gender, rural/urban, quarter), and the statware must capture these major elements to denote the data point's perfect meaning."

### On Identifying Key Elements
> "The resulting statistical variable for a value must consist of all the main key elements required to denote the value's perfect meaning. For the example data (monthly wages), the key elements must cover: Gender (Male/Female), Area/Sector (Rural/Urban), Salary Type, Time/Quarter."

### On Data Understanding
> "The more time spent on understanding, the less time it takes to create the PV map. This means comprehending what the data is about and how we can capture the property values to ensure every value is included in the output."

### On Extracting Meaning
> "The value for the quarter April-June in 2017 to 2018 quarter for male in rural sector in India is 1,423. Correct, their average salary."

### On the Skeleton Approach
> "Understanding the data's skeleton determines which columns are important to capture to ensure all differentiating elements (like gender, sector, age, etc.) are covered to create the appropriate output statV."

---

## Appendix B: Related Code References

### Data Sampler Core Logic
- `src/pipeline/sampling/data_sampler.py` - Main sampling engine (1444 lines)
- Lines 636-679: Coverage detection
- Lines 1039-1141: Row selection logic
- Lines 909-990: Prescan for categorical columns

### Column Analysis
- `src/pipeline/sampling/column_analyzer.py` - Column type detection
- Lines 170-210: Constant column detection
- Lines 306-365: Derived column detection

### Agent Integration
- `src/agents/sampling_agent.py` - ADK agent wrapper (210 lines)
- `src/tools/data_sampler_tool.py` - Tool interface (136 lines)

### PVMAP Generation
- `src/resources/prompts/improved_pvmap_prompt.txt` - LLM prompt template
- `run_pvmap_pipeline.py` - Pipeline orchestration

---

## Appendix C: Debugging Commands

```bash
# Check sampled files exist
ls -l input/{dataset}/test_data/*sampled*

# Manual resample
python3 -c "
from src.pipeline.sampling.data_sampler import sample_csv_file
sample_csv_file('input/dataset/test_data/input.csv', 'output.csv')
"

# Force resample in pipeline
# Set force_resample=True in state

# Check sampling logs
tail -100 logs/{dataset_name}/generation_*.log | grep -i sample
```

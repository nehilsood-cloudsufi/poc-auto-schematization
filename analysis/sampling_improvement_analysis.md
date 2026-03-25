# Data Understanding & Sampling Agent: Complete Analysis & Implementation Plan

## Executive Summary

This document provides a comprehensive analysis of the data sampling pipeline and defines the **Data Understanding & Sampling Agent** - a transformation from a simple "row selector" into an intelligent agent that captures the **essence and context** of datasets for PVMAP generation.

### Key Components

1. **Complete understanding of the current sampling process** - How data flows through the three-layer architecture
2. **Expert feedback analysis** - Insights from PVMAP specialist (Sanika Prasad) on StatVar uniqueness
3. **Gemini consultation results** - AI-validated heuristics for dimension detection and universal templates
4. **Gap identification** - Where the current approach falls short (85%+ missing combinations)
5. **Improved solution architecture** - Data Understanding Agent with context generation
6. **Implementation plan** - Phased approach with testing checklist

**The Core Issue:** The current sampler tracks coverage of individual categorical **values**, but PVMAP generation requires understanding dimension **combinations** that define unique StatVars.

**The Solution:** Transform the sampling agent to:
1. **Understand the data** - What does this dataset represent? What StatVars can it produce?
2. **Identify the data skeleton** - Which columns define uniqueness? What are the dimensions?
3. **Sample strategically** - Select rows that demonstrate the dimension structure
4. **Generate context** - Produce a DataContext package that flows through the pipeline

---

## NEW: Gemini Consultation Summary

### How We Use Gemini for Data Intelligence

The improved sampling agent uses **Gemini consultation** to validate and refine heuristics for understanding data structure. This is NOT using Gemini at runtime for each dataset, but rather to establish **universal patterns** that work across all domains.

**Tool Used:** `src/tools/gemini_query_tool.py`

**Questions Asked:**
1. What determines StatVar uniqueness in Data Commons?
2. What heuristics detect dimension columns automatically?
3. Should sampling prioritize individual values or dimension combinations?
4. How to handle cartesian product explosion?
5. What is a "data skeleton" and how should it be summarized?
6. How to use MCP for StatVar discovery?

**Results Saved:** `output/gemini_consultation_results.json`

### Key Gemini-Validated Insights

#### 1. The Uniqueness Tuple (StatVarObservation)
Every StatVarObservation in Data Commons is uniquely identified by:
- **observationAbout** (Place): The geographic entity
- **observationDate** (Time): The temporal dimension
- **variableMeasured** (StatVar): The statistical variable definition

The StatVar itself is defined by combining dimension columns (e.g., `Count_Person_Female_Age18To24`).

#### 2. Column Classification Taxonomy (5 Roles)
Gemini recommends classifying columns into 5 roles:

| Role | Description | Example |
|------|-------------|---------|
| **Entity (Place)** | Geographic identifiers | State, FIPS, City, District |
| **Temporal (Time)** | Time periods | Year, Date, Quarter, Month |
| **Dimension** | Properties segmenting population | Gender, Age, Industry, Sector |
| **Measure (Value)** | Statistical count/amount | Population, Rate, Amount |
| **Metadata** | Context (doesn't define uniqueness) | Source, Unit, Notes, MOE |

#### 3. Dimension Detection Heuristics (Gemini-Validated)

**A. Cardinality Ratio Test**
```
Ratio = Unique_Values / Total_Rows

- Dimension Pattern: Ratio < 0.1 (values repeat frequently)
- Value Pattern: Ratio > 0.5 (continuous numeric, rarely repeats)
- Metadata Pattern: Ratio < 0.01 (often constant across dataset)
```

**B. The "Pivot" Test**
- Can you pivot the column to become headers?
- If yes (and it's still readable) → **Dimension**
- If no (creates nonsensical column names) → **Value**

**C. The "Summation" Test**
- If summing the Value column grouped by this column makes sense → **Dimension**
- Example: Summing Population by Gender yields Total Population (meaningful)

**D. Semantic Naming**
- Dimension keywords: gender, sex, age, race, industry, education, status, type, category, sector
- Value keywords: count, total, amount, percent, rate, value, number, sum
- Metadata keywords: source, unit, note, moe, annotation, method
- Place keywords: state, county, city, fips, geo, region, country, place, district
- Time keywords: year, date, month, quarter, period, time

#### 4. Fixed-Pivot Sampling Strategy (Gemini-Recommended)

For a target of ~80 rows:

| Allocation | Rows | Purpose |
|------------|------|---------|
| Diagonal Scan | 20 (25%) | Cover ALL unique dimension values |
| Fixed-Pivot Blocks | 40 (50%) | Vary ONE dimension at a time, fix others |
| Edge Cases | 20 (25%) | Totals, nulls, formatting edge cases |

**Fixed-Pivot Blocks Explained:**
```
BLOCK A: VARY GEOGRAPHY (10 rows)
  Fix: Year=2020, Gender=Female, Sector=Rural
  Vary: State = CA, TX, NY, FL, PA, OH, IL, GA, NC, MI
  → LLM sees: "Only State changes, confirms it's Place"

BLOCK B: VARY TIME (10 rows)
  Fix: State=CA, Gender=Female, Sector=Rural
  Vary: Year = 2015, 2016, 2017, 2018, 2019, 2020...
  → LLM sees: "Only Year changes, confirms it's Time"

BLOCK C: VARY DIMENSIONS (20 rows)
  Fix: State=CA, Year=2020
  Vary: Full cartesian of Gender × Sector
  → LLM sees: "Gender and Sector are INDEPENDENT dimensions"
```

#### 5. Universal Data Skeleton Summary Template

Gemini validated a **universal template** that works across ALL domains (demographics, economy, health, energy, environment):

```markdown
## DATA SKELETON SUMMARY

### Dataset Context
- **Name:** {dataset_name}
- **Topology:** {TIDY_LONG | PIVOTED_WIDE | HYBRID}
- **Population Type:** {Person | Electricity | Atmosphere | etc.}

### Anchors (Required)
- **Geography:** Column `{geo_column}` (Format: {format})
- **Time:** Column `{time_column}` (Format: {format})

### Skeleton Dimensions (Define StatVar)
- `{dimension_1}` → maps to DC property `{dc_property_1}`
- `{dimension_2}` → maps to DC property `{dc_property_2}`

### Measurement Logic
- Value Column: `{value_col}` ({measurement_method}, {unit})

### StatVar Pattern (P+M+C Formula)
`{measurement}_{population}_{constraint_1}_{constraint_2}`

### Coverage
- Total Combinations: {N}
- Sample Covers: {n} ({percent}%)

**IMPORTANT:** Generate PVMAP for ALL dimension combinations, not just those in sample.
```

#### 6. P+M+C Formula for MCP Queries (Universal)

For StatVar discovery via MCP, Gemini validated the **P+M+C Formula**:

```
Query = Population + MeasuredProperty + Constraints

Examples by domain:
- Demographics: "Count Person Female Hispanic Rural"
- Energy: "Electricity Generation Solar"
- Health: "Person MedicalCondition Diabetes 65YearsOrOver"
- Environment: "AirPollutant Concentration PM2.5"
- Economy: "EconomicActivity Amount Manufacturing"
```

This replaces domain-specific queries with a universal pattern.

---

## NEW: Complete Data Understanding & Sampling Flow

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    DATA UNDERSTANDING & SAMPLING AGENT                       │
│                                                                             │
│   INPUT: Raw CSV dataset                                                    │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │ 1. UNDERSTAND THE DATA (Semantic Analysis)                           │ │
│   │    - What does this dataset represent?                               │ │
│   │    - What statistical variables can it produce?                      │ │
│   │    - What entities are being measured?                               │ │
│   │    - What time periods are covered?                                  │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │ 2. IDENTIFY DATA SKELETON (Structural Analysis)                      │ │
│   │    - Which columns define StatVar uniqueness? (Dimensions)           │ │
│   │    - Which columns are Place identifiers?                            │ │
│   │    - Which columns are Time identifiers?                             │ │
│   │    - Which columns are the measurement Values?                       │ │
│   │    - What dimension combinations exist in the data?                  │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │ 3. SAMPLE + GENERATE CONTEXT (Output for Pipeline)                   │ │
│   │    - Strategic sample demonstrating dimension structure              │ │
│   │    - Data Skeleton Summary (markdown for LLM prompts)                │ │
│   │    - Dimension metadata (for downstream validation)                  │ │
│   │    - Coverage statistics (for quality assessment)                    │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│   OUTPUT: Sampled CSV + DataContext (skeleton summary, metadata, stats)    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Two-Phase Sampling Strategy

The agent uses a **two-phase sampling** approach:

```
PHASE 1: Basic Sampling (Existing Algorithm)
    ↓
    Uses current coverage-first algorithm
    Output: ~40-50 rows with categorical coverage
    ↓
PHASE 2: Data Context Generation (NEW)
    ↓
    Analyze the basic sample
    Classify columns (place, time, dimension, value)
    Build dimension domains and combinations
    Output: DataContext object
    ↓
PHASE 3: Advanced Sampling Using Context (NEW)
    ↓
    Use DataContext to guide Fixed-Pivot sampling
    Add 30-40 more rows demonstrating dimension structure
    Output: ~80 rows total + DataContext
    ↓
    Store in ADK state for downstream agents
```

### Detailed Sampling Algorithm Flow

```
═══════════════════════════════════════════════════════════════════════════════
PHASE 1: EARLY EXIT CHECK
═══════════════════════════════════════════════════════════════════════════════

    Dataset ≤ 40 rows?
        YES → Copy entire file → DONE
        NO  → Continue to Phase 2

═══════════════════════════════════════════════════════════════════════════════
PHASE 2: BASIC SAMPLING (Existing Algorithm - Unchanged)
═══════════════════════════════════════════════════════════════════════════════

    Uses existing coverage-first algorithm to:
    - Cover all unique categorical values
    - Sample numeric ranges across quartiles
    - Limit aggregation/total rows

    Output: ~40-50 rows with basic coverage

═══════════════════════════════════════════════════════════════════════════════
PHASE 3: DATA CONTEXT GENERATION (NEW!)
═══════════════════════════════════════════════════════════════════════════════

    STEP 3.1: DIMENSION DETECTION
    ┌─────────────────────────────────────────────────────────────────────┐
    │ For each column, apply 3 tests:                                     │
    │                                                                     │
    │ 1. CARDINALITY TEST                                                 │
    │    unique_values / total_rows < 0.1 → DIMENSION                     │
    │    unique_values / total_rows > 0.5 → VALUE                         │
    │    unique_values / total_rows < 0.01 → METADATA                     │
    │                                                                     │
    │ 2. SEMANTIC TEST                                                    │
    │    Header matches dimension keywords? (gender, age, sector)         │
    │    Header matches place keywords? (state, fips, county)             │
    │    Header matches time keywords? (year, date, quarter)              │
    │    Header matches value keywords? (count, total, amount)            │
    │                                                                     │
    │ 3. SUMMATION TEST                                                   │
    │    Does grouping by column + summing value make sense?              │
    │    Yes → DIMENSION, No → VALUE or METADATA                          │
    └─────────────────────────────────────────────────────────────────────┘

    STEP 3.2: COLUMN CLASSIFICATION OUTPUT
    ┌──────────────┬──────────────┬──────────────┬──────────────┐
    │    PLACE     │    TIME      │  DIMENSION   │    VALUE     │
    ├──────────────┼──────────────┼──────────────┼──────────────┤
    │ State        │ Year         │ Gender       │ Population   │
    │ District     │ Quarter      │ Sector       │ AvgWage      │
    │ FIPS         │ Date         │ Age_Group    │ Count        │
    └──────────────┴──────────────┴──────────────┴──────────────┘
    + METADATA columns (Source, Unit) → SKIP for sampling

    STEP 3.3: BUILD DIMENSION COMBINATIONS

    Dimension columns: [State, Gender, Sector]

    ALL COMBINATIONS (Cartesian product):
    ┌─────────────────────────────────────────────────────────────┐
    │ (CA, Male, Rural)    (CA, Male, Urban)                      │
    │ (CA, Female, Rural)  (CA, Female, Urban)                    │
    │ (TX, Male, Rural)    (TX, Male, Urban)                      │
    │ (TX, Female, Rural)  (TX, Female, Urban)                    │
    │ ... (50 states × 2 genders × 2 sectors = 200 combinations)  │
    └─────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
PHASE 4: ADVANCED SAMPLING USING CONTEXT (NEW!)
═══════════════════════════════════════════════════════════════════════════════

    Target: Add 30-40 more rows using Fixed-Pivot strategy (total ~80 rows)

    STEP 4.1: DIAGONAL SCAN (25% = 20 rows)
    ┌─────────────────────────────────────────────────────────────────────┐
    │ Purpose: Cover ALL unique values across ALL dimension columns       │
    │                                                                     │
    │ Algorithm:                                                          │
    │   Row 1: State=CA, Gender=Male, Sector=Rural     (new values)       │
    │   Row 2: State=TX, Gender=Female, Sector=Urban   (new values)       │
    │   Row 3: State=NY, Gender=Male, Sector=Urban     (new combo)        │
    │   ...                                                               │
    │   Select rows that maximize NEW individual values                   │
    │                                                                     │
    │ Result: All states, genders, sectors appear at least once           │
    └─────────────────────────────────────────────────────────────────────┘

    STEP 4.2: FIXED-PIVOT BLOCKS (50% = 40 rows)
    ┌─────────────────────────────────────────────────────────────────────┐
    │ Purpose: Demonstrate dimension INDEPENDENCE to LLM                  │
    │                                                                     │
    │ BLOCK A: VARY GEOGRAPHY (10 rows)                                   │
    │   Fix: Year=2020, Gender=Female, Sector=Rural                       │
    │   Vary: State = CA, TX, NY, FL, PA, OH, IL, GA, NC, MI              │
    │   → LLM sees: "Only State changes, confirms it's Place"             │
    │                                                                     │
    │ BLOCK B: VARY TIME (10 rows)                                        │
    │   Fix: State=CA, Gender=Female, Sector=Rural                        │
    │   Vary: Year = 2015, 2016, 2017, 2018, 2019, 2020...                │
    │   → LLM sees: "Only Year changes, confirms it's Time"               │
    │                                                                     │
    │ BLOCK C: VARY DIMENSIONS (20 rows)                                  │
    │   Fix: State=CA, Year=2020                                          │
    │   Vary: Full cartesian of Gender × Sector                           │
    │   → LLM sees: "Gender and Sector are INDEPENDENT dimensions"        │
    │   → LLM learns: StatVar = Wage_[Gender]_[Sector]                    │
    └─────────────────────────────────────────────────────────────────────┘

    STEP 4.3: EDGE CASES (25% = 20 rows)
    ┌─────────────────────────────────────────────────────────────────────┐
    │ Purpose: Cover special cases critical for correct PVMAP             │
    │                                                                     │
    │ TOTALS (5 rows):                                                    │
    │   State=Total, Gender=All, Sector=Combined                          │
    │   → Defines root StatVar (Count_Person)                             │
    │                                                                     │
    │ NULLS/ZEROS (5 rows):                                               │
    │   Rows with missing values or zero counts                           │
    │   → Tests null handling in PVMAP                                    │
    │                                                                     │
    │ FORMATTING EDGE CASES (10 rows):                                    │
    │   "Washington, D.C." (punctuation)                                  │
    │   "New York" vs "NY" (name variants)                                │
    │   → Tests DCID resolution                                           │
    └─────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
PHASE 5: COMBINATION TRACKING (During Advanced Sampling)
═══════════════════════════════════════════════════════════════════════════════

    For each selected row:
    ┌─────────────────────────────────────────────────────────────────────┐
    │ 1. Extract dimension tuple: (State, Gender, Sector)                 │
    │ 2. Check: Is this tuple in UNCOVERED set?                           │
    │ 3. If YES: Move to COVERED set, increment coverage                  │
    │ 4. Track coverage percentage                                        │
    └─────────────────────────────────────────────────────────────────────┘

    Coverage Stats:
    ┌─────────────────────────────────────────────────────────────────────┐
    │ Total combinations: 200                                             │
    │ Covered by sample: 80 (40%)                                         │
    │ Missing: 120 (60%)                                                  │
    └─────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
PHASE 6: GENERATE DATA CONTEXT PACKAGE
═══════════════════════════════════════════════════════════════════════════════

    OUTPUT: DataContext object containing:

    1. SAMPLED DATA (80 rows)
       - Diagonal scan rows (20)
       - Fixed-pivot block rows (40)
       - Edge case rows (20)

    2. SKELETON SUMMARY (Markdown for LLM prompts)
       ## DATA SKELETON SUMMARY

       ### Dataset Context
       - **Name:** Monthly_Wages_India
       - **Topology:** TIDY_LONG
       - **Population Type:** Person

       ### Anchors (Required)
       - **Geography:** Column `State` (Format: US State Name)
       - **Time:** Column `Quarter` (Format: YYYY-Q#)

       ### Skeleton Dimensions (Define StatVar)
       - `Gender` → maps to DC property `gender`
       - `Sector` → maps to DC property `placeOfResidenceClassification`

       ### Measurement Logic
       - Value Column: `AvgWage` (Mean, INR)

       ### StatVar Pattern
       `Mean_WageOrSalary_Worker_{Gender}_{Sector}`

       ### Coverage
       - Total Combinations: 200
       - Sample Covers: 80 (40%)

       **IMPORTANT:** Generate PVMAP for ALL combinations.

    3. STRUCTURAL METADATA (Dict for programmatic use)
       {
         "column_roles": {
           "State": "place",
           "Quarter": "time",
           "Gender": "dimension",
           "Sector": "dimension",
           "AvgWage": "value"
         },
         "dimension_columns": ["Gender", "Sector"],
         "dimension_domains": {
           "Gender": ["Male", "Female"],
           "Sector": ["Rural", "Urban"]
         },
         "statvar_pattern": "Mean_Wage_{Gender}_{Sector}",
         "total_combinations": 200,
         "coverage_percent": 40.0
       }
```

### How Context Flows to Downstream Agents

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   HOW DOWNSTREAM AGENTS USE CONTEXT                          │
│                                                                              │
│   ╔═══════════════════════════════════════════════════════════════╗         │
│   ║ STATVAR DISCOVERY AGENT (MCP)                                 ║         │
│   ║ Uses: dimension_columns, statvar_pattern, column_roles        ║         │
│   ║ → Builds queries using P+M+C Formula:                         ║         │
│   ║   Query = Population + MeasuredProperty + Constraints         ║         │
│   ║ → Example: "Mean Wage Person Male Rural"                      ║         │
│   ║ → Outputs: discovered_statvars for PVMAP generation           ║         │
│   ╚═══════════════════════════════════════════════════════════════╝         │
│                                                                              │
│   ┌───────────────────────────────────────────────────────────────┐         │
│   │ SCHEMA SELECTION AGENT                                        │         │
│   │ Uses: column_roles, dimension_columns                         │         │
│   │ → Knows this is "Economy/Employment" domain                   │         │
│   │ → Selects appropriate schema examples                         │         │
│   └───────────────────────────────────────────────────────────────┘         │
│                                                                              │
│   ┌───────────────────────────────────────────────────────────────┐         │
│   │ PVMAP GENERATION AGENT                                        │         │
│   │ Uses: skeleton_summary (full markdown), dimension_domains,    │         │
│   │       discovered_statvars (from MCP if available)             │         │
│   │ → Understands what columns define StatVar uniqueness          │         │
│   │ → Generates PVMAP that handles ALL combinations               │         │
│   │ → Uses discovered StatVars as templates                       │         │
│   └───────────────────────────────────────────────────────────────┘         │
│                                                                              │
│   ┌───────────────────────────────────────────────────────────────┐         │
│   │ DC QUERY AGENT (MCP Tools)                                    │         │
│   │ Uses: dimension_columns to build targeted queries             │         │
│   │ → With context: search "Mean Wage Male Rural India"           │         │
│   │ → Without context: search "wage" (too broad, poor results)    │         │
│   └───────────────────────────────────────────────────────────────┘         │
│                                                                              │
│   ┌───────────────────────────────────────────────────────────────┐         │
│   │ EVALUATION AGENT                                              │         │
│   │ Uses: statvar_pattern, coverage_percent                       │         │
│   │ → Compares generated StatVars against expected pattern        │         │
│   │ → Reports dimension coverage in metrics                       │         │
│   └───────────────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Before vs After Comparison

```
BEFORE (Current):                          AFTER (Improved):
────────────────────────────────────       ────────────────────────────────────

Track: Individual column values            Track: Dimension COMBINATIONS
  State: {CA, TX, NY...}                     {(CA, Male, Rural), (CA, Male, Urban),
  Gender: {Male, Female}                      (CA, Female, Rural), (TX, Male, Rural)...}
  Sector: {Rural, Urban}

Coverage: 56 values covered                Coverage: 40%+ combinations covered
          (100% individual)                          (vs 12-14% before)

Strategy: Random after coverage            Strategy: Fixed-Pivot blocks
          (haphazard combinations)                   (structured variation)

Output: Just sampled CSV                   Output: Sampled CSV + DataContext

LLM sees: Scattered examples               LLM sees: Dimension independence
          No structure guidance                      Clear uniqueness pattern
```

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

# Part 6: Implementation Plan (Gemini-Validated)

## 6.1 New Module: DataContext

**File:** `src/pipeline/sampling/data_context.py` (NEW)

The core module that generates context for the pipeline using the **Universal Template**.

```python
from dataclasses import dataclass
from typing import Dict, List, Any
import pandas as pd

@dataclass
class DataContext:
    """
    Complete context about a dataset for PVMAP generation.
    Uses UNIVERSAL TEMPLATE that works across all domains:
    Demographics, Economy, Health, Energy, Environment, etc.
    """

    # === DATASET CONTEXT (Domain-Agnostic) ===
    name: str                             # Dataset name
    description: str                      # Brief description
    topology: str                         # TIDY_LONG | PIVOTED_WIDE | HYBRID
    population_type: str                  # DC entity: Person, Electricity, Atmosphere, etc.

    # === ANCHORS (Required for all StatVarObservations) ===
    geography: Dict[str, Any]             # {column, format, resolution}
    time: Dict[str, Any]                  # {column, format, notes}

    # === SKELETON DIMENSIONS (Define StatVar uniqueness) ===
    constraint_columns: List[Dict]        # [{name, represents, role}]
    hidden_constraints: List[Dict]        # [{property, value, reason}]

    # === MEASUREMENT LOGIC ===
    value_columns: List[Dict]             # [{name, stat_type, measurement_method, unit}]
    header_semantics: str                 # For PIVOTED_WIDE: what headers represent

    # === DERIVED FIELDS ===
    column_roles: Dict[str, str]          # {column_name: role}
    dimension_columns: List[str]          # Dimension column names
    dimension_domains: Dict[str, List]    # {dimension: [values]}
    statvar_pattern: str                  # {measurement}_{population}_{constraints...}
    total_combinations: int
    sample_combinations: int
    coverage_percent: float

    def to_skeleton_summary(self) -> str:
        """
        Generate UNIVERSAL markdown summary for LLM prompts.
        Works for ANY domain: demographics, economy, health, energy, etc.
        """
        return f'''## DATA SKELETON SUMMARY

### Dataset Context
- **Name:** {self.name}
- **Topology:** {self.topology}
- **Population Type:** {self.population_type}

### Anchors (Required)
- **Geography:** Column `{self.geography['column']}` (Format: {self.geography['format']})
- **Time:** Column `{self.time['column']}` (Format: {self.time['format']})

### Skeleton Dimensions (Define StatVar)
{self._format_constraints()}

### Measurement Logic
{self._format_measurements()}

### StatVar Pattern
`{self.statvar_pattern}`

### Coverage
- Total Combinations: {self.total_combinations}
- Sample Covers: {self.sample_combinations} ({self.coverage_percent:.1f}%)

**IMPORTANT:** Generate PVMAP for ALL dimension combinations, not just those in sample.
'''

    def to_mcp_query_context(self) -> dict:
        """
        Generate context for MCP StatVar discovery.
        Uses P+M+C formula (Population + MeasuredProperty + Constraints).
        """
        return {
            'population': self.population_type,
            'measurement': self.value_columns[0]['measurement_method'] if self.value_columns else 'Count',
            'constraints': {c['name']: c['represents'] for c in self.constraint_columns},
        }

    def to_metadata_dict(self) -> dict:
        """Return structural metadata for programmatic use."""
        return {
            "column_roles": self.column_roles,
            "dimension_columns": self.dimension_columns,
            "dimension_domains": self.dimension_domains,
            "statvar_pattern": self.statvar_pattern,
            "total_combinations": self.total_combinations,
            "coverage_percent": self.coverage_percent,
        }

    def _format_constraints(self) -> str:
        lines = []
        for c in self.constraint_columns:
            lines.append(f"- `{c['name']}` → maps to DC property `{c['represents']}`")
        return "\n".join(lines) if lines else "- (none detected)"

    def _format_measurements(self) -> str:
        lines = []
        for v in self.value_columns:
            lines.append(f"- Value Column: `{v['name']}` ({v['stat_type']}, {v.get('unit', 'unspecified')})")
        return "\n".join(lines) if lines else "- (none detected)"


class DataContextGenerator:
    """
    Generates DataContext using UNIVERSAL analysis that works across ALL domains.
    NOT overfitted to any specific domain like wages or population.
    """

    # Universal population type mapping (domain-agnostic)
    POPULATION_KEYWORDS = {
        # Demographics
        'person': 'Person', 'people': 'Person', 'population': 'Person',
        'household': 'Household', 'family': 'Household',
        # Economy
        'business': 'EconomicActivity', 'gdp': 'EconomicActivity',
        'worker': 'Worker', 'employee': 'Worker',
        # Energy
        'electricity': 'Electricity', 'power': 'Electricity', 'energy': 'Electricity',
        'plant': 'PowerPlant',
        # Environment
        'air': 'Atmosphere', 'pollutant': 'AirPollutant', 'emission': 'Emissions',
        'temperature': 'Atmosphere', 'weather': 'Atmosphere',
        # Health
        'patient': 'Person', 'case': 'MedicalCondition',
    }

    # Universal measurement type mapping
    MEASUREMENT_KEYWORDS = {
        'count': 'Count', 'number': 'Count', 'total': 'Count',
        'amount': 'Amount', 'value': 'Amount',
        'rate': 'Rate', 'percent': 'Percent', 'percentage': 'Percent',
        'mean': 'Mean', 'average': 'Mean', 'avg': 'Mean',
        'concentration': 'Concentration',
        'generation': 'Generation', 'production': 'Generation',
        'consumption': 'Consumption',
    }

    def generate(self, df: pd.DataFrame, metadata: dict = None) -> DataContext:
        """Analyze dataset and generate UNIVERSAL context."""
        # Implementation: Apply dimension detection heuristics
        pass

    def _detect_topology(self, df: pd.DataFrame) -> str:
        """Detect if data is TIDY_LONG, PIVOTED_WIDE, or HYBRID."""
        pass

    def _infer_population_type(self, df: pd.DataFrame, metadata: dict) -> str:
        """Infer population type using UNIVERSAL keyword mapping."""
        pass

    def _infer_measurement_type(self, column_name: str) -> str:
        """Infer measurement type using UNIVERSAL keyword mapping."""
        pass
```

## 6.2 New Module: DimensionDetector

**File:** `src/pipeline/sampling/dimension_detector.py` (NEW)

```python
class DimensionDetector:
    """Detects dimension columns using Gemini-validated heuristics."""

    # Configuration from Gemini consultation
    CONFIG = {
        'cardinality_dimension_threshold': 0.1,   # < 10% unique = likely dimension
        'cardinality_value_threshold': 0.5,       # > 50% unique = likely value
        'cardinality_metadata_threshold': 0.01,   # < 1% unique = likely metadata

        'dimension_keywords': ['gender', 'sex', 'age', 'race', 'industry',
                               'education', 'status', 'type', 'category', 'sector'],
        'value_keywords': ['count', 'total', 'amount', 'percent', 'rate',
                           'value', 'number', 'sum'],
        'metadata_keywords': ['source', 'unit', 'note', 'moe', 'annotation', 'method'],
        'place_keywords': ['state', 'county', 'city', 'fips', 'geo',
                           'region', 'country', 'place', 'district'],
        'time_keywords': ['year', 'date', 'month', 'quarter', 'period', 'time'],
    }

    def classify_columns(self, df: pd.DataFrame) -> dict:
        """
        Classify columns into roles: place, time, dimension, value, metadata.

        Returns:
            dict with keys: 'place', 'time', 'dimensions', 'values', 'metadata'
        """
        result = {'place': [], 'time': [], 'dimensions': [], 'values': [], 'metadata': []}

        for col in df.columns:
            role = self._classify_single_column(df, col)
            result[role].append(col)

        return result

    def _classify_single_column(self, df: pd.DataFrame, col: str) -> str:
        """Apply all 3 tests to classify a single column."""
        # 1. Semantic test (highest priority for place/time)
        semantic_role = self.semantic_test(col)
        if semantic_role in ['place', 'time']:
            return semantic_role

        # 2. Cardinality test
        cardinality_role = self.cardinality_test(df[col])

        # 3. Combine results
        if semantic_role == 'dimension':
            return 'dimension'
        if semantic_role == 'value':
            return 'value'

        return cardinality_role

    def cardinality_test(self, series: pd.Series) -> str:
        """Apply cardinality ratio test."""
        ratio = series.nunique() / len(series)

        if ratio < self.CONFIG['cardinality_metadata_threshold']:
            return 'metadata'
        elif ratio < self.CONFIG['cardinality_dimension_threshold']:
            return 'dimension'
        elif ratio > self.CONFIG['cardinality_value_threshold']:
            return 'value'
        else:
            return 'dimension'  # Default for ambiguous cases

    def semantic_test(self, column_name: str) -> str:
        """Apply semantic keyword matching."""
        col_lower = column_name.lower()

        for keyword in self.CONFIG['place_keywords']:
            if keyword in col_lower:
                return 'place'

        for keyword in self.CONFIG['time_keywords']:
            if keyword in col_lower:
                return 'time'

        for keyword in self.CONFIG['dimension_keywords']:
            if keyword in col_lower:
                return 'dimension'

        for keyword in self.CONFIG['value_keywords']:
            if keyword in col_lower:
                return 'value'

        for keyword in self.CONFIG['metadata_keywords']:
            if keyword in col_lower:
                return 'metadata'

        return 'unknown'

    def summation_test(self, df: pd.DataFrame, candidate_col: str, value_col: str) -> bool:
        """Check if grouping by candidate and summing value is meaningful."""
        try:
            grouped = df.groupby(candidate_col)[value_col].sum()
            # If grouping produces reasonable aggregation, it's a dimension
            return len(grouped) > 1 and len(grouped) < len(df) * 0.5
        except:
            return False
```

## 6.3 New Module: CombinationTracker

**File:** `src/pipeline/sampling/combination_tracker.py` (NEW)

```python
from collections import Counter
from typing import Set, List, Dict

class CombinationTracker:
    """Tracks coverage of dimension combinations."""

    def __init__(self, dimension_columns: List[str]):
        self.dimension_columns = dimension_columns
        self.seen_combinations: Set[tuple] = set()
        self.combination_counts: Counter = Counter()

    def add_row(self, row: Dict[str, Any]) -> bool:
        """Add row and return True if it's a new combination."""
        combo = self._extract_combination(row)
        is_new = combo not in self.seen_combinations

        if is_new:
            self.seen_combinations.add(combo)
        self.combination_counts[combo] += 1

        return is_new

    def _extract_combination(self, row: Dict[str, Any]) -> tuple:
        """Extract dimension combination tuple from row."""
        return tuple(row.get(col, '') for col in self.dimension_columns)

    def get_coverage_stats(self) -> dict:
        """Return coverage statistics."""
        return {
            "total_seen": len(self.seen_combinations),
            "combinations": list(self.seen_combinations),
            "counts": dict(self.combination_counts),
        }

    def get_missing_combinations(self, full_cartesian: Set[tuple]) -> Set[tuple]:
        """Return combinations not yet seen."""
        return full_cartesian - self.seen_combinations
```

## 6.4 New Module: SkeletonSampler

**File:** `src/pipeline/sampling/skeleton_sampler.py` (NEW)

```python
class SkeletonSampler:
    """Implements Fixed-Pivot sampling strategy (Gemini-validated)."""

    def __init__(self, config: dict = None):
        self.config = config or {
            'target_rows': 80,
            'diagonal_scan_ratio': 0.25,    # 20 rows
            'fixed_pivot_ratio': 0.50,      # 40 rows
            'edge_cases_ratio': 0.25,       # 20 rows
            'total_keywords': ['total', 'all', 'overall', 'aggregate', 'combined'],
        }

    def sample(self, df: pd.DataFrame, column_roles: dict, target_rows: int = 80) -> pd.DataFrame:
        """
        Generate a skeleton sample that preserves dimension structure.

        Strategy:
        1. Diagonal Scan (25%): Cover all unique dimension values
        2. Fixed-Pivot Blocks (50%): Vary ONE dimension at a time
        3. Edge Cases (25%): Totals, nulls, formatting edge cases
        """
        n_diagonal = int(target_rows * self.config['diagonal_scan_ratio'])
        n_pivot = int(target_rows * self.config['fixed_pivot_ratio'])
        n_edge = target_rows - n_diagonal - n_pivot

        diagonal_rows = self._diagonal_scan(df, column_roles, n_diagonal)
        pivot_rows = self._fixed_pivot_blocks(df, column_roles, n_pivot)
        edge_rows = self._edge_cases(df, column_roles, n_edge)

        # Combine and deduplicate
        all_indices = set(diagonal_rows.index) | set(pivot_rows.index) | set(edge_rows.index)
        return df.loc[list(all_indices)[:target_rows]]

    def _diagonal_scan(self, df: pd.DataFrame, column_roles: dict, n_rows: int) -> pd.DataFrame:
        """Select rows to maximize dimension value coverage."""
        dimensions = column_roles.get('dimensions', [])
        if not dimensions:
            return df.head(n_rows)

        selected_indices = []
        covered_values = {dim: set() for dim in dimensions}

        for idx, row in df.iterrows():
            covers_new = False
            for dim in dimensions:
                val = row.get(dim)
                if val and val not in covered_values[dim]:
                    covered_values[dim].add(val)
                    covers_new = True

            if covers_new:
                selected_indices.append(idx)

            if len(selected_indices) >= n_rows:
                break

        return df.loc[selected_indices] if selected_indices else df.head(n_rows)

    def _fixed_pivot_blocks(self, df: pd.DataFrame, column_roles: dict, n_rows: int) -> pd.DataFrame:
        """Create pivot blocks varying one dimension at a time."""
        place_cols = column_roles.get('place', [])
        time_cols = column_roles.get('time', [])
        dim_cols = column_roles.get('dimensions', [])

        rows_per_block = n_rows // 3
        selected_indices = []

        # Block A: Vary Geography
        if place_cols:
            place_col = place_cols[0]
            # Fix other dimensions, vary place
            sample_a = df.drop_duplicates(subset=[place_col]).head(rows_per_block)
            selected_indices.extend(sample_a.index.tolist())

        # Block B: Vary Time
        if time_cols:
            time_col = time_cols[0]
            sample_b = df.drop_duplicates(subset=[time_col]).head(rows_per_block)
            selected_indices.extend(sample_b.index.tolist())

        # Block C: Vary Dimensions (cartesian product)
        if dim_cols:
            sample_c = df.drop_duplicates(subset=dim_cols).head(rows_per_block)
            selected_indices.extend(sample_c.index.tolist())

        return df.loc[list(set(selected_indices))[:n_rows]]

    def _edge_cases(self, df: pd.DataFrame, column_roles: dict, n_rows: int) -> pd.DataFrame:
        """Select total rows, nulls, and formatting edge cases."""
        selected_indices = []

        # Find "Total" rows
        for idx, row in df.iterrows():
            row_str = ' '.join(str(v).lower() for v in row.values[:5])
            if any(kw in row_str for kw in self.config['total_keywords']):
                selected_indices.append(idx)
                if len(selected_indices) >= n_rows // 2:
                    break

        # Find rows with nulls
        null_rows = df[df.isnull().any(axis=1)].head(n_rows // 4)
        selected_indices.extend(null_rows.index.tolist())

        # Find rows with zeros (edge case values)
        value_cols = column_roles.get('values', [])
        for col in value_cols:
            if col in df.columns:
                zero_rows = df[df[col] == 0].head(n_rows // 4)
                selected_indices.extend(zero_rows.index.tolist())
                break

        return df.loc[list(set(selected_indices))[:n_rows]]
```

## 6.5 Integration with Existing Code

### Modify: `src/pipeline/sampling/data_sampler.py`

Add DataContext generation after basic sampling:

```python
def sample_csv_file(input_path: str, output_path: str, config: dict = None) -> dict:
    """Sample CSV file and generate DataContext."""

    # ... existing sampling logic ...

    # NEW: Generate DataContext
    from .data_context import DataContextGenerator
    from .dimension_detector import DimensionDetector

    df = pd.read_csv(input_path)
    detector = DimensionDetector()
    column_roles = detector.classify_columns(df)

    context_gen = DataContextGenerator()
    data_context = context_gen.generate(df, metadata)

    return {
        "success": True,
        "output_file": str(output_path),
        "rows_sampled": rows_written,
        "data_context": data_context.to_metadata_dict(),
        "skeleton_summary": data_context.to_skeleton_summary(),
        "error": ""
    }
```

### Modify: `src/agents/sampling_agent.py`

Store DataContext in ADK state:

```python
async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
    # ... existing logic ...

    result = sample_data(input_file, output_file)

    # NEW: Store DataContext in state
    if result.get("data_context"):
        ctx.session.state["data_context"] = result["data_context"]
        ctx.session.state["skeleton_summary"] = result.get("skeleton_summary", "")

    # ... rest of logic ...
```

### Modify: `src/resources/prompts/improved_pvmap_prompt.txt`

Add DataContext placeholder:

```markdown
## DATA UNDERSTANDING

{{DATA_CONTEXT}}

## SAMPLED DATA

Below is a strategic sample of the data. It demonstrates the dimension
structure, but does NOT show all possible combinations.

{{SAMPLED_DATA}}

## IMPORTANT

Your PVMAP must handle ALL dimension combinations shown in the skeleton
summary above, not just the specific rows in the sample.
```

## 6.6 MCP Integration for StatVar Discovery

### Modify: `src/agents/statvar_discovery_agent.py`

Use DataContext for targeted MCP queries:

```python
def build_mcp_queries(data_context: dict) -> List[str]:
    """
    Build MCP queries using P+M+C Formula (Gemini-validated).

    P+M+C = Population + MeasuredProperty + Constraints
    """
    population = data_context.get('population_type', 'Person')
    measurement = data_context.get('measurement_type', 'Count')
    dimension_domains = data_context.get('dimension_domains', {})

    queries = []

    # Full query with all constraints
    for combo in itertools.product(*dimension_domains.values()):
        constraint_str = ' '.join(combo)
        queries.append(f"{measurement} {population} {constraint_str}")

    # Relaxed queries (fewer constraints)
    for dim_name, values in dimension_domains.items():
        for value in values[:3]:  # Top 3 values per dimension
            queries.append(f"{measurement} {population} {value}")

    # Broad query (just population + measurement)
    queries.append(f"{measurement} {population}")

    return queries
```

---

# Part 7: Implementation Considerations

## 7.1 Configuration Parameters

```python
SAMPLING_CONFIG = {
    # Target sample size
    'target_rows': 80,

    # Allocation ratios (Fixed-Pivot strategy)
    'diagonal_scan_ratio': 0.25,      # 20 rows
    'fixed_pivot_ratio': 0.50,        # 40 rows
    'edge_cases_ratio': 0.25,         # 20 rows

    # Dimension detection thresholds (Gemini-validated)
    'cardinality_dimension_threshold': 0.1,   # < 10% unique = likely dimension
    'cardinality_value_threshold': 0.5,       # > 50% unique = likely value
    'cardinality_metadata_threshold': 0.01,   # < 1% unique = likely metadata

    # Semantic keywords
    'dimension_keywords': ['gender', 'sex', 'age', 'race', 'industry',
                           'education', 'status', 'type', 'category', 'sector'],
    'value_keywords': ['count', 'total', 'amount', 'percent', 'rate',
                       'value', 'number', 'sum'],
    'metadata_keywords': ['source', 'unit', 'note', 'moe', 'annotation', 'method'],
    'place_keywords': ['state', 'county', 'city', 'fips', 'geo',
                       'region', 'country', 'place', 'district'],
    'time_keywords': ['year', 'date', 'month', 'quarter', 'period', 'time'],

    # Total/aggregate detection
    'total_keywords': ['total', 'all', 'overall', 'aggregate', 'combined'],

    # Combination tracking limits
    'max_dimension_columns': 5,           # Limit to prevent cartesian explosion
    'min_combination_coverage': 0.2,      # Target 20% of combinations
}
```

## 7.2 Files to Create/Modify

### New Modules (Core Data Understanding)

| File | Purpose |
|------|---------|
| `src/pipeline/sampling/data_context.py` | **DataContext dataclass + DataContextGenerator** |
| `src/pipeline/sampling/dimension_detector.py` | Column classification using Gemini-validated heuristics |
| `src/pipeline/sampling/combination_tracker.py` | Track dimension combination coverage |
| `src/pipeline/sampling/skeleton_sampler.py` | Fixed-Pivot sampling strategy |

### Modified Modules (Integration)

| File | Changes |
|------|---------|
| `src/pipeline/sampling/data_sampler.py` | Integrate DataContextGenerator, return DataContext |
| `src/tools/data_sampler_tool.py` | Return full data_context in result dict |
| `src/agents/sampling_agent.py` | Store data_context in ADK state |
| `src/resources/prompts/improved_pvmap_prompt.txt` | Add `{{DATA_CONTEXT}}` placeholder |

### Downstream Agent Updates (Context Consumers)

| File | Changes |
|------|---------|
| `src/agents/statvar_discovery_agent.py` | Use dimension_columns for targeted MCP queries |
| `src/agents/dc_query_agent.py` | Enhance search queries with dimension context |
| `src/agents/pvmap_generation_agent.py` | Read and use data_context from state |
| `src/agents/schema_selection_agent.py` | Use column_roles for schema selection |
| `src/agents/evaluation_agent.py` | Validate against expected StatVar pattern |

## 7.3 Complexity Considerations

**Cartesian Product Explosion:**
- If 5 dimension columns with 10 values each: 10^5 = 100,000 combinations
- Mitigation: Limit tracking to top 3-5 dimensions by importance

**Proposed Mitigation:**
```python
# Limit to top dimensions based on cardinality and semantics
if len(dimension_cols) > config['max_dimension_columns']:
    dimension_cols = rank_and_limit_dimensions(
        dimension_cols,
        limit=config['max_dimension_columns'],
        prioritize=['place', 'time']  # Anchors first
    )
```

## 7.4 Comprehensive Testing Checklist

### Unit Tests

#### Data Context Tests (`tests/pipeline/sampling/test_data_context.py`)
- [ ] `test_data_context_creation` - DataContext dataclass works correctly
- [ ] `test_to_skeleton_summary_format` - Generates valid markdown
- [ ] `test_to_metadata_dict` - Returns correct structure
- [ ] `test_context_generator_basic` - Generator produces valid context
- [ ] `test_infer_description_from_columns` - Infers meaningful description
- [ ] `test_infer_statvar_pattern` - Generates correct pattern
- [ ] `test_context_for_demographics_dataset` - Demographics domain
- [ ] `test_context_for_energy_dataset` - Energy domain
- [ ] `test_context_for_health_dataset` - Health domain

#### Dimension Detector Tests (`tests/pipeline/sampling/test_dimension_detector.py`)
- [ ] `test_classify_columns_basic` - Basic column classification
- [ ] `test_cardinality_test_low_ratio` - Correctly identifies dimensions
- [ ] `test_cardinality_test_high_ratio` - Correctly identifies values
- [ ] `test_semantic_test_dimension_keywords` - Recognizes "gender", "age", etc.
- [ ] `test_semantic_test_value_keywords` - Recognizes "count", "total", etc.
- [ ] `test_semantic_test_place_keywords` - Recognizes "state", "fips", etc.
- [ ] `test_summation_test_valid_dimension` - Grouping makes semantic sense
- [ ] `test_classify_columns_real_dataset` - Test on India NFHS columns

#### Combination Tracker Tests (`tests/pipeline/sampling/test_combination_tracker.py`)
- [ ] `test_add_row_new_combination` - Returns True for new combo
- [ ] `test_add_row_existing_combination` - Returns False for existing combo
- [ ] `test_get_coverage_stats_empty` - Empty tracker stats
- [ ] `test_get_coverage_stats_partial` - Partial coverage calculation
- [ ] `test_get_missing_combinations` - Correctly identifies missing combos

#### Skeleton Sampler Tests (`tests/pipeline/sampling/test_skeleton_sampler.py`)
- [ ] `test_diagonal_scan_covers_all_values` - All unique values appear
- [ ] `test_fixed_pivot_blocks_vary_one_dimension` - Each block varies one dim
- [ ] `test_edge_cases_includes_totals` - Total rows included
- [ ] `test_edge_cases_includes_nulls` - Null rows included if present
- [ ] `test_sample_respects_target_rows` - Output size matches target
- [ ] `test_sample_allocation_ratios` - 25/50/25 split maintained

### Integration Tests

#### Data Sampler Integration (`tests/pipeline/sampling/test_data_sampler_integration.py`)
- [ ] `test_sample_csv_with_dimension_tracking` - End-to-end dimension tracking
- [ ] `test_sample_csv_skeleton_summary_generated` - Summary in output
- [ ] `test_sample_csv_combination_coverage_improved` - Better than baseline
- [ ] `test_sample_csv_backward_compatible` - Existing configs still work

#### Agent Integration (`tests/agents/test_sampling_agent_context.py`)
- [ ] `test_sampling_agent_generates_context` - DataContext created
- [ ] `test_sampling_agent_stores_context_in_state` - Context in ADK state
- [ ] `test_context_flows_to_pvmap_agent` - PVMAP agent receives context
- [ ] `test_context_used_in_prompt` - Skeleton summary appears in PVMAP prompt

#### MCP Agent Integration (`tests/agents/test_statvar_discovery_with_context.py`)
- [ ] `test_discovery_uses_dimension_columns` - Builds queries from dimensions
- [ ] `test_discovery_query_uses_pmc_formula` - Uses P+M+C pattern
- [ ] `test_discovery_without_context_fallback` - Works without context

### Dataset-Specific Tests

#### India NFHS Dataset (`tests/pipeline/sampling/test_india_nfhs_sampling.py`)
- [ ] `test_india_nfhs_state_district_coverage` - > 50% combo coverage (was 14.2%)
- [ ] `test_india_nfhs_dimension_detection` - State, District detected as dims
- [ ] `test_india_nfhs_skeleton_summary` - Correct hierarchy shown

#### INPE Fire Dataset (`tests/pipeline/sampling/test_inpe_fire_sampling.py`)
- [ ] `test_inpe_fire_year_place_coverage` - > 50% combo coverage (was 12%)
- [ ] `test_inpe_fire_dimension_detection` - Year, Place detected as dims

### Full Pipeline Tests

#### End-to-End (`tests/integration/test_full_pipeline_with_skeleton.py`)
- [ ] `test_pipeline_discovery_to_evaluation` - Full run succeeds
- [ ] `test_pipeline_skeleton_flows_to_pvmap` - Skeleton reaches PVMAP prompt
- [ ] `test_pipeline_pvmap_accuracy_improved` - Better PVMAP quality

#### Regression Tests (`tests/integration/test_pipeline_regression.py`)
- [ ] `test_existing_datasets_still_pass` - All existing datasets still work
- [ ] `test_no_performance_regression` - Sampling time acceptable

## 7.5 Success Criteria

### Data Understanding Quality
| Metric | Current | Target |
|--------|---------|--------|
| Column classification accuracy | N/A | > 90% correct role assignment |
| Dimension detection accuracy | N/A | > 95% dimensions identified |
| StatVar pattern inference | N/A | Matches expected pattern |

### Sampling Quality
| Metric | Current | Target |
|--------|---------|--------|
| India NFHS combo coverage | 14.2% | > 50% |
| INPE Fire combo coverage | 12% | > 50% |
| Individual value coverage | 100% | 100% (maintain) |

### Pipeline Quality
| Metric | Current | Target |
|--------|---------|--------|
| PVMAP accuracy (PV match) | 26.8% | > 40% |
| Context flows to PVMAP agent | No | Yes |
| Skeleton summary in prompt | No | Yes |
| All existing tests pass | Yes | Yes |

## 7.6 Implementation Phases

**Phase 1: Analysis & Design** ✅ COMPLETE
- Document gap
- Gemini consultation
- Propose solution with universal templates

**Phase 2: Core Modules** (Week 1-2)
1. Create `data_context.py` - DataContext dataclass + DataContextGenerator
2. Create `dimension_detector.py` - Column classification heuristics
3. Create `combination_tracker.py` - Combination coverage tracking
4. Create `skeleton_sampler.py` - Fixed-Pivot sampling strategy

**Phase 3: Integration** (Week 3)
5. Integrate into `data_sampler.py` - Return DataContext
6. Update `data_sampler_tool.py` - Include data_context in result
7. Update `sampling_agent.py` - Store context in ADK state

**Phase 4: Pipeline Flow** (Week 4)
8. Update `improved_pvmap_prompt.txt` - Add `{{DATA_CONTEXT}}` placeholder
9. Update `pvmap_generation_agent.py` - Use context in prompt
10. Update `statvar_discovery_agent.py` - Use P+M+C queries

**Phase 5: Validation** (Week 5)
11. Run unit tests for all new modules
12. Run integration tests for context flow
13. Run dataset-specific tests (India NFHS, INPE Fire)
14. Manual validation on 3+ real datasets

## 7.7 Verification Commands

```bash
# Run unit tests for new modules
pytest tests/pipeline/sampling/test_dimension_detector.py -v
pytest tests/pipeline/sampling/test_combination_tracker.py -v
pytest tests/pipeline/sampling/test_skeleton_sampler.py -v
pytest tests/pipeline/sampling/test_data_context.py -v

# Run integration tests
pytest tests/pipeline/sampling/test_data_sampler_integration.py -v
pytest tests/agents/test_sampling_agent_context.py -v

# Run dataset-specific tests
pytest tests/pipeline/sampling/test_india_nfhs_sampling.py -v
pytest tests/pipeline/sampling/test_inpe_fire_sampling.py -v

# Run full pipeline tests
pytest tests/integration/test_full_pipeline_with_skeleton.py -v

# Manual validation: sample a specific dataset
PYTHONPATH="$(pwd):$(pwd)/src" python3 -c "
from src.pipeline.sampling.data_sampler import sample_csv_file
result = sample_csv_file('input/india_nfhs/test_data/india_nfhs_input.csv', 'test_output.csv')
print(f'Sampled: {result}')
"

# Manual validation: run full pipeline on single dataset
python3 run_pvmap_pipeline.py --dataset=india_nfhs --force-resample
```

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

# Data Sampling Improvement Plan - Refined After Gemini Consultation

## Executive Summary

Based on expert consultation with Gemini (Data Commons specialist), we've validated and refined our approach to improving the data sampling pipeline. The key insight is that **dimension combination coverage** (not just individual value coverage) is critical for correct PVMAP generation.

## Key Insights from Gemini Consultation

### 1. The Uniqueness Tuple (StatVar + Place + Time)

Every StatVarObservation in Data Commons is uniquely identified by:
- **observationAbout** (Place): The geographic entity
- **observationDate** (Time): The temporal dimension
- **variableMeasured** (StatVar): The statistical variable definition

The StatVar itself is defined by combining dimension columns (e.g., `Count_Person_Female_Age18To24`).

### 2. Column Classification Taxonomy

Gemini recommends classifying columns into 5 roles:
1. **Entity (Place)**: Geographic identifiers (State, FIPS, City)
2. **Temporal (Time)**: Time periods (Year, Date, Quarter)
3. **Dimension (StatVar Constraint)**: Properties that segment the population (Gender, Age, Industry)
4. **Measure (Value)**: The actual statistical count/amount
5. **Metadata/Attribute**: Context that doesn't define uniqueness (Source, Unit, Notes)

### 3. Dimension Detection Heuristics

**A. Cardinality Ratio Test**
- `Ratio = Unique_Values / Total_Rows`
- Dimension Pattern: Low ratio (values repeat frequently)
- Value Pattern: High ratio (continuous numeric data rarely repeats)
- Metadata Pattern: Very low (often constant across dataset)

**B. The "Pivot" Test**
- Can you pivot the column to become headers?
- If yes (and it's still readable) → **Dimension**
- If no (creates nonsensical column names) → **Value**

**C. The "Summation" Test**
- If summing the Value column grouped by this column makes sense → **Dimension**
- Example: Summing Population by Gender yields Total Population (meaningful)

**D. Semantic Naming**
- Dimension keywords: Gender, Sex, Age, Race, Industry, Education, Status
- Value keywords: Count, Total, Amount, Percent, Rate, Value
- Metadata keywords: Source, Unit, Note, MOE

### 4. Sampling Strategy: "Skeleton Sampling"

Gemini emphasizes **Skeleton Sampling** over random sampling:

> "When sampling data for PVMAP generation, you must prioritize **Dimension Combinations (Tuples)** over simple individual column value coverage."

#### The "Fixed-Pivot" Sampling Strategy

For a dataset with 50 states × 20 years × 2 genders × 5 age groups (~80 rows target):

1. **All-Dimensions Scan (20 rows)**: Ensure every unique value appears at least once
   - Diagonal selection through dimension values

2. **Fixed-Pivot Blocks (40 rows)**:
   - **Block A - Vary Geography**: 10 different states, fix time/demographics
   - **Block B - Vary Time**: 10 different years, fix geography/demographics
   - **Block C - Vary Demographics**: Full cartesian of Gender × Age for one place/time

3. **Edge Cases (20 rows)**:
   - Include "Total" or "All" aggregation rows
   - Include nulls/zeros if they exist
   - Include formatting edge cases

### 5. Data Skeleton Summary

The "Data Skeleton" is a structural digest that should include:

1. **Dataset Shape**: Wide (metrics in headers) vs Long (metrics in column values)
2. **Column Role Classification**: Place, Time, Dimension, Measure, Metadata
3. **Dimension Domain**: List unique values for each dimension column
4. **Primary Key Analysis**: The set of columns that uniquely identify each row

Example skeleton summary:
```
Dataset Structure: Long (Tidy)
Skeleton Columns (Primary Key): Year + State + Gender + Age_Group

Column Analysis:
1. Time: Year (Format: YYYY)
2. Place: State (Format: US State Abbreviation, maps to geoId/XX)
3. Dimension: Gender - Unique Values: [Male, Female, Total]
4. Dimension: Age_Group - Unique Values: [0-18, 19-35, 36-50, 51-65, 65+, Total]
5. Measure: Population (numeric count)
```

### 6. Failure Modes to Avoid

**A. Dimension Collapse**
- If a dimension column appears constant in the sample, LLM treats it as metadata
- Fix: Ensure every dimension shows at least 2 distinct values

**B. Spurious Correlation**
- If two dimensions always align in sample, LLM assumes dependency
- Fix: Include rows that "break" the pattern

**C. Missing Totals**
- "Total" rows define root StatVars and affect PVMAP logic
- Fix: Always include aggregate/total rows if they exist

---

## Implementation Plan

### Phase 1: Dimension Detection Module

**File**: `src/pipeline/sampling/dimension_detector.py`

```python
class DimensionDetector:
    """Detects dimension columns using Gemini-validated heuristics."""

    def classify_columns(self, df: pd.DataFrame) -> dict:
        """
        Classify columns into roles: place, time, dimension, value, metadata.

        Returns:
            dict with keys: 'place', 'time', 'dimensions', 'values', 'metadata'
        """
        pass

    def cardinality_test(self, series: pd.Series) -> str:
        """Apply cardinality ratio test."""
        pass

    def semantic_test(self, column_name: str) -> str:
        """Apply semantic keyword matching."""
        pass

    def summation_test(self, df: pd.DataFrame, candidate_col: str, value_col: str) -> bool:
        """Check if grouping by candidate and summing value is meaningful."""
        pass
```

### Phase 2: Combination Tracker

**File**: `src/pipeline/sampling/combination_tracker.py`

```python
class CombinationTracker:
    """Tracks coverage of dimension combinations."""

    def __init__(self, dimension_columns: list[str]):
        self.dimension_columns = dimension_columns
        self.seen_combinations = set()
        self.combination_counts = Counter()

    def add_row(self, row: dict) -> bool:
        """Add row and return True if it's a new combination."""
        pass

    def get_coverage_stats(self) -> dict:
        """Return coverage statistics."""
        pass

    def get_missing_combinations(self, full_cartesian: set) -> set:
        """Return combinations not yet seen."""
        pass
```

### Phase 3: Skeleton Sampler

**File**: `src/pipeline/sampling/skeleton_sampler.py`

```python
class SkeletonSampler:
    """Implements Fixed-Pivot sampling strategy."""

    def sample(self, df: pd.DataFrame, target_rows: int = 80) -> pd.DataFrame:
        """
        Generate a skeleton sample that preserves dimension structure.

        Strategy:
        1. All-Dimensions Scan (25% of rows)
        2. Fixed-Pivot Blocks (50% of rows)
        3. Edge Cases (25% of rows)
        """
        pass

    def _diagonal_scan(self, df: pd.DataFrame, n_rows: int) -> pd.DataFrame:
        """Select rows to maximize dimension value coverage."""
        pass

    def _fixed_pivot_blocks(self, df: pd.DataFrame, n_rows: int) -> pd.DataFrame:
        """Create pivot blocks varying one dimension at a time."""
        pass

    def _edge_cases(self, df: pd.DataFrame, n_rows: int) -> pd.DataFrame:
        """Select total rows, nulls, and formatting edge cases."""
        pass
```

### Phase 4: Skeleton Summary Generator

**File**: `src/pipeline/sampling/skeleton_summary.py`

```python
class SkeletonSummaryGenerator:
    """Generates structural digest for LLM consumption."""

    def generate(self, df: pd.DataFrame, column_roles: dict) -> str:
        """
        Generate a skeleton summary in markdown format.

        Includes:
        - Dataset shape (wide vs long)
        - Column classifications
        - Dimension domains (unique values)
        - Primary key analysis
        """
        pass
```

### Phase 5: Integration with Data Sampler

**Modify**: `src/pipeline/sampling/data_sampler.py`

Add dimension-aware sampling:
1. Detect dimension columns using `DimensionDetector`
2. Track combinations using `CombinationTracker`
3. Apply `SkeletonSampler` strategy
4. Generate `SkeletonSummary` for downstream use

### Phase 6: Prompt Enhancement

**Modify**: `src/resources/prompts/improved_pvmap_prompt.txt`

Add new placeholder `{{SKELETON_SUMMARY}}` that includes:
- Detected dimension structure
- Combination coverage statistics
- Explicit guidance on StatVar uniqueness

---

## Configuration Defaults

Based on Gemini consultation, recommended defaults:

```python
SAMPLING_CONFIG = {
    # Target sample size
    'target_rows': 80,

    # Allocation ratios
    'diagonal_scan_ratio': 0.25,      # 20 rows
    'fixed_pivot_ratio': 0.50,        # 40 rows
    'edge_cases_ratio': 0.25,         # 20 rows

    # Dimension detection thresholds
    'cardinality_dimension_threshold': 0.1,  # < 10% unique = likely dimension
    'cardinality_value_threshold': 0.5,      # > 50% unique = likely value
    'cardinality_metadata_threshold': 0.01,  # < 1% unique = likely metadata

    # Semantic keywords
    'dimension_keywords': ['gender', 'sex', 'age', 'race', 'industry', 'education', 'status', 'type', 'category'],
    'value_keywords': ['count', 'total', 'amount', 'percent', 'rate', 'value', 'number', 'sum'],
    'metadata_keywords': ['source', 'unit', 'note', 'moe', 'annotation', 'method'],
    'place_keywords': ['state', 'county', 'city', 'fips', 'geo', 'region', 'country', 'place'],
    'time_keywords': ['year', 'date', 'month', 'quarter', 'period', 'time'],

    # Total/aggregate detection
    'total_keywords': ['total', 'all', 'overall', 'aggregate', 'combined'],
}
```

---

## Next Steps

1. **Implement Phase 1**: Create `DimensionDetector` class with all heuristics
2. **Implement Phase 2**: Create `CombinationTracker` class
3. **Implement Phase 3**: Create `SkeletonSampler` class
4. **Implement Phase 4**: Create `SkeletonSummaryGenerator` class
5. **Integrate**: Modify `data_sampler.py` to use new components
6. **Test**: Create test cases with known dimension structures
7. **Validate**: Run on existing datasets and compare coverage metrics

---

## References

- Gemini consultation results: `output/gemini_consultation_results.json`
- Original analysis: (from conversation transcript)
- Data Commons StatVar documentation: https://datacommons.org/tools/statvar

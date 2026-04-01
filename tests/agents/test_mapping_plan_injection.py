"""Tests for _inject_schemaorg_into_plan with realistic pipeline data formats.

Covers:
- Backtick-wrapped column names in enrichment data
- Column name mismatches between enrichment and plan
- Colon-separated name prefix matching
- Case-insensitive matching
- Empty semantic type cells in table parsing
"""
import pytest
from src.agents.mapping_plan_agent import MappingPlanAgent
from src.agents.schemaorg_enrichment_agent import SchemaOrgEnrichmentAgent


# --- Realistic enrichment data (as produced by SchemaOrgEnrichmentAgent with backtick-wrapped column names) ---
REALISTIC_ENRICHMENT_BACKTICK = """\
### `STRUCTURE`
- No direct Schema.org match

### `STRUCTURE_ID`
- No direct Schema.org match

### `ACTION`
- No direct Schema.org match

### `FREQ:Frequency`
- DC property: variableMeasured (auto-built from dimension properties)
- Schema.org equivalent: variableMeasured (from Dataset, Observation)

### `REF_AREA:Reference area`
- DC property: observationAbout
- Schema.org equivalent: about (from Observation) — maps to Place entities
- Column-specific match: addressCountry (from Organization, PostalAddress)

### `TIME_PERIOD:Time period or range`
- DC property: observationDate
- Schema.org equivalent: dateCreated (from CreativeWork) — temporal observation axis

### `OBS_VALUE:Observation Value`
- DC property: value
- Schema.org equivalent: value (from PropertyValue, QuantitativeValue)

### `UNIT_MEASURE:Unit of measure`
- No direct Schema.org match

### `COMPILATION:Compilation`
- DC property: variableMeasured (auto-built from dimension properties)
- Schema.org equivalent: variableMeasured (from Dataset, Observation)

### `TITLE:Title`
- DC property: variableMeasured (auto-built from dimension properties)
- Schema.org equivalent: variableMeasured (from Dataset, Observation)
"""

# Same data without backticks (after enrichment agent fix)
REALISTIC_ENRICHMENT_CLEAN = REALISTIC_ENRICHMENT_BACKTICK.replace('### `', '### ').replace('`\n', '\n')

# --- Realistic plan text (as produced by LLM) ---
REALISTIC_PLAN = """\
# Mapping Plan: bis_bis_central_bank_policy_rate

## Dataset Understanding
- **Format:** Flat (TIDY_LONG)

## Column Mappings

### Column: `STRUCTURE`
- **Role:** ignored
- **Mapping:** `None -> None`
- **Reason:** Constant metadata.
- **Evidence:** Unique values: 1.
- **Alternatives rejected:** None.
- **Schema.org:** N/A
- **DC Match:** None

### Column: `FREQ:Frequency`
- **Role:** dimension
- **Mapping:** `freq:frequency -> [DATA]`
- **Reason:** Temporal frequency dimension.
- **Evidence:** Unique values: 2.
- **Alternatives rejected:** None.
- **Schema.org:** N/A
- **DC Match:** None

### Column: `REF_AREA:Reference area`
- **Role:** observationAbout
- **Mapping:** `observationAbout -> wikidataId/[DATA]`
- **Reason:** Geographic entity.
- **Evidence:** Unique values: 2.
- **Alternatives rejected:** None.
- **Schema.org:** N/A
- **DC Match:** None

### Column: `TIME_PERIOD:Time period or range`
- **Role:** observationDate
- **Mapping:** `observationDate -> [DATA]`
- **Reason:** Date column.
- **Evidence:** Unique values: 30.
- **Alternatives rejected:** None.
- **Schema.org:** N/A
- **DC Match:** None

### Column: `OBS_VALUE:Observation Value`
- **Role:** measure
- **Mapping:** `value -> [NUMBER]`
- **Reason:** Primary value.
- **Evidence:** Float type.
- **Alternatives rejected:** None.
- **Schema.org:** N/A
- **DC Match:** None

### Column: `COMPILATION:Compilation`
- **Role:** dimension
- **Mapping:** `compilation:compilation -> [DATA]`
- **Reason:** Methodological dimension.
- **Evidence:** Unique values: 2.
- **Alternatives rejected:** None.
- **Schema.org:** N/A
- **DC Match:** None

### Column: `TITLE:Title`
- **Role:** dimension
- **Mapping:** `title:title -> [DATA]`
- **Reason:** Title dimension.
- **Evidence:** Unique values: 2.
- **Alternatives rejected:** None.
- **Schema.org:** N/A
- **DC Match:** None

## Properties to Generate
- populationType,Thing
"""


def _count_na(plan_text: str) -> int:
    """Count Schema.org N/A lines in plan."""
    return sum(1 for l in plan_text.split('\n') if '**Schema.org:**' in l and 'N/A' in l)


def _count_injected(plan_text: str) -> int:
    """Count Schema.org lines with actual data (not N/A) in plan."""
    return sum(1 for l in plan_text.split('\n')
               if '**Schema.org:**' in l and 'N/A' not in l)


def assert_schemaorg_injected(plan_text: str, column_name: str, expected_content: str):
    """Assert that the Schema.org line for a given column contains expected content (not N/A)."""
    lines = plan_text.split('\n')
    found_col = False
    for line in lines:
        if f'### Column: `{column_name}`' in line:
            found_col = True
        if found_col and '**Schema.org:**' in line:
            assert 'N/A' not in line, (
                f"Column '{column_name}' still has N/A. Line: {line}"
            )
            assert expected_content in line, (
                f"Column '{column_name}' missing '{expected_content}'. Line: {line}"
            )
            return
    if not found_col:
        pytest.fail(f"Column '{column_name}' not found in plan")
    pytest.fail(f"No Schema.org line found after column '{column_name}'")


def assert_schemaorg_is_na(plan_text: str, column_name: str):
    """Assert that the Schema.org line for a given column is still N/A."""
    lines = plan_text.split('\n')
    found_col = False
    for line in lines:
        if f'### Column: `{column_name}`' in line:
            found_col = True
        if found_col and '**Schema.org:**' in line:
            assert 'N/A' in line, (
                f"Column '{column_name}' should be N/A but was: {line}"
            )
            return
    if not found_col:
        pytest.fail(f"Column '{column_name}' not found in plan")


class TestInjectSchemaorgIntoPlan:
    """Test _inject_schemaorg_into_plan with realistic data."""

    def setup_method(self):
        self.agent = MappingPlanAgent(name="TestPlan")

    def test_backtick_wrapped_enrichment_columns_are_matched(self):
        """Enrichment data with backtick-wrapped column names should match plan columns."""
        result = self.agent._inject_schemaorg_into_plan(REALISTIC_PLAN, REALISTIC_ENRICHMENT_BACKTICK)
        assert _count_injected(result) == 6
        assert_schemaorg_injected(result, "FREQ:Frequency", "variableMeasured")
        assert_schemaorg_injected(result, "REF_AREA:Reference area", "observationAbout")
        assert_schemaorg_injected(result, "TIME_PERIOD:Time period or range", "observationDate")
        assert_schemaorg_injected(result, "OBS_VALUE:Observation Value", "value")
        assert_schemaorg_injected(result, "COMPILATION:Compilation", "variableMeasured")
        assert_schemaorg_injected(result, "TITLE:Title", "variableMeasured")

    def test_clean_enrichment_columns_are_matched(self):
        """Enrichment data without backticks (after fix) should match plan columns."""
        result = self.agent._inject_schemaorg_into_plan(REALISTIC_PLAN, REALISTIC_ENRICHMENT_CLEAN)
        assert _count_injected(result) == 6

    def test_no_match_columns_remain_na(self):
        """Columns with 'No direct Schema.org match' should remain N/A."""
        result = self.agent._inject_schemaorg_into_plan(REALISTIC_PLAN, REALISTIC_ENRICHMENT_BACKTICK)
        assert_schemaorg_is_na(result, "STRUCTURE")

    def test_plan_with_short_column_names_matches_enrichment(self):
        """Plan may use short column names (e.g., REF_AREA) while enrichment uses full name."""
        short_plan = REALISTIC_PLAN.replace(
            '### Column: `REF_AREA:Reference area`',
            '### Column: `REF_AREA`'
        )
        result = self.agent._inject_schemaorg_into_plan(short_plan, REALISTIC_ENRICHMENT_BACKTICK)
        assert_schemaorg_injected(result, "REF_AREA", "observationAbout")

    def test_enrichment_with_short_names_matches_plan_long_names(self):
        """Enrichment may use short names while plan uses full colon-separated names."""
        short_enrichment = REALISTIC_ENRICHMENT_BACKTICK.replace(
            '### `REF_AREA:Reference area`',
            '### `REF_AREA`'
        )
        result = self.agent._inject_schemaorg_into_plan(REALISTIC_PLAN, short_enrichment)
        assert_schemaorg_injected(result, "REF_AREA:Reference area", "observationAbout")

    def test_plan_with_extended_column_names(self):
        """Plan may use extended names like 'REF_AREA:Reference area:AR: Argentina'."""
        extended_plan = REALISTIC_PLAN.replace(
            '### Column: `REF_AREA:Reference area`',
            '### Column: `REF_AREA:Reference area:AR: Argentina`'
        )
        result = self.agent._inject_schemaorg_into_plan(extended_plan, REALISTIC_ENRICHMENT_BACKTICK)
        assert_schemaorg_injected(result, "REF_AREA:Reference area:AR: Argentina", "observationAbout")

    def test_case_insensitive_matching(self):
        """Column names with different casing should still match."""
        # Enrichment has lowercase, plan has mixed case
        case_enrichment = REALISTIC_ENRICHMENT_CLEAN.replace(
            '### REF_AREA:Reference area',
            '### ref_area:reference area'
        )
        result = self.agent._inject_schemaorg_into_plan(REALISTIC_PLAN, case_enrichment)
        assert_schemaorg_injected(result, "REF_AREA:Reference area", "observationAbout")

    def test_empty_enrichment_returns_unchanged_plan(self):
        """Empty enrichment data should not modify the plan."""
        result = self.agent._inject_schemaorg_into_plan(REALISTIC_PLAN, "")
        assert result == REALISTIC_PLAN

    def test_enrichment_with_only_no_match_returns_unchanged(self):
        """Enrichment with only 'No direct Schema.org match' should not modify plan."""
        no_match = "### FREQ:Frequency\n- No direct Schema.org match\n"
        result = self.agent._inject_schemaorg_into_plan(REALISTIC_PLAN, no_match)
        assert _count_na(result) == _count_na(REALISTIC_PLAN)


class TestEnrichmentParseColumns:
    """Test SchemaOrgEnrichmentAgent._parse_columns with realistic skeleton data."""

    def setup_method(self):
        self.agent = SchemaOrgEnrichmentAgent(name="TestEnrich")

    def test_backtick_column_names_are_stripped(self):
        """Column names wrapped in backticks should have backticks stripped."""
        skeleton = """
## 1.5 COLUMN REFERENCE TABLE

| Column Header (EXACT) | Type | Unique Values | Semantic | Sample Values |
|------------------------|------|---------------|----------|---------------|
| `STRUCTURE` | object | 1 | | dataflow |
| `FREQ:Frequency` | object | 2 | dimension | M: Monthly, D: Daily |
| `REF_AREA:Reference area` | object | 2 | place | AR: Argentina |
"""
        cols = self.agent._parse_columns(skeleton)
        col_names = [c["name"] for c in cols]
        assert "STRUCTURE" in col_names
        assert "FREQ:Frequency" in col_names
        assert "REF_AREA:Reference area" in col_names
        # Verify NO backtick-wrapped names
        assert all('`' not in name for name in col_names)

    def test_empty_semantic_cell_preserved_as_empty(self):
        """Empty semantic type cells should not cause index shifting."""
        skeleton = """
| Column Header (EXACT) | Type | Unique Values | Semantic | Sample Values |
|------------------------|------|---------------|----------|---------------|
| `STRUCTURE` | object | 1 | | dataflow |
| `FREQ:Frequency` | object | 2 | dimension | M: Monthly |
| `OBS_VALUE` | float64 | 15 | measure | 0.26, 0.45 |
"""
        cols = self.agent._parse_columns(skeleton)

        # STRUCTURE has empty semantic type, should NOT pick up 'dataflow'
        structure = next(c for c in cols if c["name"] == "STRUCTURE")
        assert structure["semantic_type"] == "", (
            f"STRUCTURE semantic_type should be empty, got: {structure['semantic_type']!r}"
        )

        # FREQ has 'dimension' semantic type
        freq = next(c for c in cols if c["name"] == "FREQ:Frequency")
        assert freq["semantic_type"] == "dimension"

        # OBS_VALUE has 'measure' semantic type
        obs = next(c for c in cols if c["name"] == "OBS_VALUE")
        assert obs["semantic_type"] == "measure"

    def test_simple_table_format(self):
        """Simple test format without backticks should also work."""
        skeleton = """
| Column | Type | Unique | Semantic Type |
|--------|------|--------|---------------|
| Year | int | 10 | date |
| Value | float | 100 | measure |
"""
        cols = self.agent._parse_columns(skeleton)
        assert len(cols) == 2
        assert cols[0]["name"] == "Year"
        assert cols[0]["semantic_type"] == "date"


class TestSplitTableRow:
    """Test _split_table_row preserves empty cells."""

    def test_row_with_empty_cell(self):
        row = "| `STRUCTURE` | object | 1 | | dataflow |"
        parts = SchemaOrgEnrichmentAgent._split_table_row(row)
        assert len(parts) == 5
        assert parts[0] == "`STRUCTURE`"
        assert parts[3] == ""
        assert parts[4] == "dataflow"

    def test_row_with_all_cells_filled(self):
        row = "| `FREQ` | object | 2 | dimension | M: Monthly |"
        parts = SchemaOrgEnrichmentAgent._split_table_row(row)
        assert len(parts) == 5
        assert parts[3] == "dimension"

    def test_row_with_multiple_empty_cells(self):
        row = "| A | | | D |"
        parts = SchemaOrgEnrichmentAgent._split_table_row(row)
        assert parts == ["A", "", "", "D"]


class TestMatchEnrichmentCol:
    """Test _match_enrichment_col matching logic."""

    def setup_method(self):
        self.agent = MappingPlanAgent(name="TestPlan")

    def test_exact_match(self):
        col_values = {"FREQ:Frequency": "data"}
        assert self.agent._match_enrichment_col("FREQ:Frequency", col_values) == "data"

    def test_case_insensitive_exact(self):
        col_values = {"freq:frequency": "data"}
        assert self.agent._match_enrichment_col("FREQ:Frequency", col_values) == "data"

    def test_plan_shorter_prefix_match(self):
        col_values = {"REF_AREA:Reference area": "data"}
        assert self.agent._match_enrichment_col("REF_AREA", col_values) == "data"

    def test_enrichment_shorter_prefix_match(self):
        col_values = {"REF_AREA": "data"}
        assert self.agent._match_enrichment_col("REF_AREA:Reference area", col_values) == "data"

    def test_extended_plan_name(self):
        col_values = {"REF_AREA:Reference area": "data"}
        assert self.agent._match_enrichment_col("REF_AREA:Reference area:AR: Argentina", col_values) == "data"

    def test_colon_prefix_match(self):
        col_values = {"REF_AREA:Reference area": "data"}
        assert self.agent._match_enrichment_col("REF_AREA:Ref area", col_values) == "data"

    def test_no_match_returns_none(self):
        col_values = {"OTHER_COL": "data"}
        assert self.agent._match_enrichment_col("FREQ:Frequency", col_values) is None

    def test_backtick_in_enrichment_key(self):
        """Backticks in enrichment keys should be stripped during matching."""
        col_values = {"`FREQ:Frequency`": "data"}
        assert self.agent._match_enrichment_col("FREQ:Frequency", col_values) == "data"

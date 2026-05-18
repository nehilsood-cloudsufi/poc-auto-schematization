"""Tests for SchemaOrgEnrichmentAgent column parsing with realistic pipeline data formats.

Covers:
- Backtick-wrapped column names in skeleton data
- Empty semantic type cells in table parsing
- _split_table_row preserves empty cells
- _parse_columns extracts correct data

NOTE: The original _inject_schemaorg_into_plan and _match_enrichment_col tests were
removed when MappingPlanAgent v2 switched to structured output. Those methods no
longer exist. The SchemaOrgEnrichmentAgent tests remain because that agent is unchanged.
"""
import pytest
from src.agents.schemaorg_enrichment_agent import SchemaOrgEnrichmentAgent


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

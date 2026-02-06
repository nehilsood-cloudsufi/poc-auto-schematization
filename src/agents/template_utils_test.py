"""Tests for template_utils.py - ADK templating escape utilities."""

import pytest
from src.agents.template_utils import (
    escape_pvmap_placeholders,
    unescape_pvmap_placeholders,
)


class TestEscapePvmapPlaceholders:
    """Tests for escape_pvmap_placeholders function."""

    def test_escapes_data_placeholder(self):
        """Test escaping of {Data} placeholder."""
        text = "key,property,value\nYear,observationDate,{Data}"
        result = escape_pvmap_placeholders(text)
        assert "[DATA]" in result
        assert "{Data}" not in result

    def test_escapes_number_placeholder(self):
        """Test escaping of {Number} placeholder."""
        text = "Population,value,{Number}"
        result = escape_pvmap_placeholders(text)
        assert "[NUMBER]" in result
        assert "{Number}" not in result

    def test_escapes_multiple_placeholders(self):
        """Test escaping of multiple placeholders."""
        text = "Year,observationDate,{Data}\nPopulation,value,{Number}"
        result = escape_pvmap_placeholders(text)
        assert "[DATA]" in result
        assert "[NUMBER]" in result
        assert "{Data}" not in result
        assert "{Number}" not in result

    def test_preserves_format_specifiers(self):
        """Test that format specifiers are preserved."""
        text = "FIPS,observationAbout,geoId/{Data:02d}"
        result = escape_pvmap_placeholders(text)
        assert "[DATA:02d]" in result
        assert "{Data:02d}" not in result

    def test_preserves_complex_format_specifiers(self):
        """Test complex format specifiers like {Data:0>5}."""
        text = "FIPS,observationAbout,geoId/{Data:0>5}"
        result = escape_pvmap_placeholders(text)
        assert "[DATA:0>5]" in result
        assert "{Data:0>5}" not in result

    def test_handles_none_input(self):
        """Test handling of None input."""
        assert escape_pvmap_placeholders(None) == ""

    def test_handles_empty_string(self):
        """Test handling of empty string."""
        assert escape_pvmap_placeholders("") == ""

    def test_preserves_other_curly_braces(self):
        """Test that other curly brace content is preserved."""
        text = "some {other_var} text with {Data}"
        result = escape_pvmap_placeholders(text)
        assert "{other_var}" in result  # Should not be escaped
        assert "[DATA]" in result  # Should be escaped

    def test_real_pvmap_content(self):
        """Test with realistic PVMAP content."""
        pvmap = """key,property,value
Year,observationDate,{Data}
State FIPS,observationAbout,dcid:geoId/{Data:02d}
Population,value,{Number},populationType,dcid:Person,measuredProperty,dcid:count"""

        result = escape_pvmap_placeholders(pvmap)

        assert "observationDate,[DATA]" in result
        assert "geoId/[DATA:02d]" in result
        assert "value,[NUMBER]" in result
        # Verify DCIDs are NOT escaped
        assert "dcid:Person" in result
        assert "dcid:count" in result


class TestUnescapePvmapPlaceholders:
    """Tests for unescape_pvmap_placeholders function."""

    def test_unescapes_data_placeholder(self):
        """Test unescaping of [DATA] back to {Data}."""
        text = "Year,observationDate,[DATA]"
        result = unescape_pvmap_placeholders(text)
        assert "{Data}" in result
        assert "[DATA]" not in result

    def test_unescapes_number_placeholder(self):
        """Test unescaping of [NUMBER] back to {Number}."""
        text = "Population,value,[NUMBER]"
        result = unescape_pvmap_placeholders(text)
        assert "{Number}" in result
        assert "[NUMBER]" not in result

    def test_preserves_format_specifiers(self):
        """Test that format specifiers are preserved in unescape."""
        text = "FIPS,observationAbout,geoId/[DATA:02d]"
        result = unescape_pvmap_placeholders(text)
        assert "{Data:02d}" in result
        assert "[DATA:02d]" not in result

    def test_roundtrip(self):
        """Test that escape -> unescape returns original."""
        original = "Year,observationDate,{Data}\nFIPS,observationAbout,{Data:02d}\nPop,value,{Number}"
        escaped = escape_pvmap_placeholders(original)
        unescaped = unescape_pvmap_placeholders(escaped)
        assert unescaped == original

    def test_handles_none_input(self):
        """Test handling of None input."""
        assert unescape_pvmap_placeholders(None) == ""

    def test_handles_empty_string(self):
        """Test handling of empty string."""
        assert unescape_pvmap_placeholders("") == ""


class TestEdgeCases:
    """Tests for edge cases and potential issues."""

    def test_nested_braces_escaped(self):
        """Test that nested braces get partially escaped (edge case)."""
        # This shouldn't happen in practice - {{Data}} is not valid PVMAP syntax
        # The inner {Data} gets escaped to [DATA], leaving {[DATA]}
        # This is acceptable since {{Data}} isn't a real PVMAP pattern
        text = "text with {{Data}} double braces"
        result = escape_pvmap_placeholders(text)
        # The {Data} inside gets escaped, leaving the outer braces
        assert "[DATA]" in result

    def test_case_sensitivity(self):
        """Test that only exact case matches are escaped."""
        text = "{data} {DATA} {Data} {number} {NUMBER} {Number}"
        result = escape_pvmap_placeholders(text)
        # Only {Data} and {Number} (exact case) should be escaped
        assert "{data}" in result  # lowercase not escaped
        assert "{DATA}" in result  # uppercase not escaped
        assert "[DATA]" in result  # proper case escaped
        assert "{number}" in result  # lowercase not escaped
        assert "{NUMBER}" in result  # uppercase not escaped
        assert "[NUMBER]" in result  # proper case escaped

    def test_diff_output_with_pvmap_content(self):
        """Test realistic diff output that might contain PVMAP snippets."""
        diff_output = """
## Quality Diff

Expected: key,property,value
Got: key,property,value

Row 1:
- Expected: Year,observationDate,{Data}
- Got: Year,observationDate,{Data}

Row 2:
- Expected: Population,value,{Number}
- Got: Pop,value,{Number}
"""
        result = escape_pvmap_placeholders(diff_output)
        assert "{Data}" not in result
        assert "{Number}" not in result
        assert "[DATA]" in result
        assert "[NUMBER]" in result

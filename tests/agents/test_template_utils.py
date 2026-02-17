"""Tests for template_utils.py - ADK templating escape utilities."""

import pytest
from src.agents.template_utils import (
    escape_pvmap_placeholders,
    unescape_pvmap_placeholders,
    sanitize_for_adk,
    build_thinking_config,
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

    def test_escapes_arbitrary_word_patterns(self):
        """Test that arbitrary {word} patterns are escaped (catch-all)."""
        text = "some {other_var} text with {Data}"
        result = escape_pvmap_placeholders(text)
        assert "[other_var]" in result  # Catch-all escapes {word} patterns
        assert "[DATA]" in result  # Known placeholder escaped

    def test_escapes_llm_feedback_patterns(self):
        """Test that LLM-generated patterns like {year}, {measurement_type} are escaped."""
        text = "Map the {year} column to observationDate. Use {measurement_type} as property."
        result = escape_pvmap_placeholders(text)
        assert "[year]" in result
        assert "[measurement_type]" in result
        assert "{year}" not in result
        assert "{measurement_type}" not in result

    def test_preserves_json_curly_braces(self):
        """Test that JSON-like content with spaces/colons is not escaped."""
        text = '{"key": "value", "list": [1, 2]}'
        result = escape_pvmap_placeholders(text)
        # JSON-like patterns with spaces/colons should NOT match {word} regex
        assert '{"key": "value"' in result

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


class TestSanitizeForAdk:
    """Tests for sanitize_for_adk function."""

    def test_single_brace_identifier(self):
        """Single-brace identifiers are converted to brackets."""
        assert sanitize_for_adk("Search for {measurement} data") == "Search for [measurement] data"

    def test_double_brace_identifier(self):
        """Double-brace identifiers are also converted (ADK strips all braces)."""
        assert sanitize_for_adk("Search for {{measurement}} data") == "Search for [measurement] data"

    def test_triple_brace_identifier(self):
        """Triple braces are also caught."""
        assert sanitize_for_adk("{{{word}}}") == "[word]"

    def test_multiple_patterns(self):
        """Multiple patterns in one string."""
        text = "{{measurement}} {{population}} {{constraint}}"
        result = sanitize_for_adk(text)
        assert result == "[measurement] [population] [constraint]"

    def test_mixed_single_and_double(self):
        """Mix of single and double braces."""
        text = "{Data} and {{measurement}}"
        result = sanitize_for_adk(text)
        assert result == "[Data] and [measurement]"

    def test_preserves_json(self):
        """JSON-like content with spaces/colons is preserved."""
        text = '{"key": "value", "list": [1, 2]}'
        result = sanitize_for_adk(text)
        assert result == '{"key": "value", "list": [1, 2]}'

    def test_preserves_non_identifiers(self):
        """Non-identifier patterns are left alone."""
        text = "{key: value} {123abc} {}"
        result = sanitize_for_adk(text)
        assert result == "{key: value} {123abc} {}"

    def test_underscore_identifiers(self):
        """Identifiers with underscores are caught."""
        text = "{measurement_type} {_private}"
        result = sanitize_for_adk(text)
        assert result == "[measurement_type] [_private]"

    def test_none_input(self):
        assert sanitize_for_adk(None) == ""

    def test_empty_string(self):
        assert sanitize_for_adk("") == ""

    def test_no_braces(self):
        text = "Plain text with [brackets] and no braces"
        assert sanitize_for_adk(text) == text

    def test_real_enrichment_instruction(self):
        """Test with the actual problematic patterns from ENRICHMENT_BROAD_INSTRUCTION."""
        text = (
            '1. Start broad: Search for "{{measurement}} {{population}}"\n'
            '2. Narrow: "{{measurement}} {{population}} {{constraint}}"'
        )
        result = sanitize_for_adk(text)
        assert "{{" not in result
        assert "}}" not in result
        assert "[measurement]" in result
        assert "[population]" in result
        assert "[constraint]" in result

    def test_pvmap_content_in_error_resolver(self):
        """Test that PVMAP content with {Data}/{Number} in substituted values is sanitized."""
        text = (
            "Current PVMAP:\n"
            "Year,observationDate,{Data}\n"
            "Pop,value,{Number}"
        )
        result = sanitize_for_adk(text)
        assert "{Data}" not in result
        assert "{Number}" not in result
        assert "[Data]" in result
        assert "[Number]" in result


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
        """Test escape behavior across case variants."""
        text = "{data} {DATA} {Data} {number} {NUMBER} {Number}"
        result = escape_pvmap_placeholders(text)
        # {Data} and {Number} are escaped by specific rules to uppercase [DATA]/[NUMBER]
        assert "[DATA]" in result  # proper case escaped
        assert "[NUMBER]" in result  # proper case escaped
        # Other case variants are caught by the catch-all {word} -> [word]
        assert "[data]" in result  # catch-all
        assert "[DATA]" in result  # both specific + catch-all produce this
        assert "[number]" in result  # catch-all
        assert "[NUMBER]" in result  # both specific + catch-all produce this

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


class TestBuildThinkingConfig:
    """Tests for build_thinking_config function."""

    @pytest.mark.parametrize("level", [None, "", "none", "None", "NONE"])
    def test_returns_none_for_disabled(self, level):
        """Returns None when thinking is disabled."""
        assert build_thinking_config(level) is None

    @pytest.mark.parametrize("level", ["low", "medium", "high", "minimal"])
    def test_returns_config_for_valid_levels(self, level):
        """Returns a ThinkingConfig for each valid level."""
        config = build_thinking_config(level)
        assert config is not None
        # SDK normalizes string to ThinkingLevel enum (e.g. "low" -> ThinkingLevel.LOW)
        assert config.thinking_level.name == level.upper()
        assert config.include_thoughts is True

    def test_case_insensitive(self):
        """Levels are matched case-insensitively."""
        for level in ["HIGH", "High", "hIgH"]:
            config = build_thinking_config(level)
            assert config is not None
            assert config.include_thoughts is True

    def test_invalid_level_returns_none(self):
        """Invalid level strings return None."""
        assert build_thinking_config("ultra") is None
        assert build_thinking_config("off") is None
        assert build_thinking_config("turbo") is None

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace is stripped."""
        config = build_thinking_config("  high  ")
        assert config is not None
        assert config.include_thoughts is True

    def test_model_param_accepted(self):
        """model parameter is accepted (reserved for future use)."""
        config = build_thinking_config("high", model="gemini-3-pro-preview")
        assert config is not None

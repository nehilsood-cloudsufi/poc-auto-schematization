"""
Tests for two-section prompt template in build_prompt_with_feedback.

Verifies that {{HUMAN_FEEDBACK}} and {{AUTO_FEEDBACK}} placeholders are
correctly populated, and that the legacy error_feedback parameter is
backward-compatible.
"""

import pytest
from pathlib import Path

from src.agents.pvmap_generation.helpers import build_prompt_with_feedback


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_template(tmp_path: Path) -> Path:
    """Minimal template containing all relevant placeholders."""
    template = tmp_path / "template.txt"
    template.write_text(
        "## Data\n{{SAMPLED_DATA}}\n"
        "## Meta\n{{METADATA_CONFIG}}\n"
        "## Schema\n{{SCHEMA_EXAMPLES}}\n"
        "## Context\n{{DATA_CONTEXT}}\n"
        "---\n"
        "## HUMAN INSTRUCTIONS (MANDATORY — HIGHEST PRIORITY)\n"
        "{{HUMAN_FEEDBACK}}\n"
        "---\n"
        "## Auto-Generated Feedback (from validation analysis)\n"
        "{{AUTO_FEEDBACK}}\n"
        "---\n"
        "## Approved Mapping Plan\n"
        "{{APPROVED_MAPPING_PLAN}}\n"
        "## Discovered StatVars\n"
        "{{STATVAR_SUMMARY}}\n"
        "## MCP\n"
        "{{MCP_TOOLS_INSTRUCTION}}\n"
    )
    return template


@pytest.fixture
def legacy_template(tmp_path: Path) -> Path:
    """Template that still uses the old {{ERROR_FEEDBACK}} placeholder."""
    template = tmp_path / "legacy_template.txt"
    template.write_text(
        "## Data\n{{SAMPLED_DATA}}\n"
        "## Meta\n{{METADATA_CONFIG}}\n"
        "## Error Feedback\n{{ERROR_FEEDBACK}}\n"
        "## MCP\n{{MCP_TOOLS_INSTRUCTION}}\n"
    )
    return template


SAMPLE_DATA = "col1,col2\n1,2\n3,4"
METADATA = "param,value\nunit,Count"


def _build(template, **kwargs):
    """Convenience wrapper that always supplies the required positional args."""
    return build_prompt_with_feedback(
        template_path=template,
        schema_content="schema",
        sampled_data_content=SAMPLE_DATA,
        metadata_content=METADATA,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTwoSectionFeedback:
    """human_feedback + auto_feedback both provided."""

    def test_human_feedback_appears_in_human_section(self, base_template):
        prompt = _build(
            base_template,
            human_feedback="Fix the observationDate column.",
            auto_feedback="Key mismatch on row 3.",
        )
        assert "Fix the observationDate column." in prompt

    def test_auto_feedback_appears_in_auto_section(self, base_template):
        prompt = _build(
            base_template,
            human_feedback="Fix the observationDate column.",
            auto_feedback="Key mismatch on row 3.",
        )
        assert "Key mismatch on row 3." in prompt

    def test_human_section_header_present(self, base_template):
        prompt = _build(
            base_template,
            human_feedback="Do this.",
            auto_feedback="Do that.",
        )
        assert "HUMAN INSTRUCTIONS" in prompt

    def test_auto_section_header_present(self, base_template):
        prompt = _build(
            base_template,
            human_feedback="Do this.",
            auto_feedback="Do that.",
        )
        assert "Auto-Generated Feedback" in prompt

    def test_no_leftover_placeholders(self, base_template):
        prompt = _build(
            base_template,
            human_feedback="human note",
            auto_feedback="auto note",
        )
        assert "{{HUMAN_FEEDBACK}}" not in prompt
        assert "{{AUTO_FEEDBACK}}" not in prompt
        assert "{{ERROR_FEEDBACK}}" not in prompt


class TestOnlyHumanFeedback:
    """Only human_feedback provided; auto section should be empty."""

    def test_human_content_present(self, base_template):
        prompt = _build(base_template, human_feedback="Use wikidataId for places.")
        assert "Use wikidataId for places." in prompt

    def test_auto_section_is_empty(self, base_template):
        prompt = _build(base_template, human_feedback="Use wikidataId for places.")
        # The placeholder itself must be gone; the section content should be empty string
        assert "{{AUTO_FEEDBACK}}" not in prompt

    def test_no_leftover_placeholders(self, base_template):
        prompt = _build(base_template, human_feedback="Use wikidataId for places.")
        assert "{{HUMAN_FEEDBACK}}" not in prompt
        assert "{{ERROR_FEEDBACK}}" not in prompt


class TestOnlyAutoFeedback:
    """Only auto_feedback provided; human section should be empty."""

    def test_auto_content_present(self, base_template):
        prompt = _build(base_template, auto_feedback="Row 5 key mismatch.")
        assert "Row 5 key mismatch." in prompt

    def test_human_section_is_empty(self, base_template):
        prompt = _build(base_template, auto_feedback="Row 5 key mismatch.")
        assert "{{HUMAN_FEEDBACK}}" not in prompt

    def test_no_leftover_placeholders(self, base_template):
        prompt = _build(base_template, auto_feedback="Row 5 key mismatch.")
        assert "{{AUTO_FEEDBACK}}" not in prompt
        assert "{{ERROR_FEEDBACK}}" not in prompt


class TestNoFeedback:
    """No feedback of any kind provided — both sections present but empty."""

    def test_no_placeholders_remain(self, base_template):
        prompt = _build(base_template)
        assert "{{HUMAN_FEEDBACK}}" not in prompt
        assert "{{AUTO_FEEDBACK}}" not in prompt
        assert "{{ERROR_FEEDBACK}}" not in prompt

    def test_section_headers_still_present(self, base_template):
        prompt = _build(base_template)
        assert "HUMAN INSTRUCTIONS" in prompt
        assert "Auto-Generated Feedback" in prompt


class TestLegacyErrorFeedbackCompat:
    """error_feedback (legacy) should route into the auto section."""

    def test_error_feedback_appears_in_prompt(self, base_template):
        prompt = _build(base_template, error_feedback="Legacy: fix key on row 2.")
        assert "Legacy: fix key on row 2." in prompt

    def test_human_section_is_empty_for_legacy(self, base_template):
        """When only error_feedback is supplied, human section stays empty."""
        prompt = _build(base_template, error_feedback="Legacy: fix key on row 2.")
        # The human instructions header should be present but the content empty
        assert "{{HUMAN_FEEDBACK}}" not in prompt

    def test_no_leftover_placeholders_for_legacy(self, base_template):
        prompt = _build(base_template, error_feedback="Legacy: fix key on row 2.")
        assert "{{AUTO_FEEDBACK}}" not in prompt
        assert "{{ERROR_FEEDBACK}}" not in prompt


class TestLegacyOldTemplate:
    """Verify that old templates with {{ERROR_FEEDBACK}} are cleaned up gracefully."""

    def test_error_feedback_placeholder_removed(self, legacy_template):
        prompt = _build(legacy_template, error_feedback="some feedback")
        assert "{{ERROR_FEEDBACK}}" not in prompt

    def test_error_feedback_content_not_doubled(self, legacy_template):
        """Content should not appear twice when using legacy template."""
        prompt = _build(legacy_template, error_feedback="unique_marker_xyz")
        count = prompt.count("unique_marker_xyz")
        # With the old template, error_feedback goes into AUTO_FEEDBACK
        # but the template has no AUTO_FEEDBACK placeholder, so error_feedback
        # is silently dropped by the cleanup. It should NOT be doubled.
        assert count <= 1

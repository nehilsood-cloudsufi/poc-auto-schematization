import pytest


def test_approved_plan_placeholder_replacement():
    """{{APPROVED_MAPPING_PLAN}} in template gets replaced with plan content."""
    template = "Before\n{{APPROVED_MAPPING_PLAN}}\nAfter"
    plan_content = "# Mapping Plan: test\n## Column Mappings"
    populated = template.replace("{{APPROVED_MAPPING_PLAN}}", plan_content)
    assert "# Mapping Plan: test" in populated
    assert "{{APPROVED_MAPPING_PLAN}}" not in populated


def test_empty_plan_produces_empty_replacement():
    """When no approved plan exists, placeholder replaced with empty string."""
    template = "Before\n{{APPROVED_MAPPING_PLAN}}\nAfter"
    populated = template.replace("{{APPROVED_MAPPING_PLAN}}", "")
    assert "Before\n\nAfter" == populated

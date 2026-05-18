"""
Integration tests for the mapping plan workflow.

Verifies end-to-end plan workflow components without LLM calls:
- CLI flag parsing (Tasks 1)
- Plan file read/write (Tasks 3, 4)
- Approval gate (Task 4)
- Agent instantiation (Tasks 3, 9)
- Per-column DC queries (Task 8)
- Prompt template placeholders (Tasks 5, 6)
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_plan_only_flag_parsing():
    """--plan-only parses correctly."""
    from src.config.cli_parser import parse_args
    args = parse_args(["--dataset", "test_ds", "--plan-only"])
    assert args.plan_only is True
    assert args.from_plan is None


def test_from_plan_flag_parsing():
    """--from-plan parses correctly."""
    from src.config.cli_parser import parse_args
    args = parse_args(["--dataset", "test_ds", "--from-plan", "/tmp/plan.md"])
    assert args.from_plan == "/tmp/plan.md"
    assert args.plan_only is False


def test_auto_approve_flag_parsing():
    """--auto-approve parses correctly."""
    from src.config.cli_parser import parse_args
    args = parse_args(["--dataset", "test_ds", "--auto-approve"])
    assert args.auto_approve is True


def test_plan_only_and_from_plan_mutually_exclusive():
    """Cannot use --plan-only and --from-plan together."""
    from src.config.cli_parser import parse_args
    with pytest.raises(SystemExit):
        parse_args(["--dataset", "test_ds", "--plan-only", "--from-plan", "/tmp/plan.md"])


def test_from_plan_loads_file(tmp_path):
    """--from-plan loads plan content from disk."""
    from src.pipeline.approval_gate import read_plan_file

    plan_path = tmp_path / "mapping_plan.md"
    plan_path.write_text("# Mapping Plan: test\n## Column Mappings\n### Column: `Year`")

    content = read_plan_file(str(plan_path))
    assert "# Mapping Plan: test" in content
    assert "Column: `Year`" in content


def test_from_plan_file_not_found():
    """--from-plan with nonexistent file raises FileNotFoundError."""
    from src.pipeline.approval_gate import read_plan_file
    with pytest.raises(FileNotFoundError):
        read_plan_file("/nonexistent/path/plan.md")


def test_approval_gate_approve(tmp_path):
    """Approval gate returns APPROVED when user types 'a'."""
    from src.pipeline.approval_gate import request_approval, ApprovalResult

    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# Test Plan")

    with patch('builtins.input', return_value='a'):
        result = request_approval(str(plan_path))
    assert result == ApprovalResult.APPROVED


def test_approval_gate_reject(tmp_path):
    """Approval gate returns REJECTED when user types 'r'."""
    from src.pipeline.approval_gate import request_approval, ApprovalResult

    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# Test Plan")

    with patch('builtins.input', return_value='r'):
        result = request_approval(str(plan_path))
    assert result == ApprovalResult.REJECTED


def test_mapping_plan_agent_instantiation():
    """MappingPlanAgent can be instantiated with custom model."""
    from src.agents.mapping_plan_agent import MappingPlanAgent
    agent = MappingPlanAgent(name="TestPlan", model="gemini-3-flash-preview")
    assert agent.name == "TestPlan"
    assert agent._model_name == "gemini-3-flash-preview"


def test_plan_gate_agent_exists():
    """PlanGateAgent is importable from run_pipeline."""
    from src.run_pipeline import PlanGateAgent
    agent = PlanGateAgent(name="TestGate")
    assert agent.name == "TestGate"


def test_statvar_discovery_per_column_queries():
    """StatVarDiscoveryAgent builds per-column queries from skeleton."""
    from src.agents.statvar_discovery_agent import StatVarDiscoveryAgent
    agent = StatVarDiscoveryAgent(name="Test")

    skeleton = """## COLUMN REFERENCE TABLE
| Column | Type | Unique | Semantic Type |
|--------|------|--------|---------------|
| Country | str | 50 | place |
| GDP | float | 200 | measure |
| Year | int | 20 | date |"""

    queries = agent._build_per_column_queries(skeleton)
    columns = [q["column"] for q in queries]
    assert "Country" in columns
    assert "GDP" in columns
    assert "Year" not in columns  # date type excluded


def test_pvmap_prompt_has_approved_plan_placeholder():
    """PVMAP prompt template contains the APPROVED_MAPPING_PLAN placeholder."""
    prompt_path = Path("src/resources/prompts/improved_pvmap_prompt_v3.txt")
    content = prompt_path.read_text()
    assert "{{APPROVED_MAPPING_PLAN}}" in content


def test_feedback_prompt_has_approved_plan_placeholder():
    """Feedback prompt template contains the approved_mapping_plan placeholder."""
    prompt_path = Path("src/resources/prompts/feedback_agent_v2.txt")
    content = prompt_path.read_text()
    assert "{approved_mapping_plan}" in content

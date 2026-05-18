import pytest
from unittest.mock import patch
from pathlib import Path
from src.pipeline.approval_gate import request_approval, ApprovalResult, read_plan_file


def test_approve_returns_approved(tmp_path):
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# Mapping Plan")
    with patch('builtins.input', return_value='a'):
        result = request_approval(str(plan_path))
    assert result == ApprovalResult.APPROVED


def test_approve_case_insensitive(tmp_path):
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# Mapping Plan")
    with patch('builtins.input', return_value='A'):
        result = request_approval(str(plan_path))
    assert result == ApprovalResult.APPROVED


def test_reject_returns_rejected(tmp_path):
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# Mapping Plan")
    with patch('builtins.input', return_value='r'):
        result = request_approval(str(plan_path))
    assert result == ApprovalResult.REJECTED


def test_edit_returns_edited(tmp_path):
    plan_path = tmp_path / "mapping_plan.md"
    plan_path.write_text("# Original Plan")

    def fake_editor(cmd, **kwargs):
        plan_path.write_text("# Edited Plan")
        return type('Result', (), {'returncode': 0})()

    with patch('builtins.input', return_value='e'):
        with patch('subprocess.run', side_effect=fake_editor):
            result = request_approval(str(plan_path))

    assert result == ApprovalResult.EDITED


def test_invalid_input_reprompts(tmp_path):
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# Mapping Plan")
    with patch('builtins.input', side_effect=['x', 'z', 'a']):
        result = request_approval(str(plan_path))
    assert result == ApprovalResult.APPROVED


def test_read_plan_file(tmp_path):
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# My Plan\nContent here")
    content = read_plan_file(str(plan_path))
    assert content == "# My Plan\nContent here"


def test_read_plan_file_not_found():
    with pytest.raises(FileNotFoundError):
        read_plan_file("/nonexistent/path/plan.md")

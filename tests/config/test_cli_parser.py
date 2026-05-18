import pytest
from src.config.cli_parser import parse_args


def test_prompt_version_default():
    """Default prompt version is v3."""
    args = parse_args(["--dataset", "test"])
    assert args.prompt_version == "v3"


def test_prompt_version_v3():
    """Can select v3 prompt."""
    args = parse_args(["--dataset", "test", "--prompt-version", "v3"])
    assert args.prompt_version == "v3"


def test_prompt_version_invalid():
    """Invalid prompt version raises error."""
    with pytest.raises(SystemExit):
        parse_args(["--dataset", "test", "--prompt-version", "v99"])


def test_plan_only_flag():
    args = parse_args(["--dataset", "test_ds", "--plan-only"])
    assert args.plan_only is True


def test_from_plan_flag():
    args = parse_args(["--dataset", "test_ds", "--from-plan", "/tmp/plan.md"])
    assert args.from_plan == "/tmp/plan.md"


def test_auto_approve_flag():
    args = parse_args(["--dataset", "test_ds", "--auto-approve"])
    assert args.auto_approve is True


def test_default_flags_are_false():
    args = parse_args(["--dataset", "test_ds"])
    assert args.plan_only is False
    assert args.from_plan is None
    assert args.auto_approve is False


def test_plan_only_and_from_plan_mutually_exclusive():
    with pytest.raises(SystemExit):
        parse_args(["--dataset", "test_ds", "--plan-only", "--from-plan", "/tmp/plan.md"])

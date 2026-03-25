from src.config.cli_parser import parse_args


def test_prompt_version_default():
    """Default prompt version is v2."""
    args = parse_args(["--dataset", "test"])
    assert args.prompt_version == "v2"


def test_prompt_version_v3():
    """Can select v3 prompt."""
    args = parse_args(["--dataset", "test", "--prompt-version", "v3"])
    assert args.prompt_version == "v3"


def test_prompt_version_invalid():
    """Invalid prompt version raises error."""
    import pytest
    with pytest.raises(SystemExit):
        parse_args(["--dataset", "test", "--prompt-version", "v99"])

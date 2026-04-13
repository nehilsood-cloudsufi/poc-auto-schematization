"""
Comprehensive tests for CLI argument parser.

Tests cover: defaults, individual flags, invalid values, removed flags, combinations.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from src.config.cli_parser import parse_args, create_parser, args_to_dict, get_cli_config, BASE_DIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DEFAULT_SCHEMA_BASE_DIR = str(BASE_DIR / "src" / "resources" / "schema_examples")


# ===========================================================================
# 1. Default values for every argument
# ===========================================================================

class TestDefaults:
    """Verify every argument's default value when no flags are passed."""

    def test_dataset_default_none(self):
        args = parse_args([])
        assert args.dataset is None

    def test_resume_from_default_none(self):
        args = parse_args([])
        assert args.resume_from is None

    def test_dry_run_default_false(self):
        args = parse_args([])
        assert args.dry_run is False

    def test_skip_sampling_default_false(self):
        args = parse_args([])
        assert args.skip_sampling is False

    def test_force_resample_default_false(self):
        args = parse_args([])
        assert args.force_resample is False

    def test_skip_schema_selection_default_false(self):
        args = parse_args([])
        assert args.skip_schema_selection is False

    def test_force_schema_selection_default_false(self):
        args = parse_args([])
        assert args.force_schema_selection is False

    def test_schema_base_dir_default(self):
        args = parse_args([])
        assert args.schema_base_dir == DEFAULT_SCHEMA_BASE_DIR

    def test_skip_evaluation_default_false(self):
        args = parse_args([])
        assert args.skip_evaluation is False

    def test_ground_truth_repo_default(self):
        """Default comes from env var or falls back to ground_truth/."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove env var if set so we get the fallback
            env = os.environ.copy()
            env.pop("GROUND_TRUTH_REPO", None)
            with patch.dict(os.environ, env, clear=True):
                # Re-create parser to pick up env change
                from src.config.cli_parser import create_parser as _cp
                p = _cp()
                a = p.parse_args([])
                assert a.ground_truth_repo == str(BASE_DIR / "ground_truth")

    def test_ground_truth_pvmap_default_none(self):
        args = parse_args([])
        assert args.ground_truth_pvmap is None

    def test_ground_truth_dir_default_none(self):
        args = parse_args([])
        assert args.ground_truth_dir is None

    def test_input_dir_default(self):
        args = parse_args([])
        assert args.input_dir == "input"

    def test_output_dir_default(self):
        args = parse_args([])
        assert args.output_dir == "output"

    def test_model_default(self):
        args = parse_args([])
        assert args.model == "gemini-3.1-pro-preview"

    def test_thinking_level_default(self):
        args = parse_args([])
        assert args.thinking_level == "high"

    def test_enable_mcp_default_false(self):
        args = parse_args([])
        assert args.enable_mcp is False

    def test_enable_schemaorg_mcp_default_false(self):
        args = parse_args([])
        assert args.enable_schemaorg_mcp is False

    def test_no_schema_examples_default_false(self):
        args = parse_args([])
        assert args.no_schema_examples is False

    def test_input_file_default_none(self):
        args = parse_args([])
        assert args.input_file is None

    def test_use_metadata_default_false(self):
        args = parse_args([])
        assert args.use_metadata is False

    def test_metadata_file_path_default_none(self):
        args = parse_args([])
        assert args.metadata_file_path is None

    def test_schema_file_default_none(self):
        args = parse_args([])
        assert args.schema_file is None

    def test_structured_output_default_true(self):
        args = parse_args([])
        assert args.structured_output is True

    def test_no_structured_output_default_true(self):
        args = parse_args([])
        assert args.structured_output is True

    def test_verbose_default_false(self):
        args = parse_args([])
        assert args.verbose is False


# ===========================================================================
# 2. Individual flags
# ===========================================================================

class TestIndividualFlags:
    """Test each flag individually."""

    def test_dataset(self):
        args = parse_args(["--dataset", "bis_central_bank"])
        assert args.dataset == "bis_central_bank"

    def test_dataset_with_equals(self):
        args = parse_args(["--dataset=my_dataset"])
        assert args.dataset == "my_dataset"

    def test_resume_from(self):
        args = parse_args(["--resume-from", "some_dataset"])
        assert args.resume_from == "some_dataset"

    def test_dry_run(self):
        args = parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_skip_sampling(self):
        args = parse_args(["--skip-sampling"])
        assert args.skip_sampling is True

    def test_force_resample(self):
        args = parse_args(["--force-resample"])
        assert args.force_resample is True

    def test_skip_schema_selection(self):
        args = parse_args(["--skip-schema-selection"])
        assert args.skip_schema_selection is True

    def test_force_schema_selection(self):
        args = parse_args(["--force-schema-selection"])
        assert args.force_schema_selection is True

    def test_schema_base_dir(self):
        args = parse_args(["--schema-base-dir", "/tmp/schemas"])
        assert args.schema_base_dir == "/tmp/schemas"

    def test_skip_evaluation(self):
        args = parse_args(["--skip-evaluation"])
        assert args.skip_evaluation is True

    def test_ground_truth_repo(self):
        args = parse_args(["--ground-truth-repo", "/tmp/gt"])
        assert args.ground_truth_repo == "/tmp/gt"

    def test_ground_truth_pvmap(self):
        args = parse_args(["--ground-truth-pvmap", "/tmp/gt.csv"])
        assert args.ground_truth_pvmap == "/tmp/gt.csv"

    def test_ground_truth_dir(self):
        args = parse_args(["--ground-truth-dir", "/tmp/gt_dir"])
        assert args.ground_truth_dir == "/tmp/gt_dir"

    def test_input_dir(self):
        args = parse_args(["--input-dir", "/data/input"])
        assert args.input_dir == "/data/input"

    def test_output_dir(self):
        args = parse_args(["--output-dir", "/data/output"])
        assert args.output_dir == "/data/output"

    def test_model_long_flag(self):
        args = parse_args(["--model", "gemini-2.0-flash"])
        assert args.model == "gemini-2.0-flash"

    def test_model_short_flag(self):
        args = parse_args(["-m", "gemini-2.0-flash"])
        assert args.model == "gemini-2.0-flash"

    @pytest.mark.parametrize("level", ["low", "medium", "high", "minimal", "none"])
    def test_thinking_level_valid_choices(self, level):
        args = parse_args(["--thinking-level", level])
        assert args.thinking_level == level

    def test_enable_mcp(self):
        args = parse_args(["--enable-mcp"])
        assert args.enable_mcp is True

    def test_enable_schemaorg_mcp(self):
        args = parse_args(["--enable-schemaorg-mcp"])
        assert args.enable_schemaorg_mcp is True

    def test_no_schema_examples(self):
        args = parse_args(["--no-schema-examples"])
        assert args.no_schema_examples is True

    def test_input_file(self):
        args = parse_args(["--input-file", "/data/my_file.csv"])
        assert args.input_file == "/data/my_file.csv"

    def test_use_metadata(self):
        args = parse_args(["--use-metadata"])
        assert args.use_metadata is True

    def test_metadata_file_path(self):
        args = parse_args(["--metadata-file-path", "/data/meta.csv"])
        assert args.metadata_file_path == "/data/meta.csv"

    def test_schema_file(self):
        args = parse_args(["--schema-file", "/data/schema.json"])
        assert args.schema_file == "/data/schema.json"

    def test_structured_output(self):
        args = parse_args(["--structured-output"])
        assert args.structured_output is True

    def test_no_structured_output(self):
        args = parse_args(["--no-structured-output"])
        assert args.structured_output is False

    def test_verbose(self):
        args = parse_args(["--verbose"])
        assert args.verbose is True


# ===========================================================================
# 3. Invalid values raising SystemExit
# ===========================================================================

class TestInvalidValues:
    """Test that invalid inputs cause argparse to exit."""

    def test_invalid_thinking_level(self):
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--thinking-level", "ultra"])
        assert exc_info.value.code == 2

    def test_thinking_level_empty_string(self):
        with pytest.raises(SystemExit):
            parse_args(["--thinking-level", ""])

    def test_unknown_flag(self):
        with pytest.raises(SystemExit):
            parse_args(["--nonexistent-flag"])

    def test_dataset_missing_value(self):
        with pytest.raises(SystemExit):
            parse_args(["--dataset"])

    def test_model_missing_value(self):
        with pytest.raises(SystemExit):
            parse_args(["--model"])

    def test_input_dir_missing_value(self):
        with pytest.raises(SystemExit):
            parse_args(["--input-dir"])

    def test_output_dir_missing_value(self):
        with pytest.raises(SystemExit):
            parse_args(["--output-dir"])

    def test_schema_base_dir_missing_value(self):
        with pytest.raises(SystemExit):
            parse_args(["--schema-base-dir"])

    def test_ground_truth_repo_missing_value(self):
        with pytest.raises(SystemExit):
            parse_args(["--ground-truth-repo"])

    def test_resume_from_missing_value(self):
        with pytest.raises(SystemExit):
            parse_args(["--resume-from"])

    def test_input_file_missing_value(self):
        with pytest.raises(SystemExit):
            parse_args(["--input-file"])

    def test_metadata_file_path_missing_value(self):
        with pytest.raises(SystemExit):
            parse_args(["--metadata-file-path"])

    def test_schema_file_missing_value(self):
        with pytest.raises(SystemExit):
            parse_args(["--schema-file"])

    def test_ground_truth_pvmap_missing_value(self):
        with pytest.raises(SystemExit):
            parse_args(["--ground-truth-pvmap"])

    def test_ground_truth_dir_missing_value(self):
        with pytest.raises(SystemExit):
            parse_args(["--ground-truth-dir"])


# ===========================================================================
# 4. Removed flags are no longer accepted
# ===========================================================================

class TestRemovedFlags:
    """Flags that have been removed should cause SystemExit."""

    def test_sampling_mode_removed(self):
        with pytest.raises(SystemExit):
            parse_args(["--sampling-mode", "legacy"])

    def test_sampling_mode_programmatic_removed(self):
        with pytest.raises(SystemExit):
            parse_args(["--sampling-mode", "programmatic"])


# ===========================================================================
# 5. Flag combinations
# ===========================================================================

class TestFlagCombinations:
    """Test combinations of flags work correctly together."""

    def test_dataset_with_skip_sampling(self):
        args = parse_args(["--dataset", "bis", "--skip-sampling"])
        assert args.dataset == "bis"
        assert args.skip_sampling is True

    def test_all_skip_flags(self):
        args = parse_args([
            "--skip-sampling",
            "--skip-schema-selection",
            "--skip-evaluation",
        ])
        assert args.skip_sampling is True
        assert args.skip_schema_selection is True
        assert args.skip_evaluation is True

    def test_both_mcp_flags(self):
        args = parse_args(["--enable-mcp", "--enable-schemaorg-mcp"])
        assert args.enable_mcp is True
        assert args.enable_schemaorg_mcp is True

    def test_dry_run_with_dataset(self):
        args = parse_args(["--dry-run", "--dataset", "test_ds"])
        assert args.dry_run is True
        assert args.dataset == "test_ds"

    def test_input_file_with_metadata(self):
        args = parse_args([
            "--input-file", "/data/file.csv",
            "--use-metadata",
            "--metadata-file-path", "/data/meta.csv",
        ])
        assert args.input_file == "/data/file.csv"
        assert args.use_metadata is True
        assert args.metadata_file_path == "/data/meta.csv"

    def test_model_with_thinking_level(self):
        args = parse_args(["-m", "gemini-2.0-flash", "--thinking-level", "low"])
        assert args.model == "gemini-2.0-flash"
        assert args.thinking_level == "low"

    def test_force_resample_with_force_schema(self):
        args = parse_args(["--force-resample", "--force-schema-selection"])
        assert args.force_resample is True
        assert args.force_schema_selection is True

    def test_structured_output_and_no_structured_output(self):
        """Last flag wins with BooleanOptionalAction."""
        args = parse_args(["--structured-output", "--no-structured-output"])
        assert args.structured_output is False

    def test_all_ground_truth_options(self):
        args = parse_args([
            "--ground-truth-repo", "/gt/repo",
            "--ground-truth-pvmap", "/gt/file.csv",
            "--ground-truth-dir", "/gt/dir",
        ])
        assert args.ground_truth_repo == "/gt/repo"
        assert args.ground_truth_pvmap == "/gt/file.csv"
        assert args.ground_truth_dir == "/gt/dir"

    def test_full_pipeline_config(self):
        """Simulate a realistic full invocation."""
        args = parse_args([
            "--dataset", "bis_bis_central_bank_policy_rate",
            "-m", "gemini-3.1-pro-preview",
            "--thinking-level", "high",
            "--enable-mcp",
            "--verbose",
            "--input-dir", "input",
            "--output-dir", "output",
            "--schema-base-dir", "/schemas",
        ])
        assert args.dataset == "bis_bis_central_bank_policy_rate"
        assert args.model == "gemini-3.1-pro-preview"
        assert args.thinking_level == "high"
        assert args.enable_mcp is True
        assert args.verbose is True
        assert args.input_dir == "input"
        assert args.output_dir == "output"
        assert args.schema_base_dir == "/schemas"

    def test_no_schema_examples_with_skip_schema(self):
        args = parse_args(["--no-schema-examples", "--skip-schema-selection"])
        assert args.no_schema_examples is True
        assert args.skip_schema_selection is True

    def test_verbose_with_dry_run(self):
        args = parse_args(["--verbose", "--dry-run"])
        assert args.verbose is True
        assert args.dry_run is True

    def test_schema_file_with_input_file(self):
        args = parse_args([
            "--input-file", "/data/in.csv",
            "--schema-file", "/data/schema.json",
        ])
        assert args.input_file == "/data/in.csv"
        assert args.schema_file == "/data/schema.json"


# ===========================================================================
# 6. Helper functions
# ===========================================================================

class TestHelperFunctions:
    """Test args_to_dict and get_cli_config utilities."""

    def test_args_to_dict_returns_dict(self):
        args = parse_args([])
        result = args_to_dict(args)
        assert isinstance(result, dict)

    def test_args_to_dict_contains_all_keys(self):
        args = parse_args([])
        result = args_to_dict(args)
        expected_keys = {
            "dataset", "resume_from", "dry_run",
            "skip_sampling", "force_resample",
            "skip_schema_selection", "force_schema_selection", "schema_base_dir",
            "skip_evaluation", "use_llm_judge",
            "ground_truth_repo", "ground_truth_pvmap", "ground_truth_dir",
            "input_dir", "output_dir",
            "model", "thinking_level",
            "enable_mcp", "enable_schemaorg_mcp",
            "no_schema_examples",
            "input_file", "use_metadata", "metadata_file_path", "schema_file",
            "structured_output",
            "verbose",
            "skip_column_discovery",
            "prompt_version",
            "feedback_prompt_version",
            "plan_only", "from_plan", "auto_approve",
        }
        assert expected_keys == set(result.keys())

    def test_args_to_dict_preserves_values(self):
        args = parse_args(["--dataset", "test", "--verbose"])
        result = args_to_dict(args)
        assert result["dataset"] == "test"
        assert result["verbose"] is True

    def test_get_cli_config_returns_dict(self):
        result = get_cli_config([])
        assert isinstance(result, dict)

    def test_get_cli_config_with_args(self):
        result = get_cli_config(["--dataset", "abc", "--dry-run"])
        assert result["dataset"] == "abc"
        assert result["dry_run"] is True

    def test_create_parser_returns_parser(self):
        import argparse
        p = create_parser()
        assert isinstance(p, argparse.ArgumentParser)


# ===========================================================================
# 7. Environment variable interaction
# ===========================================================================

class TestEnvironmentVariables:
    """Test that environment variables affect defaults correctly."""

    def test_ground_truth_repo_from_env(self):
        """GROUND_TRUTH_REPO env var should be picked up as default."""
        with patch.dict(os.environ, {"GROUND_TRUTH_REPO": "/env/gt"}):
            parser = create_parser()
            args = parser.parse_args([])
            assert args.ground_truth_repo == "/env/gt"

    def test_ground_truth_repo_cli_overrides_env(self):
        with patch.dict(os.environ, {"GROUND_TRUTH_REPO": "/env/gt"}):
            parser = create_parser()
            args = parser.parse_args(["--ground-truth-repo", "/cli/gt"])
            assert args.ground_truth_repo == "/cli/gt"

    def test_base_dir_is_project_root(self):
        """BASE_DIR should point to the project root (two levels up from cli_parser.py)."""
        expected = Path(__file__).parent.parent.resolve()
        assert BASE_DIR == expected

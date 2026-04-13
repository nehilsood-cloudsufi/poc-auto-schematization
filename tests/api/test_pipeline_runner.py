"""Tests for framework-agnostic pipeline runner."""
import queue

import pytest

from src.api.services.pipeline_runner import PipelineConfig


class TestPipelineConfig:
    def test_defaults(self):
        config = PipelineConfig(
            run_id="test123",
            dataset_name="test_ds",
            input_dir="/tmp/input",
            output_dir="/tmp/output",
        )
        assert config.model == "gemini-3.1-pro-preview"
        assert config.enable_mcp is False
        assert config.skip_evaluation is True
        assert config.max_retries == 1

    def test_custom_values(self):
        config = PipelineConfig(
            run_id="r1",
            dataset_name="ds",
            input_dir="/tmp/in",
            output_dir="/tmp/out",
            model="gemini-2.0-flash",
            enable_mcp=False,
            max_retries=5,
        )
        assert config.model == "gemini-2.0-flash"
        assert config.enable_mcp is False
        assert config.max_retries == 5

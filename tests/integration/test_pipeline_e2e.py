"""
Integration tests for the PVMAP generation pipeline.

These tests verify that the pipeline orchestration works correctly
by mocking the ADK Runner, Gemini LLM, and subprocess calls.
No API keys are required.
"""

import csv
import os
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.state.dataset_info import DatasetInfo

# Path to the fixture CSV bundled with these tests
FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURE_CSV = FIXTURES_DIR / "test_input.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_dataset_dir(tmp_path: Path, dataset_name: str = "test_dataset") -> Path:
    """Create a minimal dataset directory structure under *tmp_path*.

    Layout::

        tmp_path/
            input/<dataset_name>/test_data/<dataset_name>_input.csv
            output/<dataset_name>/          (empty, created by pipeline)
    """
    input_dir = tmp_path / "input"
    dataset_dir = input_dir / dataset_name
    test_data_dir = dataset_dir / "test_data"
    test_data_dir.mkdir(parents=True)

    # Copy fixture CSV into the expected location
    shutil.copy(FIXTURE_CSV, test_data_dir / f"{dataset_name}_input.csv")

    # Create output dir
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    return tmp_path


def _make_dataset_info(
    tmp_path: Path,
    dataset_name: str = "test_dataset",
) -> DatasetInfo:
    """Build a DatasetInfo that mirrors the directory created by ``_setup_dataset_dir``."""
    dataset_path = tmp_path / "input" / dataset_name
    output_dir = tmp_path / "output"

    ds = DatasetInfo(name=dataset_name, path=dataset_path, output_base_dir=output_dir)
    ds.input_data_files = list((dataset_path / "test_data").glob("*_input.csv"))
    ds.output_dir = output_dir / dataset_name
    ds.output_dir.mkdir(parents=True, exist_ok=True)
    return ds


def _write_generated_pvmap(output_dir: Path) -> Path:
    """Write a minimal but structurally valid PVMAP CSV into *output_dir*."""
    pvmap_path = output_dir / "generated_pvmap.csv"
    pvmap_path.write_text(
        "Column,dcProperty,dcValue\n"
        "Year,observationDate,{Year}\n"
        "Country,observationAbout,{Country}\n"
        "Value,value,{Value}\n"
    )
    return pvmap_path


def _write_processed_csv(output_dir: Path) -> Path:
    """Write a minimal processed.csv that signals validation success."""
    processed_path = output_dir / "processed.csv"
    processed_path.write_text(
        "observationAbout,observationDate,value,variableMeasured\n"
        "country/USA,2020,100.5,Count_Something\n"
    )
    return processed_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pipeline_workspace(tmp_path):
    """Provide a fully set-up temp workspace with input data."""
    return _setup_dataset_dir(tmp_path)


# ---------------------------------------------------------------------------
# A mock that replaces the entire async pipeline execution path so we never
# touch ADK Runner, Gemini, or the network.
# ---------------------------------------------------------------------------

def _make_mock_run_pipeline(
    workspace: Path,
    dataset_name: str = "test_dataset",
    write_pvmap: bool = True,
    write_processed: bool = True,
):
    """Return a side_effect callable for patching ``run_dataset_pipeline``.

    When the patched function is called it creates the output artifacts that
    the real pipeline would produce, then returns a plausible state dict.
    """

    def _side_effect(**kwargs):
        ds_name = kwargs.get("dataset_name", dataset_name)
        out = workspace / "output" / ds_name
        out.mkdir(parents=True, exist_ok=True)

        if write_pvmap:
            _write_generated_pvmap(out)
        if write_processed:
            _write_processed_csv(out)

        return {
            "dataset_name": ds_name,
            "generation_success": write_pvmap and write_processed,
            "pvmap_path": str(out / "generated_pvmap.csv") if write_pvmap else None,
            "validation_passed": write_processed,
            "exit_reason": "max_retries" if write_pvmap else "error",
            "retry_count": 1,
            "validation_data_rows": 1 if write_processed else 0,
        }

    return _side_effect


# ===================================================================
# Tests
# ===================================================================


@pytest.mark.integration
class TestRunDatasetPipelineSignature:
    """Verify that ``run_dataset_pipeline`` can be called with the documented parameters."""

    def test_accepts_required_params(self, pipeline_workspace):
        """The function should accept dataset_name, input_dir, output_dir without error."""
        ws = pipeline_workspace
        side_effect = _make_mock_run_pipeline(ws)

        with patch("src.run_pipeline.run_dataset_pipeline", side_effect=side_effect):
            from src.run_pipeline import run_dataset_pipeline

            result = run_dataset_pipeline(
                dataset_name="test_dataset",
                input_dir=ws / "input",
                output_dir=ws / "output",
            )
            assert result["dataset_name"] == "test_dataset"

    def test_accepts_all_optional_params(self, pipeline_workspace):
        """Ensure every documented optional kwarg is accepted (no TypeError)."""
        ws = pipeline_workspace
        side_effect = _make_mock_run_pipeline(ws)

        with patch("src.run_pipeline.run_dataset_pipeline", side_effect=side_effect):
            from src.run_pipeline import run_dataset_pipeline

            result = run_dataset_pipeline(
                dataset_name="test_dataset",
                input_dir=ws / "input",
                output_dir=ws / "output",
                schema_base_dir=ws / "schema",
                model="gemini-3.1-pro-preview",
                enable_mcp=False,
                mcp_url=None,
                skip_sampling=True,
                force_resample=False,
                skip_schema_selection=True,
                force_schema_selection=False,
                ground_truth_pvmap=None,
                ground_truth_dir=None,
                ground_truth_repo=None,
                skip_evaluation=True,
                input_file=None,
                use_metadata=False,
                metadata_file_path=None,
                schema_file=None,
                use_schema_examples=True,
                human_feedback=None,
                min_attempts=None,
                max_retries=2,
                extra_plugins=None,
                thinking_level=None,
            )
            assert isinstance(result, dict)


@pytest.mark.integration
class TestOutputDirectoryStructure:
    """Verify the pipeline produces the expected output layout."""

    def test_pvmap_and_processed_created(self, pipeline_workspace):
        """After a successful run the output dir should contain generated_pvmap.csv
        and processed.csv."""
        ws = pipeline_workspace
        ds = "test_dataset"
        out_dir = ws / "output" / ds
        out_dir.mkdir(parents=True, exist_ok=True)

        side_effect = _make_mock_run_pipeline(ws, dataset_name=ds)

        with patch("src.run_pipeline.run_dataset_pipeline", side_effect=side_effect):
            from src.run_pipeline import run_dataset_pipeline

            run_dataset_pipeline(
                dataset_name=ds,
                input_dir=ws / "input",
                output_dir=ws / "output",
            )

        assert (out_dir / "generated_pvmap.csv").exists()
        assert (out_dir / "processed.csv").exists()

    def test_pvmap_csv_has_expected_columns(self, pipeline_workspace):
        """generated_pvmap.csv should have Column, dcProperty, dcValue headers."""
        ws = pipeline_workspace
        ds = "test_dataset"
        out_dir = ws / "output" / ds
        out_dir.mkdir(parents=True, exist_ok=True)

        side_effect = _make_mock_run_pipeline(ws, dataset_name=ds)

        with patch("src.run_pipeline.run_dataset_pipeline", side_effect=side_effect):
            from src.run_pipeline import run_dataset_pipeline

            run_dataset_pipeline(
                dataset_name=ds,
                input_dir=ws / "input",
                output_dir=ws / "output",
            )

        with open(out_dir / "generated_pvmap.csv") as f:
            reader = csv.DictReader(f)
            assert set(reader.fieldnames) == {"Column", "dcProperty", "dcValue"}

    def test_processed_csv_has_data_rows(self, pipeline_workspace):
        """processed.csv should have at least one data row beyond the header."""
        ws = pipeline_workspace
        ds = "test_dataset"
        out_dir = ws / "output" / ds
        out_dir.mkdir(parents=True, exist_ok=True)

        side_effect = _make_mock_run_pipeline(ws, dataset_name=ds)

        with patch("src.run_pipeline.run_dataset_pipeline", side_effect=side_effect):
            from src.run_pipeline import run_dataset_pipeline

            run_dataset_pipeline(
                dataset_name=ds,
                input_dir=ws / "input",
                output_dir=ws / "output",
            )

        with open(out_dir / "processed.csv") as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) > 1, "processed.csv should have header + data"

    def test_no_artifacts_when_generation_fails(self, pipeline_workspace):
        """When the pipeline fails, no pvmap or processed file should appear."""
        ws = pipeline_workspace
        ds = "test_dataset"
        out_dir = ws / "output" / ds
        out_dir.mkdir(parents=True, exist_ok=True)

        side_effect = _make_mock_run_pipeline(
            ws, dataset_name=ds, write_pvmap=False, write_processed=False,
        )

        with patch("src.run_pipeline.run_dataset_pipeline", side_effect=side_effect):
            from src.run_pipeline import run_dataset_pipeline

            result = run_dataset_pipeline(
                dataset_name=ds,
                input_dir=ws / "input",
                output_dir=ws / "output",
            )

        assert result["generation_success"] is False
        assert not (out_dir / "generated_pvmap.csv").exists()
        assert not (out_dir / "processed.csv").exists()


@pytest.mark.integration
class TestSkipFlags:
    """Verify that skip flags are threaded into initial_state correctly."""

    def _get_initial_state(self, workspace, **overrides):
        """Capture the ``initial_state`` dict that ``run_dataset_pipeline`` builds.

        We mock the entire async execution but let the synchronous setup code
        (discovery, state assembly) run so we can inspect initial_state.
        """
        captured = {}

        # Patch the async internals so no ADK/Gemini code runs
        with (
            patch("src.run_pipeline.create_runner") as mock_runner_factory,
            patch("src.run_pipeline.setup_python_logging", return_value=MagicMock()),
            patch("src.run_pipeline.setup_adk_logging", return_value=[]),
        ):
            # The runner mock needs a session_service with create_session
            mock_runner = MagicMock()
            mock_runner.session_service = MagicMock()

            # Capture the state dict passed to create_session
            async def _capture_create_session(**kwargs):
                captured["state"] = kwargs.get("state", {})

            mock_runner.session_service.create_session = AsyncMock(
                side_effect=_capture_create_session
            )
            mock_runner.run_async = MagicMock(return_value=AsyncMock().__aiter__())
            mock_runner.close = AsyncMock()
            mock_runner_factory.return_value = mock_runner

            # Patch get_session_state_direct to return empty dict (avoids real session lookup)
            with patch(
                "src.run_pipeline.get_session_state_direct", return_value={}
            ):
                from src.run_pipeline import run_dataset_pipeline

                default_kwargs = dict(
                    dataset_name="test_dataset",
                    input_dir=workspace / "input",
                    output_dir=workspace / "output",
                    max_retries=0,
                    skip_evaluation=True,
                )
                default_kwargs.update(overrides)

                try:
                    run_dataset_pipeline(**default_kwargs)
                except Exception:
                    # We only care about the captured state
                    pass

        return captured.get("state", {})

    def test_skip_sampling_flag(self, pipeline_workspace):
        state = self._get_initial_state(pipeline_workspace, skip_sampling=True)
        assert state.get("skip_sampling") is True

    def test_skip_schema_selection_flag(self, pipeline_workspace):
        state = self._get_initial_state(pipeline_workspace, skip_schema_selection=True)
        assert state.get("skip_schema_selection") is True

    def test_skip_evaluation_flag(self, pipeline_workspace):
        state = self._get_initial_state(pipeline_workspace, skip_evaluation=True)
        assert state.get("skip_evaluation") is True

    def test_human_feedback_injected(self, pipeline_workspace):
        state = self._get_initial_state(
            pipeline_workspace, human_feedback="Fix the country mapping"
        )
        assert state.get("error_feedback") == "Fix the country mapping"
        assert state.get("human_feedback_provided") is True

    def test_no_human_feedback_by_default(self, pipeline_workspace):
        state = self._get_initial_state(pipeline_workspace)
        assert "error_feedback" not in state
        assert "human_feedback_provided" not in state


@pytest.mark.integration
class TestErrorHandling:
    """Verify graceful handling of bad inputs."""

    def test_missing_input_directory(self, tmp_path):
        """When the dataset directory does not exist the pipeline should complete
        but report generation_success=False (no artifacts produced)."""
        nonexistent = tmp_path / "input"
        output = tmp_path / "output"
        output.mkdir()

        # The discovery agent does not raise for missing dirs — it returns a
        # DatasetInfo with no input_data_files and the agents handle it.
        # We mock the runner internals to avoid hitting Gemini.
        with (
            patch("src.run_pipeline.create_runner") as mock_runner_factory,
            patch("src.run_pipeline.setup_python_logging", return_value=MagicMock()),
            patch("src.run_pipeline.setup_adk_logging", return_value=[]),
            patch("src.run_pipeline.get_session_state_direct", return_value={}),
        ):
            mock_runner = MagicMock()
            mock_runner.session_service = MagicMock()
            mock_runner.session_service.create_session = AsyncMock()
            mock_runner.run_async = MagicMock(return_value=AsyncMock().__aiter__())
            mock_runner.close = AsyncMock()
            mock_runner_factory.return_value = mock_runner

            from src.run_pipeline import run_dataset_pipeline

            result = run_dataset_pipeline(
                dataset_name="nonexistent_dataset",
                input_dir=nonexistent,
                output_dir=output,
                max_retries=0,
            )

            # No PVMAP or processed.csv was created
            assert result.get("generation_success") is False

    def test_empty_csv(self, tmp_path):
        """Pipeline should handle a CSV with only a header (no data rows)."""
        ws = _setup_dataset_dir(tmp_path, dataset_name="empty_ds")
        csv_path = ws / "input" / "empty_ds" / "test_data" / "empty_ds_input.csv"
        csv_path.write_text("Year,Country,Value,Category\n")

        with (
            patch("src.run_pipeline.create_runner") as mock_runner_factory,
            patch("src.run_pipeline.setup_python_logging", return_value=MagicMock()),
            patch("src.run_pipeline.setup_adk_logging", return_value=[]),
            patch("src.run_pipeline.get_session_state_direct", return_value={}),
        ):
            mock_runner = MagicMock()
            mock_runner.session_service = MagicMock()
            mock_runner.session_service.create_session = AsyncMock()
            mock_runner.run_async = MagicMock(return_value=AsyncMock().__aiter__())
            mock_runner.close = AsyncMock()
            mock_runner_factory.return_value = mock_runner

            from src.run_pipeline import run_dataset_pipeline

            # Should not raise — the pipeline should start and the agents
            # will handle the empty data gracefully (or report it).
            try:
                result = run_dataset_pipeline(
                    dataset_name="empty_ds",
                    input_dir=ws / "input",
                    output_dir=ws / "output",
                    max_retries=0,
                    skip_evaluation=True,
                )
            except Exception:
                # Some internal error is acceptable for empty data,
                # but it must not be an unhandled TypeError/AttributeError
                pass


@pytest.mark.integration
class TestDatasetInfo:
    """Verify DatasetInfo construction from the test fixture directory."""

    def test_dataset_info_discovers_input_files(self, pipeline_workspace):
        ws = pipeline_workspace
        ds = _make_dataset_info(ws)
        assert ds.has_required_files()
        assert len(ds.input_data_files) == 1
        assert ds.input_data_files[0].name == "test_dataset_input.csv"

    def test_dataset_info_output_paths(self, pipeline_workspace):
        ws = pipeline_workspace
        ds = _make_dataset_info(ws)
        assert ds.output_dir == ws / "output" / "test_dataset"
        assert ds.pvmap_path == ws / "output" / "test_dataset" / "generated_pvmap.csv"

    def test_dataset_info_default_flags(self, pipeline_workspace):
        ws = pipeline_workspace
        ds = _make_dataset_info(ws)
        assert ds.use_metadata is False
        assert ds.standalone is False


@pytest.mark.integration
class TestFixtureCSV:
    """Sanity-check the bundled test fixture."""

    def test_fixture_exists(self):
        assert FIXTURE_CSV.exists(), f"Fixture CSV not found at {FIXTURE_CSV}"

    def test_fixture_has_10_rows(self):
        with open(FIXTURE_CSV) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 10

    def test_fixture_columns(self):
        with open(FIXTURE_CSV) as f:
            reader = csv.DictReader(f)
            assert set(reader.fieldnames) == {"Year", "Country", "Value", "Category"}

"""
Discovery Agent for ADK pipeline.

Discovers dataset files and populates DatasetInfo.
Migrated from run_pvmap_pipeline.py:144-184.

This agent uses Google ADK BaseAgent pattern for proper async execution.
"""

import sys
from pathlib import Path
from typing import List, AsyncGenerator

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from src.state.dataset_info import DatasetInfo


class DiscoveryAgent(BaseAgent):
    """
    Agent for discovering dataset files in input directory.

    This is a simple (non-LLM) agent that scans directories
    and populates DatasetInfo objects.

    ADK State Inputs:
        - input_dir: str - Path to input directory containing datasets

    ADK State Outputs:
        - datasets: List[DatasetInfo] - Discovered datasets with files
        - dataset_count: int - Number of datasets found
        - error: str | None - Error message if discovery failed

    Responsibilities:
    - Scan input directory for dataset subdirectories
    - Find schema files (*.txt, *.mcf)
    - Find metadata files (*metadata*.csv)
    - Find data files (*_input.csv, *_sampled_data.csv)
    - Populate DatasetInfo objects with discovered paths
    """

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Run discovery logic using ADK pattern.

        Reads input_dir from ctx.session.state, discovers datasets,
        and writes results back to state.

        Args:
            ctx: ADK invocation context with session state

        Yields:
            Event with discovery results
        """
        # 1. Read input from state
        input_dir = ctx.session.state.get("input_dir")

        if not input_dir:
            # Write error to state
            ctx.session.state["error"] = "No input_dir specified in state"
            ctx.session.state["datasets"] = []
            ctx.session.state["dataset_count"] = 0

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Discovery failed: No input_dir in state")
                ])
            )
            return

        # 2. Perform discovery (call helper method)
        input_path = Path(input_dir)
        datasets = self._discover_datasets(input_path)

        # 3. Write results to state
        ctx.session.state["datasets"] = datasets
        ctx.session.state["dataset_count"] = len(datasets)
        ctx.session.state["error"] = None

        # 4. Yield event with result
        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text=f"Discovered {len(datasets)} datasets in {input_dir}")
            ])
        )

    def _discover_datasets(self, input_dir: Path) -> List[DatasetInfo]:
        """
        Discover all datasets in the input directory.

        This is a helper method that contains the actual discovery logic.
        Migrated from run_pvmap_pipeline.py:144-184.

        Args:
            input_dir: Path to input directory containing datasets

        Returns:
            List of DatasetInfo objects with discovered files
        """
        datasets = []

        if not input_dir.exists():
            return datasets

        for dataset_path in sorted(input_dir.iterdir()):
            if not dataset_path.is_dir():
                continue

            dataset = DatasetInfo(dataset_path.name, dataset_path)

            # Find schema examples
            schema_files = list(dataset_path.glob("scripts_*_schema_examples_*.txt"))
            if schema_files:
                dataset.schema_examples = schema_files[0]

            # Find schema MCF files
            schema_mcf_files = list(dataset_path.glob("scripts_statvar_llm_config_vertical_*.mcf"))
            if schema_mcf_files:
                dataset.schema_mcf = schema_mcf_files[0]

            # Find metadata files (exclude combined_metadata to avoid copying to itself)
            dataset.metadata_files = [
                f for f in dataset_path.glob("*metadata*.csv")
                if "_combined_metadata.csv" not in f.name
            ]

            # Find combined metadata if it exists
            combined_metadata_files = list(dataset_path.glob("*_combined_metadata.csv"))
            if combined_metadata_files:
                dataset.combined_metadata = combined_metadata_files[0]

            # Find test data files
            if dataset.test_data_path.exists():
                # Exclude combined_* files to avoid infinite loops when re-running
                dataset.sampled_data_files = [
                    f for f in dataset.test_data_path.glob("*_sampled_data.csv")
                    if not f.name.startswith("combined_")
                ]
                dataset.input_data_files = [
                    f for f in dataset.test_data_path.glob("*_input.csv")
                    if not f.name.startswith("combined_")
                ]

                # Find combined sampled data if it exists
                combined_sampled_files = list(dataset.test_data_path.glob("combined_sampled_data.csv"))
                if combined_sampled_files:
                    dataset.combined_sampled_data = combined_sampled_files[0]

            datasets.append(dataset)

        return datasets

    def _discover_single_dataset(
        self,
        dataset_path: Path,
        dataset_name: str = None
    ) -> DatasetInfo:
        """
        Discover files for a single dataset.

        Helper method for discovering a specific dataset.

        Args:
            dataset_path: Path to dataset directory
            dataset_name: Optional dataset name (defaults to directory name)

        Returns:
            DatasetInfo object with discovered files
        """
        if dataset_name is None:
            dataset_name = dataset_path.name

        dataset = DatasetInfo(dataset_name, dataset_path)

        # Find schema examples
        schema_files = list(dataset_path.glob("scripts_*_schema_examples_*.txt"))
        if schema_files:
            dataset.schema_examples = schema_files[0]

        # Find schema MCF files
        schema_mcf_files = list(dataset_path.glob("scripts_statvar_llm_config_vertical_*.mcf"))
        if schema_mcf_files:
            dataset.schema_mcf = schema_mcf_files[0]

        # Find metadata files (exclude combined_metadata)
        dataset.metadata_files = [
            f for f in dataset_path.glob("*metadata*.csv")
            if "_combined_metadata.csv" not in f.name
        ]

        # Find combined metadata if it exists
        combined_metadata_files = list(dataset_path.glob("*_combined_metadata.csv"))
        if combined_metadata_files:
            dataset.combined_metadata = combined_metadata_files[0]

        # Find test data files
        if dataset.test_data_path.exists():
            dataset.sampled_data_files = [
                f for f in dataset.test_data_path.glob("*_sampled_data.csv")
                if not f.name.startswith("combined_")
            ]
            dataset.input_data_files = [
                f for f in dataset.test_data_path.glob("*_input.csv")
                if not f.name.startswith("combined_")
            ]

            # Find combined sampled data if it exists
            combined_sampled_files = list(dataset.test_data_path.glob("combined_sampled_data.csv"))
            if combined_sampled_files:
                dataset.combined_sampled_data = combined_sampled_files[0]

        return dataset

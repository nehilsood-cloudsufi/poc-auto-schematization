"""
Discovery Agent for ADK pipeline.

Discovers dataset files and populates DatasetInfo.
Migrated from run_pvmap_pipeline.py:144-184.

This agent uses Google ADK BaseAgent pattern for proper async execution.

Folder structure expected:
    input/{dataset_name}/
    ├── input_metadata/        (optional, for PVMAP generation prompts)
    │   └── *.csv
    ├── schema/                (auto-populated by SchemaSelectionAgent if empty)
    │   └── *.txt, *.mcf
    └── test_data/
        └── *_input.csv, *.csv, *.txt, *.xlsx, *.xls

    ground_truth/{dataset_name}/
    ├── metadata/              (used by validation)
    │   └── *.csv
    └── pvmap/
        └── *_pvmap.csv
"""

import sys
from pathlib import Path
from typing import List, Optional, AsyncGenerator

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from src.state.dataset_info import DatasetInfo
from src.pipeline.discovery.file_utils import derive_dataset_name, SUPPORTED_EXTENSIONS


class DiscoveryAgent(BaseAgent):
    """
    Agent for discovering dataset files in input directory.

    This is a simple (non-LLM) agent that scans directories
    and populates DatasetInfo objects.

    ADK State Inputs:
        - input_dir: str - Path to input directory containing datasets
        - use_metadata: bool - Whether to load metadata for prompts (default: False)
        - ground_truth_repo: str - Path to ground truth repository (optional)
        - input_file: str - Path to standalone input file (optional)
        - metadata_file_path: str - Path to explicit metadata file override (optional)
        - schema_file: str - Path to explicit schema file override (optional)

    ADK State Outputs:
        - datasets: List[DatasetInfo] - Discovered datasets with files
        - dataset_count: int - Number of datasets found
        - error: str | None - Error message if discovery failed
    """

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Run discovery logic using ADK pattern.

        Reads input_dir from ctx.session.state, discovers datasets,
        and writes results back to state.
        """
        # Check for standalone mode first
        input_file = ctx.session.state.get("input_file")
        if input_file:
            output_dir = ctx.session.state.get("output_dir", str(PROJECT_ROOT / "output"))
            use_metadata = ctx.session.state.get("use_metadata", False)
            metadata_file = ctx.session.state.get("metadata_file_path")
            schema_file = ctx.session.state.get("schema_file")

            dataset = self._discover_standalone(
                input_file=Path(input_file),
                output_base_dir=Path(output_dir),
                use_metadata=use_metadata,
                metadata_file=Path(metadata_file) if metadata_file else None,
                schema_file=Path(schema_file) if schema_file else None,
            )

            ctx.session.state["datasets"] = [dataset]
            ctx.session.state["dataset_count"] = 1
            ctx.session.state["error"] = None
            ctx.session.state["current_dataset"] = dataset

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Discovered standalone file: {input_file}")
                ])
            )
            return

        # Normal directory-based discovery
        input_dir = ctx.session.state.get("input_dir")

        if not input_dir:
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

        use_metadata = ctx.session.state.get("use_metadata", False)
        ground_truth_repo = ctx.session.state.get("ground_truth_repo")

        input_path = Path(input_dir)
        datasets = self._discover_datasets(
            input_dir=input_path,
            use_metadata=use_metadata,
            ground_truth_repo=Path(ground_truth_repo) if ground_truth_repo else None,
        )

        ctx.session.state["datasets"] = datasets
        ctx.session.state["dataset_count"] = len(datasets)
        ctx.session.state["error"] = None

        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text=f"Discovered {len(datasets)} datasets in {input_dir}")
            ])
        )

    def _discover_datasets(
        self,
        input_dir: Path,
        use_metadata: bool = False,
        ground_truth_repo: Optional[Path] = None,
    ) -> List[DatasetInfo]:
        """
        Discover all datasets in the input directory.

        Args:
            input_dir: Path to input directory containing datasets
            use_metadata: Whether to load metadata files
            ground_truth_repo: Path to ground truth repository

        Returns:
            List of DatasetInfo objects with discovered files
        """
        datasets = []

        if not input_dir.exists():
            return datasets

        for dataset_path in sorted(input_dir.iterdir()):
            if not dataset_path.is_dir():
                continue

            dataset = self._discover_single_dataset(
                dataset_path=dataset_path,
                use_metadata=use_metadata,
                ground_truth_repo=ground_truth_repo,
            )
            datasets.append(dataset)

        return datasets

    def _discover_single_dataset(
        self,
        dataset_path: Path,
        dataset_name: str = None,
        use_metadata: bool = False,
        metadata_file_override: Optional[Path] = None,
        schema_file_override: Optional[Path] = None,
        ground_truth_repo: Optional[Path] = None,
    ) -> DatasetInfo:
        """
        Discover files for a single dataset.

        Args:
            dataset_path: Path to dataset directory
            dataset_name: Optional dataset name (defaults to directory name)
            use_metadata: Whether to load metadata for prompts
            metadata_file_override: Explicit metadata file path
            schema_file_override: Explicit schema file path
            ground_truth_repo: Path to ground truth repository

        Returns:
            DatasetInfo object with discovered files
        """
        if dataset_name is None:
            dataset_name = dataset_path.name

        dataset = DatasetInfo(dataset_name, dataset_path)
        dataset.use_metadata = use_metadata

        # --- Schema discovery: scan schema/ subfolder ---
        if schema_file_override and schema_file_override.exists():
            dataset.schema_files = [schema_file_override]
            if schema_file_override.suffix == '.txt':
                dataset.schema_examples = schema_file_override
            elif schema_file_override.suffix == '.mcf':
                dataset.schema_mcf = schema_file_override
        elif dataset.schema_path.exists():
            for f in sorted(dataset.schema_path.iterdir()):
                if f.is_file() and f.suffix in ('.txt', '.mcf'):
                    dataset.schema_files.append(f)
                    if f.suffix == '.txt' and not dataset.schema_examples:
                        dataset.schema_examples = f
                    elif f.suffix == '.mcf' and not dataset.schema_mcf:
                        dataset.schema_mcf = f

        # --- Metadata discovery: scan input_metadata/ only if use_metadata ---
        if metadata_file_override and metadata_file_override.exists():
            dataset.metadata_files = [metadata_file_override]
            dataset.use_metadata = True
        elif use_metadata and dataset.input_metadata_path.exists():
            dataset.metadata_files = sorted([
                f for f in dataset.input_metadata_path.iterdir()
                if f.is_file() and f.suffix == '.csv'
            ])

        # --- Ground truth metadata discovery ---
        if ground_truth_repo:
            gt_metadata_dir = ground_truth_repo / dataset_name / "metadata"
            if gt_metadata_dir.exists() and any(gt_metadata_dir.iterdir()):
                dataset.ground_truth_metadata = gt_metadata_dir

        # --- Input data files: scan test_data/ ---
        if dataset.test_data_path.exists():
            dataset.input_data_files = sorted([
                f for f in dataset.test_data_path.iterdir()
                if f.is_file()
                and f.suffix.lower() in SUPPORTED_EXTENSIONS
                and not f.name.startswith("combined_")
                and not f.name.startswith("agentic_")
                and "_sampled_data" not in f.name
            ])

            # Sampled data files (still discovered for backward compat)
            dataset.sampled_data_files = sorted([
                f for f in dataset.test_data_path.iterdir()
                if f.is_file()
                and f.name.endswith("_sampled_data.csv")
                and not f.name.startswith("combined_")
            ])

        return dataset

    def _discover_standalone(
        self,
        input_file: Path,
        output_base_dir: Path,
        use_metadata: bool = False,
        metadata_file: Optional[Path] = None,
        schema_file: Optional[Path] = None,
    ) -> DatasetInfo:
        """
        Create a virtual DatasetInfo from a standalone input file.

        No dataset folder structure required. Creates a minimal DatasetInfo
        with the input file as the sole input data file.

        Args:
            input_file: Path to the input file
            output_base_dir: Base output directory
            use_metadata: Whether metadata is being used
            metadata_file: Optional explicit metadata file
            schema_file: Optional explicit schema file

        Returns:
            DatasetInfo object for standalone processing
        """
        dataset_name = derive_dataset_name(input_file)

        # Create a virtual dataset pointing to the file's parent
        dataset = DatasetInfo(
            name=dataset_name,
            path=input_file.parent,
            output_base_dir=output_base_dir,
        )
        dataset.standalone = True
        dataset.input_file_path = input_file
        dataset.input_data_files = [input_file]

        if metadata_file and metadata_file.exists():
            dataset.metadata_files = [metadata_file]
            dataset.use_metadata = True
        else:
            dataset.use_metadata = use_metadata

        if schema_file and schema_file.exists():
            dataset.schema_files = [schema_file]
            if schema_file.suffix == '.txt':
                dataset.schema_examples = schema_file
            elif schema_file.suffix == '.mcf':
                dataset.schema_mcf = schema_file

        return dataset

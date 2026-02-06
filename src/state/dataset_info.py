"""
DatasetInfo class for ADK migration.

Migrated from run_pvmap_pipeline.py (lines 68-92).
Stores information about a dataset and its files throughout the pipeline.
"""

from pathlib import Path
from typing import Optional, List


class DatasetInfo:
    """
    Information about a dataset and its files.

    Attributes:
        # Identity
        name: Dataset name (e.g., "bis_central_bank")
        path: Dataset directory path (e.g., "input/bis_central_bank/")
        test_data_path: Test data subdirectory path
        input_metadata_path: Path to input_metadata/ subfolder
        schema_path: Path to schema/ subfolder

        # Files to be discovered
        schema_examples: Path to schema examples .txt file (optional)
        schema_mcf: Path to schema MCF file (optional)
        schema_files: List of all schema files in schema/ dir
        metadata_files: List of metadata CSV files
        sampled_data_files: List of sampled data CSV files
        input_data_files: List of raw input CSV files

        # Combined/merged file paths (created during preparation)
        combined_metadata: Path to merged metadata CSV
        combined_sampled_data: Path to combined sampled data CSV
        combined_input_data: Path to combined input data CSV

        # Flags
        use_metadata: Whether to use metadata for prompt building
        standalone: Whether this is a standalone file (no dataset folder)

        # Standalone mode
        input_file_path: Explicit input file path (standalone mode)

        # Ground truth
        ground_truth_metadata: Path to ground_truth/{dataset}/metadata/ dir

        # Output paths
        output_dir: Dataset-specific output directory
        pvmap_path: Generated PVMAP CSV file path
        notes_path: Generation notes markdown file path
    """

    def __init__(self, name: str, path: Path, output_base_dir: Optional[Path] = None):
        """
        Initialize DatasetInfo.

        Args:
            name: Dataset name
            path: Dataset directory path
            output_base_dir: Base output directory (default: path.parent.parent / "output")
        """
        self.name = name
        self.path = Path(path)
        self.test_data_path = self.path / "test_data"
        self.input_metadata_path = self.path / "input_metadata"
        self.schema_path = self.path / "schema"

        # Files to be discovered
        self.schema_examples: Optional[Path] = None
        self.schema_mcf: Optional[Path] = None
        self.schema_files: List[Path] = []
        self.metadata_files: List[Path] = []
        self.sampled_data_files: List[Path] = []
        self.input_data_files: List[Path] = []

        # Combined/merged file paths (created during preparation)
        self.combined_metadata: Optional[Path] = None
        self.combined_sampled_data: Optional[Path] = None
        self.combined_input_data: Optional[Path] = None

        # Flags
        self.use_metadata: bool = False
        self.standalone: bool = False

        # Standalone mode
        self.input_file_path: Optional[Path] = None

        # Ground truth
        self.ground_truth_metadata: Optional[Path] = None

        # Output paths
        if output_base_dir is None:
            # Default: sibling directory "output" next to "input"
            output_base_dir = self.path.parent.parent / "output"

        self.output_dir = output_base_dir / name
        self.pvmap_path = self.output_dir / "generated_pvmap.csv"
        self.notes_path = self.output_dir / "generation_notes.md"

    def __repr__(self) -> str:
        """String representation of DatasetInfo."""
        parts = [
            f"DatasetInfo(name={self.name}",
            f"metadata_files={len(self.metadata_files)}",
            f"input_files={len(self.input_data_files)}",
            f"sampled_files={len(self.sampled_data_files)}",
            f"schema_files={len(self.schema_files)}",
        ]
        if self.standalone:
            parts.append("standalone=True")
        if self.use_metadata:
            parts.append("use_metadata=True")
        return ", ".join(parts) + ")"

    def has_required_files(self) -> bool:
        """
        Check if dataset has minimum required files.

        Returns:
            True if dataset has at least input data files
        """
        return len(self.input_data_files) > 0

    def get_file_summary(self) -> dict:
        """
        Get summary of discovered files.

        Returns:
            Dictionary with file counts and paths
        """
        return {
            "name": self.name,
            "schema_examples": str(self.schema_examples) if self.schema_examples else None,
            "schema_mcf": str(self.schema_mcf) if self.schema_mcf else None,
            "schema_files_count": len(self.schema_files),
            "metadata_count": len(self.metadata_files),
            "input_data_count": len(self.input_data_files),
            "sampled_data_count": len(self.sampled_data_files),
            "has_required_files": self.has_required_files(),
            "standalone": self.standalone,
            "use_metadata": self.use_metadata,
            "ground_truth_metadata": str(self.ground_truth_metadata) if self.ground_truth_metadata else None,
        }

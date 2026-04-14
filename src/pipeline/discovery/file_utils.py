"""
File utility functions for dataset discovery.

Handles dataset name derivation.
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Supported input file extensions
SUPPORTED_EXTENSIONS = {'.csv', '.txt', '.xlsx', '.xls'}


def derive_dataset_name(file_path: Path) -> str:
    """
    Derive a dataset name from a file path.

    Strips extension, converts to lowercase, replaces non-alphanumeric
    characters with underscores.

    Args:
        file_path: Path to the input file

    Returns:
        Derived dataset name string
    """
    stem = file_path.stem.lower()
    # Replace non-alphanumeric (except underscores) with underscores
    name = re.sub(r'[^a-z0-9_]', '_', stem)
    # Collapse multiple underscores
    name = re.sub(r'_+', '_', name)
    # Strip leading/trailing underscores
    return name.strip('_')

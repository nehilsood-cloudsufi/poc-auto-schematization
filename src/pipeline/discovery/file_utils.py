"""
File utility functions for dataset discovery.

Handles file normalization, combining, and dataset name derivation.
"""

import logging
import re
import shutil
from pathlib import Path
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Supported input file extensions
SUPPORTED_EXTENSIONS = {'.csv', '.txt', '.xlsx', '.xls'}


def normalize_file(file_path: Path, output_dir: Path) -> List[Path]:
    """
    Normalize a file to CSV format.

    Handles .csv (passthrough), .txt (treat as CSV), .xlsx/.xls (convert).

    Args:
        file_path: Path to the input file
        output_dir: Directory for converted outputs

    Returns:
        List of CSV paths (may be multiple sheets for Excel files)
    """
    suffix = file_path.suffix.lower()

    if suffix in ('.csv', '.txt'):
        return [file_path]

    if suffix in ('.xlsx', '.xls'):
        return _convert_excel_to_csv(file_path, output_dir)

    return []


def _convert_excel_to_csv(excel_path: Path, output_dir: Path) -> List[Path]:
    """Convert Excel file to CSV(s), one per sheet with data."""
    output_dir.mkdir(parents=True, exist_ok=True)
    result_paths = []

    try:
        xls = pd.ExcelFile(excel_path)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            if df.empty:
                continue

            safe_name = re.sub(r'[^\w]', '_', sheet_name).lower()
            stem = excel_path.stem
            csv_name = f"{stem}_{safe_name}.csv" if len(xls.sheet_names) > 1 else f"{stem}.csv"
            csv_path = output_dir / csv_name
            df.to_csv(csv_path, index=False)
            result_paths.append(csv_path)
            logger.debug(f"Converted sheet '{sheet_name}' to {csv_path}")

    except Exception as e:
        logger.warning(f"Failed to convert {excel_path}: {e}")

    return result_paths


def combine_csv_files(files: List[Path], output_path: Path) -> Optional[Path]:
    """
    Concatenate CSV files with the same header into one file.

    Args:
        files: List of CSV file paths
        output_path: Path for the combined output

    Returns:
        Path to combined file, or None if no files
    """
    if not files:
        return None

    if len(files) == 1:
        return files[0]

    try:
        dfs = []
        for f in files:
            try:
                df = pd.read_csv(f, nrows=0)  # read header only first
                dfs.append(pd.read_csv(f))
            except Exception as e:
                logger.warning(f"Skipping {f}: {e}")

        if not dfs:
            return None

        combined = pd.concat(dfs, ignore_index=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        combined.to_csv(output_path, index=False)
        logger.debug(f"Combined {len(dfs)} files into {output_path}")
        return output_path

    except Exception as e:
        logger.warning(f"Failed to combine CSV files: {e}")
        return files[0] if files else None


def combine_metadata_files(files: List[Path], output_path: Path) -> bool:
    """
    Merge multiple metadata config files into one.

    Metadata files are key-value CSVs (param,value format).
    Later files override earlier ones for duplicate keys.

    Args:
        files: List of metadata file paths to merge
        output_path: Path where merged metadata should be written

    Returns:
        True if merge successful, False otherwise
    """
    if not files:
        return False

    if len(files) == 1:
        shutil.copy(files[0], output_path)
        return True

    try:
        merged = {}
        for f in files:
            try:
                df = pd.read_csv(f, header=None, names=['param', 'value'])
                for _, row in df.iterrows():
                    key = str(row['param']).strip()
                    val = str(row['value']).strip() if pd.notna(row['value']) else ''
                    merged[key] = val
            except Exception as e:
                logger.warning(f"Skipping metadata file {f}: {e}")

        if not merged:
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        result_df = pd.DataFrame(
            list(merged.items()), columns=['param', 'value']
        )
        result_df.to_csv(output_path, index=False, header=False)
        logger.debug(f"Merged {len(files)} metadata files into {output_path}")
        return True

    except Exception as e:
        logger.warning(f"Failed to merge metadata: {e}")
        return False


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

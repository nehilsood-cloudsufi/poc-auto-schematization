"""
CLI argument parser for ADK PVMAP pipeline.

Migrated from run_pvmap_pipeline.py (lines 1420-1502).
Defines all command-line arguments for the pipeline.
"""

import argparse
import os
from pathlib import Path
from typing import Dict, Any


# Base directory for default paths
BASE_DIR = Path(__file__).parent.parent.parent.resolve()


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure argument parser for the pipeline.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="PVMAP Generation & Validation Pipeline"
    )

    # Dataset selection
    parser.add_argument(
        '--dataset',
        type=str,
        help='Process specific dataset (partial name match)'
    )
    parser.add_argument(
        '--resume-from',
        type=str,
        help='Resume from specific dataset (skip earlier ones)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be processed without executing'
    )

    # Sampling phase options
    parser.add_argument(
        '--skip-sampling',
        action='store_true',
        help='Skip sampling phase (use existing sampled data)'
    )
    parser.add_argument(
        '--force-resample',
        action='store_true',
        help='Force re-sampling even if sampled data exists'
    )

    # Schema selection phase options
    parser.add_argument(
        '--skip-schema-selection',
        action='store_true',
        help='Skip schema selection phase (use existing schema files)'
    )
    parser.add_argument(
        '--force-schema-selection',
        action='store_true',
        help='Force re-selection of schema files even if they exist'
    )
    parser.add_argument(
        '--schema-base-dir',
        type=str,
        default=str(BASE_DIR / "src" / "resources" / "schema_examples"),
        help='Path to schema files directory (default: src/resources/schema_examples/)'
    )

    # Evaluation phase options
    parser.add_argument(
        '--skip-evaluation',
        action='store_true',
        help='Skip evaluation phase (Phase 5)'
    )
    parser.add_argument(
        '--ground-truth-repo',
        type=str,
        default=os.environ.get(
            'GROUND_TRUTH_REPO',
            str(BASE_DIR.parent / "datacommonsorg-data" / "ground_truth")
        ),
        help='Path to datacommonsorg-data repo for ground truth PVMAPs '
             '(default: $GROUND_TRUTH_REPO or ../datacommonsorg-data/ground_truth)'
    )
    parser.add_argument(
        '--ground-truth-pvmap',
        type=str,
        help='Path to a single ground truth PVMAP file '
             '(takes precedence over --ground-truth-dir and --ground-truth-repo)'
    )
    parser.add_argument(
        '--ground-truth-dir',
        type=str,
        help='Path to directory containing ground truth PVMAP files '
             '(searched by dataset name, takes precedence over --ground-truth-repo)'
    )

    # Input/Output directories
    parser.add_argument(
        '--input-dir',
        type=str,
        default='input',
        help='Input directory containing datasets (default: input/)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output',
        help='Output directory for generated PVMAPs (default: output/)'
    )

    # Model configuration
    parser.add_argument(
        '--model', '-m',
        type=str,
        default='gemini-3-pro-preview',
        help='Gemini model to use (default: gemini-3-pro-preview)'
    )

    return parser


def parse_args(args=None) -> argparse.Namespace:
    """
    Parse command-line arguments.

    Args:
        args: Optional list of arguments to parse (for testing)

    Returns:
        Parsed arguments namespace
    """
    parser = create_parser()
    return parser.parse_args(args)


def args_to_dict(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Convert argparse.Namespace to dictionary for context.

    Args:
        args: Parsed arguments namespace

    Returns:
        Dictionary of argument values
    """
    return vars(args)


def get_cli_config(args=None) -> Dict[str, Any]:
    """
    Parse CLI arguments and return as configuration dictionary.

    Args:
        args: Optional list of arguments to parse (for testing)

    Returns:
        Configuration dictionary
    """
    parsed_args = parse_args(args)
    return args_to_dict(parsed_args)

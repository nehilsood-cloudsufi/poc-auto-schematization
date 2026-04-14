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
    # Column discovery options
    parser.add_argument(
        '--skip-column-discovery',
        action='store_true',
        help='Skip PVMAP skeleton generation (disables column completeness checking)'
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
        '--use-llm-judge',
        action='store_true',
        help='Enable LLM-as-judge qualitative evaluation (runs after GT comparison)'
    )
    parser.add_argument(
        '--ground-truth-repo',
        type=str,
        default=os.environ.get(
            'GROUND_TRUTH_REPO',
            str(BASE_DIR / "ground_truth")
        ),
        help='Path to ground truth PVMAPs '
             '(default: $GROUND_TRUTH_REPO or ground_truth/)'
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
        default='gemini-3.1-pro-preview',
        help='Gemini model to use (default: gemini-3.1-pro-preview)'
    )
    parser.add_argument(
        '--thinking-level',
        type=str,
        choices=['low', 'medium', 'high', 'minimal', 'none'],
        default='high',
        help='Thinking level for Gemini models (default: high). Use "none" to disable.'
    )

    # MCP integration
    parser.add_argument(
        '--enable-mcp',
        action='store_true',
        default=True,
        help='Enable Data Commons MCP integration for StatVar discovery (default: on)'
    )
    parser.add_argument(
        '--enable-schemaorg-mcp',
        action='store_true',
        help='Enable Schema.org MCP server for vocabulary lookup'
    )

    # Schema examples
    parser.add_argument(
        '--no-schema-examples',
        action='store_true',
        help='Skip schema example injection into PVMAP prompt'
    )

    # Input modes
    parser.add_argument(
        '--input-file',
        type=str,
        help='Standalone input file (no dataset folder required)'
    )
    parser.add_argument(
        '--use-metadata',
        action='store_true',
        help='Use metadata files for prompt building (default: off)'
    )
    parser.add_argument(
        '--metadata-file-path',
        type=str,
        help='Explicit metadata file path (auto-enables --use-metadata)'
    )
    parser.add_argument(
        '--schema-file',
        type=str,
        help='Explicit schema file override'
    )

    # Mapping plan workflow
    plan_group = parser.add_mutually_exclusive_group()
    plan_group.add_argument(
        '--plan-only',
        action='store_true',
        default=False,
        help='Generate mapping plan and exit without PVMAP generation'
    )
    plan_group.add_argument(
        '--from-plan',
        type=str,
        default=None,
        help='Path to approved mapping plan file (skips plan generation, goes straight to PVMAP generation)'
    )
    parser.add_argument(
        '--auto-approve',
        action='store_true',
        default=False,
        help='Auto-approve mapping plan without interactive prompt'
    )

    # Structured output
    parser.add_argument(
        '--structured-output',
        action=argparse.BooleanOptionalAction,
        default=True,
        help='Use structured output (deterministic CSV) [default: True]'
    )

    # Verbose
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    # Prompt version
    parser.add_argument(
        '--prompt-version',
        choices=['v2', 'v3'],
        default='v3',
        help='PVMAP prompt version to use (default: v3)'
    )

    # Feedback prompt version
    parser.add_argument(
        '--feedback-prompt-version',
        choices=['v1', 'v2'],
        default='v2',
        help='Feedback agent prompt version (default: v2)'
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

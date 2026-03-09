"""
06_use_with_our_data.py — Integration with auto-schematization project via ADK.

Uses DataAnalysisAgent (LlmAgent) to upload a CSV from our input/ directory,
ask questions about the data, and generate a briefing.

Usage:
    python 06_use_with_our_data.py --dataset bis_bis_central_bank_policy_rate
    python 06_use_with_our_data.py --file ../input/my_dataset/test_data/input_data.csv
"""

import argparse
import asyncio
import sys
from pathlib import Path

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from notebooklm.agents import create_data_analysis_agent
from notebooklm.tools import shutdown_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_ROOT / "input"


def find_dataset_csv(dataset_name: str) -> Path:
    """Find the input CSV for a dataset."""
    dataset_dir = INPUT_DIR / dataset_name / "test_data"
    if not dataset_dir.exists():
        print(f"Error: dataset directory not found: {dataset_dir}")
        sys.exit(1)

    csvs = list(dataset_dir.glob("*_input.csv")) + list(dataset_dir.glob("*.csv"))
    csvs = [f for f in csvs if "sampled" not in f.name]
    if not csvs:
        print(f"Error: no CSV files found in {dataset_dir}")
        sys.exit(1)

    return csvs[0]


def find_metadata(dataset_name: str) -> str | None:
    """Load metadata content if available."""
    meta_dir = INPUT_DIR / dataset_name / "input_metadata"
    if not meta_dir.exists():
        return None
    meta_files = list(meta_dir.glob("*.csv"))
    if not meta_files:
        return None
    return meta_files[0].read_text()


async def main():
    parser = argparse.ArgumentParser(description="Analyze project data via NotebookLM + ADK")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dataset", help="Dataset name from input/ directory")
    group.add_argument("--file", help="Direct path to a CSV file")
    args = parser.parse_args()

    if args.dataset:
        csv_path = find_dataset_csv(args.dataset)
        dataset_name = args.dataset
    else:
        csv_path = Path(args.file).resolve()
        dataset_name = csv_path.stem

    metadata = find_metadata(args.dataset) if args.dataset else None

    print(f"Dataset: {dataset_name}")
    print(f"CSV: {csv_path}")
    print(f"Size: {csv_path.stat().st_size / 1024:.1f} KB\n")

    agent = create_data_analysis_agent()
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name="notebooklm_data", session_service=session_service)

    session = await session_service.create_session(
        app_name="notebooklm_data",
        user_id="user",
    )

    message = (
        f"Analyze the dataset '{dataset_name}'.\n"
        f"The CSV file is at: {csv_path}\n"
    )
    if metadata:
        message += f"\nHere is the dataset metadata:\n{metadata}\n"
    message += (
        "\nPlease:\n"
        "1. Create a notebook and upload the CSV file.\n"
        "2. If metadata was provided, add it as a text source.\n"
        "3. Ask about column descriptions, geographic/temporal coverage, "
        "and how to map it into a Schema.org knowledge graph.\n"
        "4. Generate a briefing report and download it to "
        f"'briefing_{dataset_name[:40]}.md'.\n"
        "5. Delete the notebook when done."
    )

    print("Starting data analysis via ADK DataAnalysisAgent...\n")

    async for event in runner.run_async(
        user_id="user",
        session_id=session.id,
        new_message=message,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"[{event.author}] {part.text}\n")

    await shutdown_client()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())

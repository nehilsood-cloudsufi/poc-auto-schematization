"""
main.py — Coordinated runner for all NotebookLM + ADK demos.

Usage:
    python main.py                          # Interactive menu
    python main.py --demo quickstart        # Run specific demo
    python main.py --demo podcast --topic "AI in healthcare"
    python main.py --demo data --dataset bis_bis_central_bank_policy_rate
    python main.py --list                   # List available demos
"""

import argparse
import asyncio
import importlib
import sys

DEMOS = {
    "quickstart": {
        "module": "notebooklm.demos.01_quickstart",
        "description": "Create notebook, add URL, ask question, generate audio",
    },
    "chat": {
        "module": "notebooklm.demos.02_sources_and_chat",
        "description": "Add multiple sources, multi-turn chat",
    },
    "artifacts": {
        "module": "notebooklm.demos.03_generate_artifacts",
        "description": "Generate audio, report, and quiz artifacts",
    },
    "podcast": {
        "module": "notebooklm.demos.04_research_to_podcast",
        "description": "Research a topic and generate a podcast",
    },
    "bulk": {
        "module": "notebooklm.demos.05_bulk_import",
        "description": "Bulk import multiple sources concurrently",
    },
    "data": {
        "module": "notebooklm.demos.06_use_with_our_data",
        "description": "Analyze a project CSV dataset",
    },
}


def list_demos():
    print("Available demos:\n")
    for name, info in DEMOS.items():
        print(f"  {name:<12} {info['description']}")
    print()


def run_demo(name: str, extra_args: list[str]):
    """Import and run a demo module's main() function."""
    if name not in DEMOS:
        print(f"Unknown demo: {name}")
        print(f"Available: {', '.join(DEMOS.keys())}")
        sys.exit(1)

    # Inject extra args so the demo script can parse them
    # (e.g., 04_research_to_podcast.py reads sys.argv for topic)
    original_argv = sys.argv
    sys.argv = [DEMOS[name]["module"]] + extra_args

    try:
        module = importlib.import_module(DEMOS[name]["module"])
        asyncio.run(module.main())
    finally:
        sys.argv = original_argv


def interactive_menu():
    print("NotebookLM + ADK Demos")
    print("=" * 40)
    list_demos()

    choice = input("Enter demo name (or 'q' to quit): ").strip().lower()
    if choice in ("q", "quit", "exit"):
        return

    if choice in DEMOS:
        extra = []
        if choice == "podcast":
            topic = input("Topic (press Enter for default): ").strip()
            if topic:
                extra = topic.split()
        elif choice == "data":
            dataset = input("Dataset name: ").strip()
            if dataset:
                extra = ["--dataset", dataset]
            else:
                print("Dataset name is required for the data demo.")
                return

        run_demo(choice, extra)
    else:
        print(f"Unknown demo: {choice}")


def main():
    parser = argparse.ArgumentParser(
        description="Run NotebookLM + ADK demos",
        add_help=True,
    )
    parser.add_argument("--demo", help="Demo to run (see --list)")
    parser.add_argument("--list", action="store_true", help="List available demos")
    parser.add_argument("--topic", help="Topic for podcast demo")
    parser.add_argument("--dataset", help="Dataset for data demo")
    parser.add_argument("--file", help="CSV file for data demo")

    args, unknown = parser.parse_known_args()

    if args.list:
        list_demos()
        return

    if args.demo:
        extra = unknown[:]
        if args.topic:
            extra.extend(args.topic.split())
        if args.dataset:
            extra.extend(["--dataset", args.dataset])
        if args.file:
            extra.extend(["--file", args.file])
        run_demo(args.demo, extra)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()

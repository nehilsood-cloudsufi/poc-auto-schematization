"""
Gemini Query Tool for Data Commons Expert Consultation.

This tool queries Gemini 3 Pro Preview for expert guidance on Data Commons
best practices, particularly for StatVar design and dimension analysis.

Usage:
    python -m src.tools.gemini_query_tool "Your question about Data Commons"

    # Or with specific topics
    python -m src.tools.gemini_query_tool --topic statvar "How should I design StatVars for population data?"
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

# Import GeminiClient from our existing infrastructure
from src.data_commons.api.gemini_client import GeminiClient


# System context for Data Commons expertise
DATA_COMMONS_CONTEXT = """You are a Data Commons expert consultant specializing in:

1. **StatVar (Statistical Variable) Design**:
   - StatVars represent unique statistical measurements in Data Commons
   - Each StatVar has a unique DCID (Data Commons ID)
   - StatVars are defined by their properties: populationType, measuredProperty, statType, constraintProperties
   - Example: "Count_Person_Female" = Count of Female Persons

2. **PVMAP (Property-Value Map) Generation**:
   - PVMAPs define how to transform source CSV columns into Data Commons observations
   - Each row in the output must be a unique StatVarObservation
   - Key format: column header or value mapping to property-value pairs

3. **Dimension Analysis**:
   - Dimensions are columns that define the uniqueness of a StatVar
   - Common dimensions: geography (place), time (observationDate), demographic properties
   - Cartesian product of dimension values defines the observation space

4. **Data Commons Schema**:
   - Uses MCF (Meta Content Framework) format
   - StatVarObservations have: observationAbout, observationDate, variableMeasured, value
   - Places are referenced by DCIDs (e.g., "geoId/06" for California)

5. **Best Practices**:
   - Every observation must be uniquely identifiable by its dimensions
   - No duplicate observations for the same StatVar + Place + Time
   - Sampling must preserve dimension combination coverage
   - Understanding data "skeleton" (dimension structure) is crucial for correct mapping

Provide detailed, actionable guidance based on Data Commons specifications and best practices.
When discussing dimension detection or StatVar design, be specific about the criteria and heuristics.
"""


def query_gemini(
    question: str,
    topic: Optional[str] = None,
    include_examples: bool = True,
    temperature: float = 0.1,
    model: str = "gemini-3.1-pro-preview",
) -> dict:
    """Query Gemini for Data Commons expert guidance.

    Args:
        question: The question to ask about Data Commons best practices.
        topic: Optional topic focus (statvar, dimension, sampling, pvmap).
        include_examples: Whether to request concrete examples in response.
        temperature: Model temperature (0-1). Lower = more deterministic.
        model: Gemini model to use.

    Returns:
        dict with keys:
            - question: Original question
            - topic: Topic focus (if provided)
            - response: Gemini's response text
            - model: Model used
            - timestamp: ISO timestamp
            - thinking: Model's reasoning (if available)
    """
    # Build the prompt with context
    topic_guidance = ""
    if topic:
        topic_guides = {
            "statvar": "Focus on StatVar design, uniqueness requirements, and property definitions.",
            "dimension": "Focus on dimension detection heuristics, column classification, and uniqueness criteria.",
            "sampling": "Focus on sampling strategies that preserve dimension combination coverage.",
            "pvmap": "Focus on PVMAP generation best practices and mapping strategies.",
            "mcp": "Focus on MCP (Model Context Protocol) integration for StatVar discovery.",
        }
        topic_guidance = f"\n\nTopic Focus: {topic_guides.get(topic, topic)}"

    example_request = ""
    if include_examples:
        example_request = "\n\nPlease include concrete examples where applicable."

    prompt = f"""{DATA_COMMONS_CONTEXT}{topic_guidance}

Question: {question}{example_request}

Provide a comprehensive but focused response. Structure your answer with clear sections if appropriate."""

    # Query Gemini
    client = GeminiClient(model_name=model)

    try:
        result = client.generate_content_with_metadata(
            prompt=prompt,
            temperature=temperature,
            max_output_tokens=8192,  # Allow detailed responses
        )

        return {
            "question": question,
            "topic": topic,
            "response": result.get("text", ""),
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "duration_ms": result.get("duration_ms"),
            "total_tokens": result.get("total_tokens"),
            "thinking": result.get("thinking_content", []),
        }
    except Exception as e:
        return {
            "question": question,
            "topic": topic,
            "response": None,
            "error": str(e),
            "model": model,
            "timestamp": datetime.now().isoformat(),
        }


def batch_query(questions: list[dict], output_file: Optional[Path] = None) -> list[dict]:
    """Query Gemini with multiple questions.

    Args:
        questions: List of dicts with 'question' and optional 'topic' keys.
        output_file: Optional path to save results as JSON.

    Returns:
        List of response dicts.
    """
    results = []
    for i, q in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] Querying: {q.get('question', '')[:60]}...")
        result = query_gemini(
            question=q.get("question", ""),
            topic=q.get("topic"),
            include_examples=q.get("include_examples", True),
        )
        results.append(result)

        # Print brief status
        if result.get("response"):
            print(f"  ✓ Got response ({result.get('total_tokens', '?')} tokens)")
        else:
            print(f"  ✗ Error: {result.get('error', 'Unknown error')}")

    if output_file:
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_file}")

    return results


def format_response(result: dict) -> str:
    """Format a query result for display.

    Args:
        result: Response dict from query_gemini.

    Returns:
        Formatted string for display.
    """
    lines = []
    lines.append("=" * 80)
    lines.append(f"Question: {result.get('question', 'N/A')}")
    if result.get("topic"):
        lines.append(f"Topic: {result['topic']}")
    lines.append(f"Model: {result.get('model', 'N/A')}")
    lines.append(f"Timestamp: {result.get('timestamp', 'N/A')}")
    if result.get("duration_ms"):
        lines.append(f"Duration: {result['duration_ms']}ms")
    if result.get("total_tokens"):
        lines.append(f"Tokens: {result['total_tokens']}")
    lines.append("-" * 80)

    if result.get("response"):
        lines.append(result["response"])
    elif result.get("error"):
        lines.append(f"ERROR: {result['error']}")
    else:
        lines.append("No response received.")

    lines.append("=" * 80)
    return "\n".join(lines)


def main():
    """CLI for the Gemini Query Tool."""
    parser = argparse.ArgumentParser(
        description="Query Gemini for Data Commons expert guidance"
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="The question to ask about Data Commons best practices",
    )
    parser.add_argument(
        "--topic", "-t",
        choices=["statvar", "dimension", "sampling", "pvmap", "mcp"],
        help="Topic focus for the question",
    )
    parser.add_argument(
        "--no-examples",
        action="store_true",
        help="Don't request examples in the response",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Model temperature (0.0-1.0, default: 0.1)",
    )
    parser.add_argument(
        "--model", "-m",
        default="gemini-3.1-pro-preview",
        help="Gemini model to use (default: gemini-3.1-pro-preview)",
    )
    parser.add_argument(
        "--batch", "-b",
        type=Path,
        help="Path to JSON file with batch questions",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Path to save results as JSON",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted text",
    )

    args = parser.parse_args()

    # Batch mode
    if args.batch:
        if not args.batch.exists():
            print(f"Error: Batch file not found: {args.batch}")
            return 1
        with open(args.batch) as f:
            questions = json.load(f)
        results = batch_query(questions, args.output)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            for result in results:
                print(format_response(result))
        return 0

    # Single question mode
    if not args.question:
        parser.print_help()
        return 1

    result = query_gemini(
        question=args.question,
        topic=args.topic,
        include_examples=not args.no_examples,
        temperature=args.temperature,
        model=args.model,
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Results saved to: {args.output}")

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_response(result))

    return 0 if result.get("response") else 1


if __name__ == "__main__":
    exit(main())

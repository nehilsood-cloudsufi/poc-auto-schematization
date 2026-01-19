"""
Agno-based Auto-Schematization Pipeline using Gemini.

This module replaces the Claude CLI-based pipeline with an Agno agent
that uses Gemini for PVMAP generation and schema selection.
"""

import csv
import io
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Dict

from agno.agent import Agent
from agno.models.google import Gemini

# Add paths for imports
BASE_DIR = Path(__file__).parent.resolve()
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "tools"))
sys.path.append(str(BASE_DIR / "util"))

# Schema categories
SCHEMA_CATEGORIES = ['Demographics', 'Economy', 'Education', 'Employment', 'Energy', 'Health']


class PVMAPAgent:
    """Agno agent for PVMAP generation using Gemini."""

    def __init__(self, api_key: str, model_id: str = "gemini-2.0-flash"):
        """Initialize the agent with Gemini model."""
        self.api_key = api_key
        self.model_id = model_id
        os.environ["GOOGLE_API_KEY"] = api_key

        # Create Agno agent with Gemini
        self.agent = Agent(
            model=Gemini(id=model_id),
            markdown=True,
            description="Data Commons PVMAP generation expert"
        )

    def sample_csv(self, input_file: Path, output_file: Path, max_rows: int = 100) -> bool:
        """Sample CSV file to max_rows for processing."""
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)

            if len(rows) <= max_rows + 1:  # +1 for header
                # File is small enough, just copy
                with open(output_file, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
            else:
                # Sample rows
                header = rows[0]
                data_rows = rows[1:]

                # Take evenly distributed samples
                step = max(1, len(data_rows) // (max_rows - 1))
                sampled = [header] + data_rows[::step][:max_rows]

                with open(output_file, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(sampled)

            return True
        except Exception as e:
            print(f"Error sampling CSV: {e}")
            return False

    def select_schema(self, metadata_content: str, data_preview: str) -> str:
        """Use Gemini to select the best schema category."""
        category_info = {
            'Demographics': 'Population, age, gender, race, household, nativity data',
            'Economy': 'GDP, business establishments, revenue, trade, commodities',
            'Education': 'School enrollment, degrees, educational attainment, literacy',
            'Employment': 'Labor force, jobs, wages, unemployment, occupations',
            'Energy': 'Power generation, consumption, renewable energy, infrastructure',
            'Health': 'Disease prevalence, mortality, healthcare access, medical conditions'
        }

        prompt = f"""You are a data schema classification expert. Analyze this dataset and select the most appropriate schema category.

## Dataset Metadata Configuration:

{metadata_content}

## Sample Data (first rows):

{data_preview}

## Available Schema Categories:

"""
        for i, (cat, desc) in enumerate(category_info.items(), 1):
            prompt += f"{i}. **{cat}**: {desc}\n"

        prompt += """
## Task:

Based on the metadata and data columns, select ONE category that best matches this dataset.

**Important:** Respond with ONLY the category name (Demographics, Economy, Education, Employment, Energy, or Health). No explanation, no punctuation - just the category name.

Selected Category:"""

        response = self.agent.run(prompt)
        result = response.content.strip()

        # Parse response to get category
        for cat in SCHEMA_CATEGORIES:
            if cat.lower() in result.lower():
                return cat

        # Default to Economy if can't determine
        return "Economy"

    def load_prompt_template(self) -> str:
        """Load the PVMAP prompt template."""
        prompt_file = BASE_DIR / "tools" / "improved_pvmap_prompt.txt"
        if prompt_file.exists():
            with open(prompt_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    def load_schema_examples(self, schema_category: str) -> str:
        """Load schema examples for the given category."""
        schema_file = BASE_DIR / "schema_example_files" / schema_category / \
                      f"scripts_statvar_llm_config_schema_examples_dc_topic_{schema_category}.txt"
        if schema_file.exists():
            with open(schema_file, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    def generate_pvmap(self, sampled_data: str, metadata: str, schema_examples: str,
                       error_feedback: str = "") -> Tuple[bool, str]:
        """Generate PVMAP using Gemini via Agno agent."""
        # Load and populate prompt template
        template = self.load_prompt_template()

        if not template:
            return False, "Could not load prompt template"

        # Replace placeholders
        prompt = template.replace("{{SCHEMA_EXAMPLES}}", schema_examples)
        prompt = template.replace("{{SAMPLED_DATA}}", sampled_data)
        prompt = template.replace("{{METADATA_CONFIG}}", metadata)

        # Add error feedback if retrying
        if error_feedback:
            prompt += f"\n\n## PREVIOUS ATTEMPT FAILED\n\nError from validation:\n{error_feedback}\n\nPlease fix the issues and regenerate the PVMAP."

        # Call Gemini via Agno
        response = self.agent.run(prompt)
        output = response.content

        # Extract CSV from response
        pvmap_csv = self.extract_pvmap_csv(output)

        if pvmap_csv:
            return True, pvmap_csv
        else:
            return False, output

    def extract_pvmap_csv(self, output: str) -> Optional[str]:
        """Extract the PVMAP CSV from Gemini's output."""
        lines = output.split('\n')
        csv_lines = []
        in_csv = False

        for line in lines:
            stripped = line.strip()

            # Start of CSV (header row)
            if stripped.startswith('key,') or stripped == 'key':
                in_csv = True
                csv_lines = [stripped]
                continue

            if in_csv:
                # End of CSV (empty line or markdown)
                if not stripped or stripped.startswith('#') or stripped.startswith('```'):
                    if csv_lines:
                        break
                else:
                    csv_lines.append(stripped)

        if csv_lines:
            return '\n'.join(csv_lines)

        # Fallback: look for CSV in code blocks
        code_block_pattern = r'```(?:csv)?\n(key[,\n].*?)```'
        matches = re.findall(code_block_pattern, output, re.DOTALL)

        if matches:
            return matches[0].strip()

        return None


def run_validation(input_file: Path, pvmap_file: Path, metadata_file: Path,
                   output_dir: Path) -> Tuple[bool, str]:
    """Run stat_var_processor.py validation."""
    env = os.environ.copy()
    pythonpath_parts = [
        str(BASE_DIR),
        str(BASE_DIR / "tools"),
        str(BASE_DIR / "util"),
        env.get('PYTHONPATH', '')
    ]
    env['PYTHONPATH'] = ':'.join(filter(None, pythonpath_parts))

    cmd = [
        'python3',
        str(BASE_DIR / 'tools' / 'stat_var_processor.py'),
        f'--input_data={input_file}',
        f'--pv_map={pvmap_file}',
        f'--config_file={metadata_file}',
        '--generate_statvar_name=True',
        f'--output_path={output_dir}/processed'
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(BASE_DIR),
            env=env
        )

        if result.returncode == 0:
            # Check if output has data
            output_file = output_dir / "processed.csv"
            if output_file.exists():
                with open(output_file, 'r', encoding='utf-8') as f:
                    lines = [l for l in f.readlines() if l.strip()]
                if len(lines) > 1:  # More than just header
                    return True, "Validation successful"

            return False, f"Validation produced empty output.\n{result.stderr or result.stdout}"

        return False, f"Validation failed:\n{result.stderr or result.stdout}"

    except subprocess.TimeoutExpired:
        return False, "Validation timed out"
    except Exception as e:
        return False, f"Validation error: {str(e)}"


def run_pipeline(dataset_name: str, input_dir: Path, output_dir: Path,
                 schema_category: Optional[str] = None,
                 api_key: Optional[str] = None,
                 model_id: str = "gemini-2.0-flash",
                 max_retries: int = 2) -> Tuple[bool, str]:
    """
    Run the complete PVMAP generation pipeline using Agno + Gemini.

    Args:
        dataset_name: Name of the dataset
        input_dir: Path to input directory
        output_dir: Path to output directory
        schema_category: Optional schema category (auto-detected if not provided)
        api_key: Gemini API key (uses GOOGLE_API_KEY env var if not provided)
        model_id: Gemini model ID
        max_retries: Maximum retry attempts on validation failure

    Returns:
        Tuple of (success, message)
    """
    # Get API key
    api_key = api_key or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return False, "No Gemini API key provided"

    # Initialize agent
    agent = PVMAPAgent(api_key, model_id)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find input files
    test_data_dir = input_dir / "test_data"
    input_files = list(test_data_dir.glob("*_input.csv")) if test_data_dir.exists() else []
    metadata_files = list(input_dir.glob("*_metadata.csv"))

    if not input_files:
        return False, "No input CSV files found"
    if not metadata_files:
        return False, "No metadata files found"

    input_file = input_files[0]
    metadata_file = metadata_files[0]

    # Step 1: Sample data
    print(f"[1/4] Sampling data from {input_file.name}...")
    sampled_file = test_data_dir / f"{dataset_name}_sampled_data.csv"
    if not agent.sample_csv(input_file, sampled_file):
        return False, "Failed to sample data"

    # Load sampled data
    with open(sampled_file, 'r', encoding='utf-8') as f:
        sampled_data = f.read()

    # Load metadata
    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = f.read()

    # Step 2: Schema selection
    if not schema_category:
        print("[2/4] Auto-detecting schema category...")
        schema_category = agent.select_schema(metadata, sampled_data[:2000])
        print(f"      Selected: {schema_category}")
    else:
        print(f"[2/4] Using provided schema: {schema_category}")

    # Load schema examples
    schema_examples = agent.load_schema_examples(schema_category)

    # Step 3: Generate PVMAP with retries
    print("[3/4] Generating PVMAP with Gemini...")
    pvmap_file = output_dir / "generated_pvmap.csv"
    error_feedback = ""

    for attempt in range(max_retries + 1):
        if attempt > 0:
            print(f"      Retry {attempt}/{max_retries}...")

        success, result = agent.generate_pvmap(sampled_data, metadata, schema_examples, error_feedback)

        if success:
            # Save PVMAP
            with open(pvmap_file, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"      PVMAP saved to {pvmap_file}")

            # Step 4: Validate
            print("[4/4] Validating PVMAP...")
            valid, validation_msg = run_validation(input_file, pvmap_file, metadata_file, output_dir)

            if valid:
                print("      Validation successful!")
                return True, f"Pipeline completed successfully for {dataset_name}"
            else:
                print(f"      Validation failed: {validation_msg[:200]}...")
                error_feedback = validation_msg
        else:
            print(f"      Generation failed: {result[:200]}...")
            error_feedback = f"Could not extract PVMAP CSV from output: {result[:500]}"

    return False, f"Pipeline failed after {max_retries + 1} attempts"


# Standalone execution
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run PVMAP generation pipeline with Agno + Gemini")
    parser.add_argument("--dataset", required=True, help="Dataset name")
    parser.add_argument("--input-dir", default="input", help="Input directory")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    parser.add_argument("--schema", help="Schema category (auto-detected if not provided)")
    parser.add_argument("--model", default="gemini-2.0-flash", help="Gemini model ID")

    args = parser.parse_args()

    input_path = Path(args.input_dir) / args.dataset
    output_path = Path(args.output_dir) / args.dataset

    success, message = run_pipeline(
        dataset_name=args.dataset,
        input_dir=input_path,
        output_dir=output_path,
        schema_category=args.schema,
        model_id=args.model
    )

    print(f"\n{'SUCCESS' if success else 'FAILED'}: {message}")
    sys.exit(0 if success else 1)

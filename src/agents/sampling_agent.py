"""
Sampling Agent for ADK pipeline.

Creates data samples for schema selection and PVMAP generation.
Uses Pattern 1: Simple BaseAgent (deterministic logic, no LLM needed).

This agent checks for existing sampled files and either reuses them
or creates new ones using the data_sampler tool.
"""

import sys
from pathlib import Path
from typing import AsyncGenerator, List

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from src.tools.data_sampler_tool import sample_data
from src.state.dataset_info import DatasetInfo


class SamplingAgent(BaseAgent):
    """
    Agent for sampling dataset files.

    This is a simple (non-LLM) agent that performs deterministic
    file checking and sampling operations.

    ADK State Inputs:
        - current_dataset: DatasetInfo - Current dataset being processed
        - skip_sampling: bool - Whether to skip sampling
        - force_resample: bool - Whether to force resampling

    ADK State Outputs:
        - sampled_data_files: List[Path] - Individual sampled data files
        - combined_sampled_data: Path - Combined sampled data file
        - sampling_success: bool - Whether sampling succeeded
        - error: str | None - Error message if sampling failed
    """

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Run sampling logic using ADK pattern.

        Checks for existing sampled files and either reuses them
        or creates new ones.

        Args:
            ctx: ADK invocation context with session state

        Yields:
            Events with sampling results
        """
        # 1. Check skip flag
        skip_sampling = ctx.session.state.get("skip_sampling", False)
        if skip_sampling:
            ctx.session.state["sampling_success"] = True
            ctx.session.state["error"] = None

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Sampling skipped (skip_sampling=True)")
                ])
            )
            return

        # 2. Get dataset from state
        current_dataset: DatasetInfo = ctx.session.state.get("current_dataset")
        if not current_dataset:
            ctx.session.state["error"] = "No current_dataset specified in state"
            ctx.session.state["sampling_success"] = False

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Sampling failed: No current_dataset in state")
                ])
            )
            return

        force_resample = ctx.session.state.get("force_resample", False)

        # 3. Check for existing sampled files
        test_data_dir = current_dataset.path / "test_data"
        existing_sampled_files: List[Path] = []
        combined_sampled: Path | None = None

        if test_data_dir.exists() and not force_resample:
            for file in test_data_dir.iterdir():
                if file.suffix == '.csv' and 'sampled' in file.name.lower():
                    existing_sampled_files.append(file)
                    if 'combined' in file.name.lower():
                        combined_sampled = file

        # 4. Reuse existing samples if found
        if existing_sampled_files and not force_resample:
            # Update DatasetInfo object directly
            current_dataset.sampled_data_files = existing_sampled_files
            current_dataset.combined_sampled_data = combined_sampled if combined_sampled else existing_sampled_files[0]

            # Also set state keys for backward compatibility
            ctx.session.state["sampled_data_files"] = [str(f) for f in existing_sampled_files]
            ctx.session.state["combined_sampled_data"] = str(current_dataset.combined_sampled_data)
            ctx.session.state["sampling_success"] = True
            ctx.session.state["error"] = None

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Using existing sampled files: {len(existing_sampled_files)} files found")
                ])
            )
            return

        # 5. Need to create new samples
        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text=f"Creating new samples for {current_dataset.name}...")
            ])
        )

        # Find input CSV files to sample
        input_files = current_dataset.input_data_files
        if not input_files:
            # Try to discover input files
            if test_data_dir.exists():
                input_files = [f for f in test_data_dir.iterdir()
                              if f.suffix == '.csv' and 'input' in f.name.lower() and 'sampled' not in f.name.lower()]

        if not input_files:
            ctx.session.state["error"] = f"No input CSV files found in {test_data_dir}"
            ctx.session.state["sampling_success"] = False

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Sampling failed: No input files found")
                ])
            )
            return

        # 6. Sample each input file
        sampled_files: List[str] = []
        errors: List[str] = []

        for input_file in input_files:
            # Generate output filename
            output_file = input_file.parent / f"{input_file.stem}_sampled_data.csv"

            # Call sample_data tool
            result = sample_data(
                input_file=str(input_file),
                output_file=str(output_file)
            )

            if result["success"]:
                sampled_files.append(result["output_file"])
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Sampled {input_file.name}: {result['rows_sampled']} rows")
                    ])
                )
            else:
                errors.append(f"{input_file.name}: {result['error']}")

        # 7. Check results
        if not sampled_files:
            ctx.session.state["error"] = f"All sampling failed: {'; '.join(errors)}"
            ctx.session.state["sampling_success"] = False

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Sampling failed: {errors[0] if errors else 'Unknown error'}")
                ])
            )
            return

        # 8. Use first sampled file as combined (or create actual combined file)
        combined_file = sampled_files[0] if len(sampled_files) == 1 else sampled_files[0]

        # Update DatasetInfo object directly
        current_dataset.sampled_data_files = [Path(f) for f in sampled_files]
        current_dataset.combined_sampled_data = Path(combined_file)

        # Also set state keys for backward compatibility
        ctx.session.state["sampled_data_files"] = sampled_files
        ctx.session.state["combined_sampled_data"] = combined_file
        ctx.session.state["sampling_success"] = True
        ctx.session.state["error"] = None

        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text=f"Sampling complete: {len(sampled_files)} files created")
            ])
        )

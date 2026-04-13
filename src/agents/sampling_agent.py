"""Programmatic Sampling Agent — Python controls flow, LLM does reasoning.

Replaces the LLM-orchestrated SamplingAgentWrapper with a deterministic
6-step DAG that uses exactly 2 LLM calls for semantic reasoning:

DAG: profile -> semantic_analysis -> skeleton -> sampling -> grounding -> assembly

The agent maintains the same state contract as SamplingAgentWrapper so
downstream agents (SchemaSelection, PVMAPGenerator, Evaluation) see no change.

State Contract:
    Reads:  current_dataset, skip_sampling, force_resample
    Writes: skeleton_summary, data_context, sampling_success,
            sampled_data_path, context_file_path
"""

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from typing import AsyncGenerator, Optional

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.agents.sampling.schemas import RelationalSkeleton, SemanticAnalysis
from src.agents.sampling.semantic_analyzer import create_semantic_analyzer
from src.agents.sampling.skeleton_mapper import create_skeleton_mapper
from src.pipeline.sampling.context_assembler import assemble_context
from src.pipeline.sampling.profiler import profile_dataset
from src.pipeline.sampling.statvar_grounder import ground_statvars
from src.pipeline.sampling.stratified_sampler import execute_sampling

logger = logging.getLogger(__name__)


class ProgrammaticSamplingAgent(BaseAgent):
    """Programmatic sampling agent with exactly 2 LLM calls.

    Steps:
        1. CODE: Profile dataset (pandas, <2s)
        2. LLM:  Semantic analysis (single-shot, output_schema)
        3. LLM:  Relational skeleton (single-shot, output_schema)
        4. CODE: Execute sampling (deterministic, pandas)
        5. CODE: Ground StatVars (optional, DC API)
        6. CODE: Assemble context (deterministic, template)
    """

    def __init__(
        self,
        name: str = "ProgrammaticSamplingAgent",
        model: Optional[str] = None,
        enable_mcp: bool = False,
        mcp_url: Optional[str] = None,
    ):
        super().__init__(name=name)
        self._model = model or os.getenv("SAMPLING_AGENT_MODEL", "gemini-3.1-pro-preview")
        self._enable_mcp = enable_mcp
        self._mcp_url = mcp_url

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Run the 6-step programmatic sampling DAG."""

        # --- Pre-checks ---
        skip_sampling = ctx.session.state.get("skip_sampling", False)
        if skip_sampling:
            yield self._emit("Sampling skipped per skip_sampling flag")
            ctx.session.state["sampling_success"] = True
            # Preserve existing skeleton_summary from Phase 1 state (if injected
            # via extra_initial_state). Only set to empty if not already present.
            if not ctx.session.state.get("skeleton_summary"):
                ctx.session.state["skeleton_summary"] = ""
            return

        current_dataset = ctx.session.state.get("current_dataset")
        if not current_dataset:
            yield self._emit("No current_dataset in session state")
            ctx.session.state["sampling_success"] = False
            ctx.session.state["error"] = "No current_dataset specified"
            return

        # Resolve input file
        input_file = None
        if current_dataset.input_data_files:
            input_file = Path(str(current_dataset.input_data_files[0]))

        if not input_file or not input_file.exists():
            yield self._emit(f"No input file found for {current_dataset.name}")
            ctx.session.state["sampling_success"] = False
            ctx.session.state["error"] = "No input data file available"
            return

        # Output paths
        output_dir = Path(current_dataset.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        sampled_file = output_dir / "agentic_sampled.csv"
        context_file = output_dir / "data_context.json"

        # --- Cache check ---
        force_resample = ctx.session.state.get("force_resample", False)
        if context_file.exists() and not force_resample:
            yield self._emit("Found existing data_context.json, loading from cache")
            try:
                with open(context_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                self._populate_state(ctx, cached, str(context_file))
                yield self._emit("Loaded cached sampling context successfully")
                return
            except Exception as e:
                yield self._emit(f"Cache load failed: {e}, re-running sampling")

        yield self._emit(f"Starting programmatic sampling for {current_dataset.name}")

        try:
            # --- Step 1: Profile dataset (CODE) ---
            yield self._emit("Step 1/6: Profiling dataset...")
            profile = profile_dataset(input_file)
            yield self._emit(
                f"Profile: {profile.total_rows} rows, {profile.total_columns} cols, "
                f"preformatted={profile.is_preformatted_dc}"
            )

            # --- Step 2: Semantic analysis (LLM) ---
            yield self._emit("Step 2/6: Running semantic analysis (LLM)...")
            analysis = await self._run_semantic_analysis(profile)
            yield self._emit(
                f"Analysis: topology={analysis.topology}, "
                f"population={analysis.population_type}, "
                f"preformatted={analysis.is_preformatted_dc}"
            )

            # --- Step 3: Relational skeleton (LLM) ---
            yield self._emit("Step 3/6: Building relational skeleton (LLM)...")
            skeleton = await self._run_skeleton_mapping(profile, analysis)
            yield self._emit(
                f"Skeleton: pattern={skeleton.statvar_pattern}, "
                f"dims={skeleton.dimension_columns}, "
                f"place={skeleton.place_column}, time={skeleton.time_column}"
            )

            # --- Step 4: Execute sampling (CODE) ---
            yield self._emit("Step 4/6: Executing deterministic sampling...")
            sample_result = execute_sampling(
                file_path=input_file,
                output_path=sampled_file,
                skeleton=skeleton,
                analysis=analysis,
                profile=profile,
            )
            if not sample_result.success:
                yield self._emit(f"Sampling failed: {sample_result.error}")
                ctx.session.state["sampling_success"] = False
                ctx.session.state["error"] = sample_result.error
                return
            yield self._emit(
                f"Sampled {sample_result.rows_sampled} rows "
                f"(strategy={sample_result.strategy_used})"
            )

            # --- Step 5: Ground StatVars (CODE, optional) ---
            grounded = []
            if self._enable_mcp:
                yield self._emit("Step 5/6: Grounding StatVars via DC API...")
                grounded = ground_statvars(
                    skeleton, analysis, enable_mcp=True, mcp_url=self._mcp_url
                )
                confirmed = sum(1 for g in grounded if g.confirmed)
                yield self._emit(f"Grounded {confirmed}/{len(grounded)} StatVars")
            else:
                yield self._emit("Step 5/6: StatVar grounding skipped (no --enable-mcp)")

            # --- Step 6: Assemble context (CODE) ---
            yield self._emit("Step 6/6: Assembling context...")
            skeleton_summary, data_context = assemble_context(
                profile=profile,
                analysis=analysis,
                skeleton=skeleton,
                sampled_file=sampled_file,
                grounded_statvars=grounded if grounded else None,
            )
            yield self._emit(
                f"Context assembled: skeleton_summary={len(skeleton_summary)} chars"
            )

            # --- Persist to state ---
            ctx.session.state["skeleton_summary"] = skeleton_summary
            ctx.session.state["data_context"] = data_context
            ctx.session.state["sampling_success"] = True
            ctx.session.state["sampled_data_path"] = str(sampled_file)
            ctx.session.state["context_file_path"] = str(context_file)

            yield self._emit("Programmatic sampling complete")

        except Exception as e:
            logger.exception("Programmatic sampling failed")
            yield self._emit(f"ERROR: Sampling failed: {e}")
            ctx.session.state["sampling_success"] = False
            ctx.session.state["error"] = str(e)

    async def _run_semantic_analysis(
        self, profile: 'DatasetProfile'
    ) -> SemanticAnalysis:
        """Run SemanticAnalyzer LlmAgent and extract structured output."""
        agent = create_semantic_analyzer(self._model)
        profile_json = json.dumps(profile.to_dict(), indent=2)

        session_service = InMemorySessionService()
        runner = Runner(
            app_name="semantic_analysis",
            agent=agent,
            session_service=session_service,
        )

        session_id = f"sem_{uuid.uuid4().hex[:8]}"

        # Pre-populate state so {dataset_profile} resolves in instruction template
        await session_service.create_session(
            app_name="semantic_analysis",
            user_id="sampler",
            session_id=session_id,
            state={"dataset_profile": profile_json},
        )

        message = types.Content(parts=[types.Part(text="Analyze this dataset profile.")])

        result = None
        for event in runner.run(
            user_id="sampler",
            session_id=session_id,
            new_message=message,
        ):
            # Check for structured output in event
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        try:
                            data = json.loads(part.text)
                            result = SemanticAnalysis(**data)
                        except (json.JSONDecodeError, Exception):
                            pass

        # Also check session state for output_key
        if result is None:
            try:
                session = await session_service.get_session(
                    app_name="semantic_analysis",
                    user_id="sampler",
                    session_id=session_id,
                )
                if session and session.state:
                    state_result = session.state.get("semantic_analysis")
                    if state_result:
                        if isinstance(state_result, SemanticAnalysis):
                            result = state_result
                        elif isinstance(state_result, dict):
                            result = SemanticAnalysis(**state_result)
            except Exception as e:
                logger.warning("Failed to read semantic_analysis from session state: %s", e)

        if result is None:
            raise RuntimeError("SemanticAnalyzer did not return valid output")

        return result

    async def _run_skeleton_mapping(
        self, profile: 'DatasetProfile', analysis: SemanticAnalysis
    ) -> RelationalSkeleton:
        """Run SkeletonMapper LlmAgent and extract structured output."""
        agent = create_skeleton_mapper(self._model)
        profile_json = json.dumps(profile.to_dict(), indent=2)
        analysis_json = analysis.model_dump_json(indent=2)

        session_service = InMemorySessionService()
        runner = Runner(
            app_name="skeleton_mapping",
            agent=agent,
            session_service=session_service,
        )

        session_id = f"skel_{uuid.uuid4().hex[:8]}"

        # Pre-populate state so {dataset_profile} and {semantic_analysis} resolve
        await session_service.create_session(
            app_name="skeleton_mapping",
            user_id="sampler",
            session_id=session_id,
            state={
                "dataset_profile": profile_json,
                "semantic_analysis": analysis_json,
            },
        )

        message = types.Content(parts=[types.Part(text="Build relational skeleton.")])

        result = None
        for event in runner.run(
            user_id="sampler",
            session_id=session_id,
            new_message=message,
        ):
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        try:
                            data = json.loads(part.text)
                            result = RelationalSkeleton(**data)
                        except (json.JSONDecodeError, Exception):
                            pass

        # Check session state
        if result is None:
            try:
                session = await session_service.get_session(
                    app_name="skeleton_mapping",
                    user_id="sampler",
                    session_id=session_id,
                )
                if session and session.state:
                    state_result = session.state.get("relational_skeleton")
                    if state_result:
                        if isinstance(state_result, RelationalSkeleton):
                            result = state_result
                        elif isinstance(state_result, dict):
                            result = RelationalSkeleton(**state_result)
            except Exception as e:
                logger.warning("Failed to read relational_skeleton from session state: %s", e)

        if result is None:
            raise RuntimeError("SkeletonMapper did not return valid output")

        return result

    def _populate_state(
        self,
        ctx: InvocationContext,
        data_context: dict,
        context_file_path: str,
    ) -> None:
        """Populate session state from cached data context.

        Same logic as SamplingAgentWrapper._populate_state_from_context().
        """
        ctx.session.state["skeleton_summary"] = data_context.get("skeleton_summary", "")
        ctx.session.state["data_context"] = data_context.get("data_context", data_context)
        ctx.session.state["sampling_success"] = data_context.get("success", True)
        ctx.session.state["context_file_path"] = context_file_path

        sampled_path = data_context.get("sampled_file") or data_context.get(
            "data_context", {}
        ).get("sampled_file")
        if sampled_path:
            ctx.session.state["sampled_data_path"] = sampled_path
        else:
            current_dataset = ctx.session.state.get("current_dataset")
            if current_dataset and hasattr(current_dataset, 'output_dir'):
                fallback = Path(current_dataset.output_dir) / "agentic_sampled.csv"
                if fallback.exists():
                    ctx.session.state["sampled_data_path"] = str(fallback)

    def _emit(self, text: str) -> Event:
        """Create an event with text content."""
        return Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text=text)])
        )

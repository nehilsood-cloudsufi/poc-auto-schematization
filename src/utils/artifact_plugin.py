"""Custom plugin for saving agent artifacts."""
from google.adk.plugins import BasePlugin
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from pathlib import Path
from typing import Optional
from datetime import datetime
import json


class ArtifactLoggingPlugin(BasePlugin):
    """
    Plugin to save agent execution artifacts.

    Captures:
    - LLM responses per attempt
    - Generation notes with reasoning
    - Error feedback chains
    - Retry history
    """

    def __init__(self, output_dir: Path, dataset_name: str):
        """
        Initialize artifact logger.

        Args:
            output_dir: Base output directory (e.g., src/output/)
            dataset_name: Current dataset being processed
        """
        super().__init__(name="artifact_logger")
        self.output_dir = output_dir
        self.dataset_name = dataset_name

        # Create dataset output directory
        self.dataset_dir = output_dir / dataset_name
        self.dataset_dir.mkdir(parents=True, exist_ok=True)

        # Track attempts
        self.attempt_count = 0
        self.generation_notes = []

        # Create generated_response directory
        self.response_dir = self.dataset_dir / "generated_response"
        self.response_dir.mkdir(exist_ok=True)

    async def after_model_callback(
        self,
        *,
        callback_context: CallbackContext,
        llm_response: LlmResponse,
    ) -> Optional[LlmResponse]:
        """Save LLM response after each model call."""

        # Only track PVMAP generation agent
        if "PVMAPGeneration" in callback_context.agent_name:
            # Extract response text
            response_text = ""
            if llm_response.candidates:
                candidate = llm_response.candidates[0]
                if candidate.content and candidate.content.parts:
                    response_text = candidate.content.parts[0].text

            # Save attempt file
            attempt_file = self.response_dir / f"attempt_{self.attempt_count}.md"
            timestamp = datetime.now().isoformat()

            with open(attempt_file, 'w') as f:
                f.write(f"# PVMAP Generation Attempt {self.attempt_count}\n")
                f.write(f"**Timestamp:** {timestamp}\n")
                f.write(f"**Agent:** {callback_context.agent_name}\n")
                f.write(f"**Invocation ID:** {callback_context.invocation_id}\n\n")

                # Token usage
                if llm_response.usage_metadata:
                    usage = llm_response.usage_metadata
                    f.write(f"**Token Usage:**\n")
                    f.write(f"- Prompt tokens: {usage.prompt_token_count}\n")
                    f.write(f"- Response tokens: {usage.candidates_token_count}\n")
                    f.write(f"- Total tokens: {usage.total_token_count}\n\n")

                f.write("## Response\n\n")
                f.write(response_text)

            # Add to generation notes
            self.generation_notes.append({
                "attempt": self.attempt_count,
                "timestamp": timestamp,
                "token_count": llm_response.usage_metadata.total_token_count if llm_response.usage_metadata else 0,
                "response_length": len(response_text),
            })

            self.attempt_count += 1

        return None  # Don't modify response

    async def on_event_callback(
        self,
        *,
        invocation_context: InvocationContext,
        event: Event,
    ) -> Optional[Event]:
        """Track events for generation notes."""

        # Extract validation results from events
        if event.author and "PVMAP" in event.author:
            for part in event.content.parts:
                if part.text:
                    # Check for validation events
                    if "validation" in part.text.lower():
                        self.generation_notes.append({
                            "event": "validation",
                            "timestamp": datetime.now().isoformat(),
                            "content": part.text[:200]  # First 200 chars
                        })

                    # Check for error feedback
                    if "error" in part.text.lower() or "retry" in part.text.lower():
                        self.generation_notes.append({
                            "event": "error_feedback",
                            "timestamp": datetime.now().isoformat(),
                            "content": part.text[:200]
                        })

        return None

    async def on_invocation_end_callback(
        self, *, invocation_context: InvocationContext
    ) -> None:
        """Save generation notes at the end of invocation."""

        notes_file = self.dataset_dir / "generation_notes.md"

        with open(notes_file, 'w') as f:
            f.write(f"# PVMAP Generation Notes: {self.dataset_name}\n\n")
            f.write(f"**Generated:** {datetime.now().isoformat()}\n")
            f.write(f"**Invocation ID:** {invocation_context.invocation_id}\n")
            f.write(f"**Session ID:** {invocation_context.session.id}\n\n")

            # Final state
            state = invocation_context.session.state
            f.write("## Final State\n\n")
            f.write(f"- Generation success: {state.get('generation_success', False)}\n")
            f.write(f"- Attempts made: {self.attempt_count}\n")
            f.write(f"- Validation passed: {state.get('validation_results', {}).get('valid', False)}\n")

            if state.get('error'):
                f.write(f"- Final error: {state['error']}\n")

            f.write("\n## Execution Timeline\n\n")
            for note in self.generation_notes:
                # Build event title
                if 'event' in note:
                    event_title = note['event']
                else:
                    attempt_num = note.get('attempt', '?')
                    event_title = f"Attempt {attempt_num}"

                f.write(f"### {event_title} - {note['timestamp']}\n")
                if 'token_count' in note:
                    f.write(f"- Tokens: {note['token_count']}\n")
                if 'response_length' in note:
                    f.write(f"- Response length: {note['response_length']} chars\n")
                if 'content' in note:
                    f.write(f"- Content: {note['content']}\n")
                f.write("\n")

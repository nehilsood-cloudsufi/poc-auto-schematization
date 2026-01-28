"""
Custom Agent Example - Google ADK

This example demonstrates how to create a custom agent by inheriting
from BaseAgent and implementing custom orchestration logic.

Based on the StoryFlowAgent pattern from google_adk_python/llms-full.txt (Python sections).

This is an ADVANCED pattern - use LlmAgent for most cases.
"""

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.context import InvocationContext
from google.adk.events import Event
from google.adk import Runner
from typing import AsyncGenerator
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConditionalFlowAgent(BaseAgent):
    """
    Custom agent that orchestrates sub-agents with conditional logic.

    This agent:
    1. Runs a generator sub-agent
    2. Runs a validator sub-agent
    3. Conditionally re-runs the generator if validation fails
    """

    # Pydantic field declarations
    generator: LlmAgent
    validator: LlmAgent

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        name: str,
        generator: LlmAgent,
        validator: LlmAgent,
    ):
        """
        Initialize the custom agent.

        Args:
            name: Agent name
            generator: Agent that generates content
            validator: Agent that validates content
        """
        # Define sub_agents list for framework
        sub_agents_list = [generator, validator]

        # Initialize parent with all fields
        super().__init__(
            name=name,
            generator=generator,
            validator=validator,
            sub_agents=sub_agents_list,
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Custom orchestration logic with conditional flow.

        This implements:
        - Sequential execution of generator then validator
        - Conditional re-generation based on validation result
        """
        logger.info(f"[{self.name}] Starting custom workflow")

        # Step 1: Run generator
        logger.info(f"[{self.name}] Running generator...")
        async for event in self.generator.run_async(ctx):
            yield event

        # Check if content was generated
        if "generated_content" not in ctx.session.state:
            logger.error(f"[{self.name}] No content generated, aborting")
            return

        logger.info(f"[{self.name}] Content: {ctx.session.state.get('generated_content')}")

        # Step 2: Run validator
        logger.info(f"[{self.name}] Running validator...")
        async for event in self.validator.run_async(ctx):
            yield event

        # Step 3: Conditional logic based on validation
        validation_result = ctx.session.state.get("validation_result")
        logger.info(f"[{self.name}] Validation: {validation_result}")

        if validation_result == "invalid":
            logger.info(f"[{self.name}] Content invalid, regenerating...")
            # Re-run generator
            async for event in self.generator.run_async(ctx):
                yield event
        else:
            logger.info(f"[{self.name}] Content valid, workflow complete")

        logger.info(f"[{self.name}] Workflow finished")


def create_custom_agent_system():
    """Create a custom agent system with conditional logic."""

    # Create generator agent
    generator = LlmAgent(
        name="Generator",
        model="gemini-2.5-flash",
        instruction="""Generate a short product description (2-3 sentences) based on
        the topic in session state with key 'topic'. Write it to session state with key 'generated_content'.""",
        input_schema=None,
        output_key="generated_content",
    )

    # Create validator agent
    validator = LlmAgent(
        name="Validator",
        model="gemini-2.5-flash",
        instruction="""Validate the product description in session state with key 'generated_content'.
        Check if it's professional and appropriate. Output ONLY one word: 'valid' if good,
        'invalid' if it needs improvement.""",
        input_schema=None,
        output_key="validation_result",
    )

    # Create custom agent
    custom_agent = ConditionalFlowAgent(
        name="ConditionalFlow",
        generator=generator,
        validator=validator,
    )

    return custom_agent


def run_custom_agent_example():
    """Run the custom agent with sample input."""
    print("=" * 60)
    print("Custom Agent with Conditional Logic")
    print("=" * 60)

    # Create custom agent
    agent = create_custom_agent_system()
    print(f"Created custom agent: {agent.name}")
    print(f"Sub-agents: {[a.name for a in agent.sub_agents]}")

    # Initialize runner
    runner = Runner(root_agent=agent)

    # Set initial state
    initial_state = {"topic": "wireless headphones"}

    # Run agent
    print(f"\nTopic: {initial_state['topic']}")
    result = runner.run(
        user_message="Generate and validate a product description",
        session_state=initial_state
    )

    print(f"\nFinal result: {result}")


if __name__ == "__main__":
    # Make sure to set GEMINI_API_KEY in your .env file
    run_custom_agent_example()

    print("\n" + "=" * 60)
    print("NOTE: This is an ADVANCED pattern.")
    print("For most use cases, use LlmAgent or workflow agents.")
    print("=" * 60)
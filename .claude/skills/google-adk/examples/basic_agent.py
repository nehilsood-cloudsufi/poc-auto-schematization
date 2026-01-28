"""
Basic Agent Example - Google ADK

This example demonstrates how to create a simple ADK agent with
basic configuration and run it with the Runner.

Reference: google_adk_python/llms.txt
"""

from google.adk.agents import Agent
from google.adk import Runner


def create_basic_agent():
    """Create a basic agent with minimal configuration."""
    agent = Agent(
        name="greeting_agent",
        model="gemini-2.5-flash",  # Fast and efficient
        instruction="You are a friendly greeting agent. Keep responses brief and warm.",
        description="An agent that greets users warmly"
    )
    return agent


def run_agent_example():
    """Run the agent with a sample message."""
    # Create the agent
    agent = create_basic_agent()
    print(f"Created agent: {agent.name}")
    print(f"Model: {agent.model}")

    # Initialize runner
    runner = Runner(root_agent=agent)

    # Run with user message
    user_message = "Hello!"
    print(f"\nUser: {user_message}")

    result = runner.run(user_message=user_message)
    print(f"Agent: {result}")


if __name__ == "__main__":
    # Make sure to set GEMINI_API_KEY in your .env file
    run_agent_example()
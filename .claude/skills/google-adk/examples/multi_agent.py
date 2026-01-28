"""
Multi-Agent System Example - Google ADK

This example demonstrates how to create a multi-agent system with
a coordinator and specialized sub-agents.

Reference: google_adk_python/llms.txt - Multi-Agent Systems section
"""

from google.adk.agents import Agent, LlmAgent
from google.adk import Runner


def create_multi_agent_system():
    """Create a multi-agent system with coordinator and sub-agents."""

    # Create specialized sub-agents
    greeter = Agent(
        name="Greeter",
        model="gemini-2.5-flash",
        instruction="You greet users warmly and briefly. Be friendly and welcoming.",
        description="Handles user greetings"
    )

    helper = Agent(
        name="Helper",
        model="gemini-2.5-flash",
        instruction="You answer general questions helpfully and concisely.",
        description="Answers general questions"
    )

    task_executor = Agent(
        name="TaskExecutor",
        model="gemini-2.5-flash",
        instruction="You help users complete specific tasks. Be action-oriented.",
        description="Executes user tasks"
    )

    # Create coordinator agent with sub-agents
    coordinator = LlmAgent(
        name="Coordinator",
        model="gemini-2.5-flash",
        instruction="You are a coordinator. Route user requests to the appropriate sub-agent based on the request type.",
        description="Main coordinator that routes requests",
        sub_agents=[greeter, helper, task_executor]
    )

    return coordinator


def run_multi_agent_example():
    """Run the multi-agent system with various messages."""

    # Create the multi-agent system
    coordinator = create_multi_agent_system()
    print("Multi-Agent System Created:")
    print(f"  Coordinator: {coordinator.name}")
    print(f"  Sub-agents: {[agent.name for agent in coordinator.sub_agents]}")

    # Initialize runner with coordinator as root
    runner = Runner(root_agent=coordinator)

    # Test with different message types
    test_messages = [
        "Hi there!",
        "What is the capital of France?",
        "Can you help me schedule a meeting?"
    ]

    for message in test_messages:
        print(f"\n{'=' * 60}")
        print(f"User: {message}")
        result = runner.run(user_message=message)
        print(f"System: {result}")


if __name__ == "__main__":
    # Make sure to set GEMINI_API_KEY in your .env file
    run_multi_agent_example()
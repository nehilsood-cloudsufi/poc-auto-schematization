"""
Function Calling (Tools) Example - Google ADK

This example demonstrates how to equip agents with custom tools
(Python functions) that the agent can call automatically.

Reference: test_google_adk/test_adk_agents.py
"""

from google.adk.agents import Agent
from google.adk import Runner
from datetime import datetime


# Define custom tool functions
def get_time() -> str:
    """Get the current time in HH:MM:SS format."""
    return datetime.now().strftime("%H:%M:%S")


def get_date() -> str:
    """Get the current date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")


def add_numbers(a: int, b: int) -> int:
    """Add two numbers and return the sum."""
    return a + b


def multiply_numbers(a: int, b: int) -> int:
    """Multiply two numbers and return the product."""
    return a * b


def calculate_area(length: float, width: float) -> float:
    """Calculate the area of a rectangle given length and width."""
    return length * width


def create_agent_with_single_tool():
    """Create an agent with a single custom tool."""
    agent = Agent(
        name="time_agent",
        model="gemini-2.5-flash",
        instruction="You help users with time-related queries. Use the get_time tool when needed.",
        tools=[get_time]
    )
    return agent


def create_agent_with_multiple_tools():
    """Create an agent with multiple custom tools."""
    agent = Agent(
        name="math_agent",
        model="gemini-2.5-flash",
        instruction="You help with math calculations. Use the appropriate tool for each operation.",
        tools=[add_numbers, multiply_numbers, calculate_area]
    )
    return agent


def create_agent_with_datetime_tools():
    """Create an agent with date and time tools."""
    agent = Agent(
        name="datetime_agent",
        model="gemini-2.5-flash",
        instruction="You help users with date and time queries. Use the appropriate tools.",
        tools=[get_time, get_date]
    )
    return agent


def run_single_tool_example():
    """Run example with single tool."""
    print("=" * 60)
    print("Example 1: Agent with Single Tool")
    print("=" * 60)

    agent = create_agent_with_single_tool()
    runner = Runner(root_agent=agent)

    message = "What time is it?"
    print(f"\nUser: {message}")
    result = runner.run(user_message=message)
    print(f"Agent: {result}")


def run_multiple_tools_example():
    """Run example with multiple tools."""
    print("\n" + "=" * 60)
    print("Example 2: Agent with Multiple Tools")
    print("=" * 60)

    agent = create_agent_with_multiple_tools()
    runner = Runner(root_agent=agent)

    test_messages = [
        "What is 15 plus 27?",
        "Calculate 8 times 9",
        "What's the area of a rectangle with length 5 and width 3?"
    ]

    for message in test_messages:
        print(f"\nUser: {message}")
        result = runner.run(user_message=message)
        print(f"Agent: {result}")


def run_datetime_tools_example():
    """Run example with datetime tools."""
    print("\n" + "=" * 60)
    print("Example 3: Agent with DateTime Tools")
    print("=" * 60)

    agent = create_agent_with_datetime_tools()
    runner = Runner(root_agent=agent)

    test_messages = [
        "What's the current time?",
        "What's today's date?",
        "Tell me both the date and time"
    ]

    for message in test_messages:
        print(f"\nUser: {message}")
        result = runner.run(user_message=message)
        print(f"Agent: {result}")


if __name__ == "__main__":
    # Make sure to set GEMINI_API_KEY in your .env file

    run_single_tool_example()
    run_multiple_tools_example()
    run_datetime_tools_example()

    print("\n" + "=" * 60)
    print("All function calling examples completed!")
    print("=" * 60)
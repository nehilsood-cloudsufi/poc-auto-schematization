"""
Workflow Agents Example - Google ADK

This example demonstrates Sequential, Parallel, and Loop workflow agents
for orchestrating multiple agents in different patterns.

Reference: google_adk_python/llms.txt - Workflow Agents section
"""

from google.adk.agents import (
    LlmAgent,
    SequentialAgent,
    ParallelAgent,
    LoopAgent
)
from google.adk import Runner


def create_sequential_workflow():
    """
    Create a sequential workflow where agents run one after another.
    Output of each agent flows to the next.
    """
    # Create sub-agents
    planner = LlmAgent(
        name="Planner",
        model="gemini-2.5-flash",
        instruction="Create a brief plan (2 steps) for the given task. Store in 'plan'.",
        output_key="plan"
    )

    executor = LlmAgent(
        name="Executor",
        model="gemini-2.5-flash",
        instruction="Execute the plan from state key 'plan'. Store results in 'execution_result'.",
        output_key="execution_result"
    )

    reviewer = LlmAgent(
        name="Reviewer",
        model="gemini-2.5-flash",
        instruction="Review the execution result from 'execution_result'. Provide brief feedback.",
        output_key="review"
    )

    # Create sequential agent
    sequential = SequentialAgent(
        name="SequentialPipeline",
        sub_agents=[planner, executor, reviewer]
    )

    return sequential


def create_parallel_workflow():
    """
    Create a parallel workflow where agents run simultaneously.
    Useful for independent tasks that don't depend on each other.
    """
    # Create independent analysis agents
    sentiment_analyzer = LlmAgent(
        name="SentimentAnalyzer",
        model="gemini-2.5-flash",
        instruction="Analyze sentiment of the input. Output: positive/negative/neutral.",
        output_key="sentiment"
    )

    keyword_extractor = LlmAgent(
        name="KeywordExtractor",
        model="gemini-2.5-flash",
        instruction="Extract 3 main keywords from the input.",
        output_key="keywords"
    )

    length_analyzer = LlmAgent(
        name="LengthAnalyzer",
        model="gemini-2.5-flash",
        instruction="Analyze text length and complexity.",
        output_key="length_analysis"
    )

    # Create parallel agent
    parallel = ParallelAgent(
        name="ParallelAnalysis",
        sub_agents=[sentiment_analyzer, keyword_extractor, length_analyzer]
    )

    return parallel


def create_loop_workflow():
    """
    Create a loop workflow where agents iterate multiple times.
    Useful for iterative refinement tasks.
    """
    # Create iterative agents
    writer = LlmAgent(
        name="Writer",
        model="gemini-2.5-flash",
        instruction="Write or improve content based on feedback. Read from 'feedback', write to 'content'.",
        output_key="content"
    )

    critic = LlmAgent(
        name="Critic",
        model="gemini-2.5-flash",
        instruction="Critique the content from 'content'. Provide brief feedback to 'feedback'.",
        output_key="feedback"
    )

    # Create loop agent (will iterate max 2 times)
    loop = LoopAgent(
        name="IterativeRefinement",
        sub_agents=[writer, critic],
        max_iterations=2
    )

    return loop


def run_sequential_example():
    """Run sequential workflow example."""
    print("=" * 60)
    print("Example 1: Sequential Workflow")
    print("Plan -> Execute -> Review")
    print("=" * 60)

    agent = create_sequential_workflow()
    runner = Runner(root_agent=agent)

    message = "Create a simple hello world program"
    print(f"\nUser: {message}")
    result = runner.run(user_message=message)
    print(f"Result: {result}")


def run_parallel_example():
    """Run parallel workflow example."""
    print("\n" + "=" * 60)
    print("Example 2: Parallel Workflow")
    print("Sentiment + Keywords + Length (simultaneous)")
    print("=" * 60)

    agent = create_parallel_workflow()
    runner = Runner(root_agent=agent)

    message = "The quick brown fox jumps over the lazy dog. This is a classic pangram."
    print(f"\nUser: {message}")
    result = runner.run(user_message=message)
    print(f"Result: {result}")


def run_loop_example():
    """Run loop workflow example."""
    print("\n" + "=" * 60)
    print("Example 3: Loop Workflow")
    print("Write -> Critique -> Improve (iterative)")
    print("=" * 60)

    agent = create_loop_workflow()
    runner = Runner(root_agent=agent)

    message = "Write a short welcome message for a website"
    print(f"\nUser: {message}")
    result = runner.run(user_message=message)
    print(f"Result: {result}")


def create_combined_workflow():
    """
    Create a complex workflow combining multiple patterns.

    Structure:
    - Sequential outer workflow
    - Contains a parallel analysis step
    - Followed by iterative refinement loop
    """
    # Parallel analysis
    parallel_analysis = create_parallel_workflow()

    # Loop refinement
    loop_refinement = create_loop_workflow()

    # Combine in sequential workflow
    combined = SequentialAgent(
        name="CombinedWorkflow",
        sub_agents=[parallel_analysis, loop_refinement]
    )

    return combined


def run_combined_example():
    """Run combined workflow example."""
    print("\n" + "=" * 60)
    print("Example 4: Combined Workflow")
    print("(Parallel Analysis) -> (Loop Refinement)")
    print("=" * 60)

    agent = create_combined_workflow()
    runner = Runner(root_agent=agent)

    message = "Analyze and improve: Our product is great and everyone loves it!"
    print(f"\nUser: {message}")
    result = runner.run(user_message=message)
    print(f"Result: {result}")


if __name__ == "__main__":
    # Make sure to set GEMINI_API_KEY in your .env file

    run_sequential_example()
    run_parallel_example()
    run_loop_example()
    run_combined_example()

    print("\n" + "=" * 60)
    print("All workflow examples completed!")
    print("=" * 60)

# Advanced Patterns in Google ADK

This reference guide covers advanced patterns for building sophisticated agents with Google Agent Development Kit (ADK). All examples are Python-only and extracted from the official ADK documentation.

**Reference:** `google_adk_python/llms-full.txt` lines 159-865

## Table of Contents

- [Custom Agents with BaseAgent](#custom-agents-with-baseagent)
- [StoryFlowAgent Pattern](#storyflowagent-pattern)
- [State-Based Communication](#state-based-communication)
- [Conditional Agent Orchestration](#conditional-agent-orchestration)
- [Structured Input/Output with Schemas](#structured-inputoutput-with-schemas)
- [Session Management](#session-management)
- [Event Escalation](#event-escalation)

---

## Custom Agents with BaseAgent

Custom agents provide ultimate flexibility by allowing you to define arbitrary orchestration logic. You inherit from `BaseAgent` and implement the `_run_async_impl` method.

**Reference:** llms-full.txt lines 159-193

### When to Use Custom Agents

Use custom agents when you need:
- **Conditional Logic**: Execute different sub-agents based on runtime conditions
- **Complex State Management**: Intricate logic for maintaining state throughout workflow
- **External Integrations**: Direct calls to external APIs, databases, or custom libraries
- **Dynamic Agent Selection**: Choose which sub-agent(s) to run based on dynamic evaluation
- **Unique Workflow Patterns**: Orchestration that doesn't fit Sequential, Parallel, or Loop structures

### Core Implementation Pattern

```python
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from typing import AsyncGenerator
from typing_extensions import override

class CustomAgent(BaseAgent):
    """Custom agent with specialized orchestration logic."""

    # Declare sub-agents as class attributes with type hints (for Pydantic)
    sub_agent_1: LlmAgent
    sub_agent_2: LlmAgent

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, name: str, sub_agent_1: LlmAgent, sub_agent_2: LlmAgent):
        """Initialize the custom agent."""
        super().__init__(
            name=name,
            sub_agent_1=sub_agent_1,
            sub_agent_2=sub_agent_2,
            sub_agents=[sub_agent_1, sub_agent_2]  # Register for framework
        )

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Implement custom orchestration logic."""

        # 1. Call first sub-agent
        async for event in self.sub_agent_1.run_async(ctx):
            yield event

        # 2. Read state to make decisions
        result = ctx.session.state.get("some_key")

        # 3. Conditional logic
        if result == "specific_value":
            # Call second sub-agent conditionally
            async for event in self.sub_agent_2.run_async(ctx):
                yield event
        else:
            # Different behavior
            pass
```

**Key Points:**
- `_run_async_impl` must be an `async def` function returning `AsyncGenerator[Event, None]`
- Use `async for event in agent.run_async(ctx): yield event` to call sub-agents
- Access session state via `ctx.session.state`
- Sub-agents must be registered in `sub_agents` list for framework features

---

## StoryFlowAgent Pattern

A complete example of a custom agent that orchestrates a multi-stage content generation workflow with conditional logic.

**Reference:** llms-full.txt lines 282-865

### Pattern Overview

The StoryFlowAgent demonstrates:
1. **Sequential stages**: Story generation → Critique/Revision loop → Grammar/Tone checks
2. **Iterative refinement**: LoopAgent for critic-reviser cycle
3. **Conditional regeneration**: If tone is negative, regenerate story
4. **State-based communication**: All agents communicate via `ctx.session.state`

### Architecture

```
StoryFlowAgent (Custom)
├── story_generator (LlmAgent) - Initial story generation
├── loop_agent (LoopAgent)
│   ├── critic (LlmAgent) - Provide critique
│   └── reviser (LlmAgent) - Revise based on critique
└── sequential_agent (SequentialAgent)
    ├── grammar_check (LlmAgent) - Check grammar
    └── tone_check (LlmAgent) - Analyze tone
```

### Implementation

**Step 1: Define Sub-Agents**

```python
from google.adk.agents import LlmAgent

GEMINI_2_FLASH = "gemini-2.5-flash"

# Story generator
story_generator = LlmAgent(
    name="StoryGenerator",
    model=GEMINI_2_FLASH,
    instruction="""You are a story writer. Write a short story (around 100 words) about a cat,
based on the topic provided in session state with key 'topic'""",
    output_key="current_story"  # Saves to state['current_story']
)

# Critic agent
critic = LlmAgent(
    name="Critic",
    model=GEMINI_2_FLASH,
    instruction="""You are a story critic. Review the story provided in
session state with key 'current_story'. Provide 1-2 sentences of constructive criticism
on how to improve it. Focus on plot or character.""",
    output_key="criticism"
)

# Reviser agent
reviser = LlmAgent(
    name="Reviser",
    model=GEMINI_2_FLASH,
    instruction="""You are a story reviser. Revise the story provided in
session state with key 'current_story', based on the criticism in
session state with key 'criticism'. Output only the revised story.""",
    output_key="current_story"  # Overwrites the original story
)

# Grammar checker
grammar_check = LlmAgent(
    name="GrammarCheck",
    model=GEMINI_2_FLASH,
    instruction="""You are a grammar checker. Check the grammar of the story
provided in session state with key 'current_story'. Output only the suggested
corrections as a list, or output 'Grammar is good!' if there are no errors.""",
    output_key="grammar_suggestions"
)

# Tone analyzer
tone_check = LlmAgent(
    name="ToneCheck",
    model=GEMINI_2_FLASH,
    instruction="""You are a tone analyzer. Analyze the tone of the story
provided in session state with key 'current_story'. Output only one word: 'positive' if
the tone is generally positive, 'negative' if the tone is generally negative, or 'neutral'
otherwise.""",
    output_key="tone_check_result"  # This determines conditional flow
)
```

**Step 2: Create Custom Orchestrator**

```python
from google.adk.agents import BaseAgent, LoopAgent, SequentialAgent
import logging

logger = logging.getLogger(__name__)

class StoryFlowAgent(BaseAgent):
    """
    Custom agent for story generation and refinement workflow.

    Orchestrates a sequence of LLM agents to generate a story,
    critique it, revise it, check grammar and tone, and potentially
    regenerate the story if the tone is negative.
    """

    # Field declarations for Pydantic
    story_generator: LlmAgent
    critic: LlmAgent
    reviser: LlmAgent
    grammar_check: LlmAgent
    tone_check: LlmAgent
    loop_agent: LoopAgent
    sequential_agent: SequentialAgent

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        name: str,
        story_generator: LlmAgent,
        critic: LlmAgent,
        reviser: LlmAgent,
        grammar_check: LlmAgent,
        tone_check: LlmAgent,
    ):
        """Initialize the StoryFlowAgent."""
        # Create internal workflow agents *before* calling super().__init__
        loop_agent = LoopAgent(
            name="CriticReviserLoop",
            sub_agents=[critic, reviser],
            max_iterations=2
        )

        sequential_agent = SequentialAgent(
            name="PostProcessing",
            sub_agents=[grammar_check, tone_check]
        )

        # Define sub_agents list for framework
        sub_agents_list = [
            story_generator,
            loop_agent,
            sequential_agent,
        ]

        # Call super().__init__ with all agents
        super().__init__(
            name=name,
            story_generator=story_generator,
            critic=critic,
            reviser=reviser,
            grammar_check=grammar_check,
            tone_check=tone_check,
            loop_agent=loop_agent,
            sequential_agent=sequential_agent,
            sub_agents=sub_agents_list
        )

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Implements the custom orchestration logic."""
        logger.info(f"[{self.name}] Starting story generation workflow.")

        # 1. Initial Story Generation
        logger.info(f"[{self.name}] Running StoryGenerator...")
        async for event in self.story_generator.run_async(ctx):
            yield event

        # Check if story was generated
        if "current_story" not in ctx.session.state:
            logger.error(f"[{self.name}] Failed to generate initial story.")
            return

        logger.info(f"[{self.name}] Story: {ctx.session.state.get('current_story')}")

        # 2. Critic-Reviser Loop
        logger.info(f"[{self.name}] Running CriticReviserLoop...")
        async for event in self.loop_agent.run_async(ctx):
            yield event

        logger.info(f"[{self.name}] Story after loop: {ctx.session.state.get('current_story')}")

        # 3. Sequential Post-Processing (Grammar and Tone Check)
        logger.info(f"[{self.name}] Running PostProcessing...")
        async for event in self.sequential_agent.run_async(ctx):
            yield event

        # 4. Conditional Logic Based on Tone
        tone_check_result = ctx.session.state.get("tone_check_result")
        logger.info(f"[{self.name}] Tone check result: {tone_check_result}")

        if tone_check_result == "negative":
            logger.info(f"[{self.name}] Tone is negative. Regenerating story...")
            async for event in self.story_generator.run_async(ctx):
                yield event
        else:
            logger.info(f"[{self.name}] Tone is not negative. Keeping current story.")

        logger.info(f"[{self.name}] Workflow finished.")
```

**Step 3: Instantiate and Run**

```python
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Create the custom agent instance
story_flow_agent = StoryFlowAgent(
    name="StoryFlowAgent",
    story_generator=story_generator,
    critic=critic,
    reviser=reviser,
    grammar_check=grammar_check,
    tone_check=tone_check,
)

# Setup session with initial state
INITIAL_STATE = {"topic": "a brave kitten exploring a haunted house"}

async def setup_session_and_runner():
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="story_app",
        user_id="12345",
        session_id="123344",
        state=INITIAL_STATE
    )

    runner = Runner(
        agent=story_flow_agent,
        app_name="story_app",
        session_service=session_service
    )

    return session_service, runner

# Run the agent
async def call_agent_async(user_input_topic: str):
    session_service, runner = await setup_session_and_runner()

    content = types.Content(
        role='user',
        parts=[types.Part(text=f"Generate a story about: {user_input_topic}")]
    )

    events = runner.run_async(
        user_id="12345",
        session_id="123344",
        new_message=content
    )

    async for event in events:
        if event.is_final_response():
            print(f"Final response: {event.content.parts[0].text}")
```

**Key Takeaways:**
- Custom agents can combine multiple workflow patterns (LoopAgent + SequentialAgent)
- State-based communication allows agents to read/write shared data
- Conditional logic enables dynamic workflow adjustments
- All agents work on the same `InvocationContext`

---

## State-Based Communication

Agents communicate by reading from and writing to `ctx.session.state`.

**Reference:** llms-full.txt lines 2119-2145

### Reading from State

```python
# In custom agent _run_async_impl or LlmAgent instruction
previous_result = ctx.session.state.get("some_key")
previous_result_with_default = ctx.session.state.get("some_key", "default_value")

# Check if key exists
if "some_key" in ctx.session.state:
    # Use the value
    value = ctx.session.state["some_key"]
```

### Writing to State

**Option 1: Using `output_key` (Recommended for LlmAgent)**

```python
agent = LlmAgent(
    name="DataProcessor",
    instruction="Process the data and output the result.",
    output_key="processed_data"  # Final response saved to state['processed_data']
)
```

**Option 2: Direct State Manipulation (in custom agents)**

```python
# In custom agent _run_async_impl
ctx.session.state["my_custom_result"] = "calculated_value"
```

### State Templates in Instructions

You can reference state variables directly in LlmAgent instructions using template syntax:

```python
agent = LlmAgent(
    name="AgentB",
    instruction="""
    You are an assistant. Use the data from the previous step.

    Data from state: {data_key}
    Optional data: {optional_key?}
    Artifact content: {artifact.my_artifact}

    Process this data and provide insights.
    """,
    output_key="insights"
)
```

**Template Syntax:**
- `{var}`: Insert value of state variable `var` (raises error if not found)
- `{var?}`: Insert value of `var`, ignore if not found
- `{artifact.var}`: Insert text content of artifact named `var`

### Example: Sequential Pipeline with State

```python
from google.adk.agents import SequentialAgent, LlmAgent

agent_A = LlmAgent(
    name="AgentA",
    instruction="Find the capital of France.",
    output_key="capital_city"  # Saves "Paris" to state['capital_city']
)

agent_B = LlmAgent(
    name="AgentB",
    instruction="Tell me about the city stored in state key 'capital_city'.",
    # Can also use template: "Tell me about {capital_city}"
)

pipeline = SequentialAgent(
    name="CityInfo",
    sub_agents=[agent_A, agent_B]
)

# When pipeline runs:
# 1. AgentA runs, saves "Paris" to state['capital_city']
# 2. AgentB runs, reads state['capital_city'] to get "Paris"
```

---

## Conditional Agent Orchestration

Use custom agents to implement if/else logic and dynamic agent selection.

**Reference:** llms-full.txt lines 360-404

### Pattern: Conditional Sub-Agent Execution

```python
class ConditionalAgent(BaseAgent):
    agent_option_a: LlmAgent
    agent_option_b: LlmAgent

    model_config = {"arbitrary_types_allowed": True}

    def __init__(self, name: str, agent_a: LlmAgent, agent_b: LlmAgent):
        super().__init__(
            name=name,
            agent_option_a=agent_a,
            agent_option_b=agent_b,
            sub_agents=[agent_a, agent_b]
        )

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # Read condition from state
        condition = ctx.session.state.get("condition", "default")

        if condition == "option_a":
            async for event in self.agent_option_a.run_async(ctx):
                yield event
        elif condition == "option_b":
            async for event in self.agent_option_b.run_async(ctx):
                yield event
        else:
            # Default behavior
            pass
```

### Pattern: Error Handling with Fallback

```python
class RobustAgent(BaseAgent):
    primary_agent: LlmAgent
    fallback_agent: LlmAgent

    model_config = {"arbitrary_types_allowed": True}

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        try:
            # Try primary agent
            async for event in self.primary_agent.run_async(ctx):
                yield event

            # Check if successful
            if not ctx.session.state.get("success"):
                raise ValueError("Primary agent failed")

        except Exception as e:
            logger.warning(f"Primary agent failed: {e}. Using fallback.")
            # Use fallback agent
            async for event in self.fallback_agent.run_async(ctx):
                yield event
```

---

## Structured Input/Output with Schemas

Define expected input and output formats using Pydantic BaseModel.

**Reference:** llms-full.txt lines 1098-1135

### Input Schema

```python
from pydantic import BaseModel, Field

class CountryInput(BaseModel):
    country: str = Field(description="The country to get information about.")

agent = LlmAgent(
    name="CapitalFinder",
    model="gemini-2.5-flash",
    instruction="Extract the country name and find its capital.",
    input_schema=CountryInput,  # User message must be JSON matching this schema
    output_key="capital"
)

# Usage: user_message must be '{"country": "France"}'
```

### Output Schema

```python
class CapitalOutput(BaseModel):
    capital: str = Field(description="The capital of the country.")
    population_estimate: str = Field(description="Estimated population.")

structured_agent = LlmAgent(
    name="StructuredCapitalAgent",
    model="gemini-2.5-flash",
    instruction="""Respond ONLY with JSON: {"capital": "city_name", "population_estimate": "estimate"}""",
    output_schema=CapitalOutput,  # Enforces JSON output matching schema
    output_key="capital_info"
)

# Note: Using output_schema DISABLES tool use and agent transfer
```

### Complete Example

```python
class UserQuery(BaseModel):
    question: str = Field(description="The user's question.")

class AnswerFormat(BaseModel):
    answer: str = Field(description="The answer to the question.")
    confidence: str = Field(description="Confidence level: high, medium, low.")

structured_qa_agent = LlmAgent(
    name="StructuredQA",
    model="gemini-2.5-flash",
    instruction="""Answer the question in JSON format.
    {"answer": "your answer", "confidence": "high|medium|low"}
    """,
    input_schema=UserQuery,
    output_schema=AnswerFormat,
    output_key="structured_answer"
)
```

---

## Session Management

Manage conversation history and session state with InMemorySessionService.

**Reference:** llms-full.txt lines 506-552

### Creating Sessions with Initial State

```python
from google.adk.sessions import InMemorySessionService
from google.adk import Runner

APP_NAME = "my_app"
USER_ID = "user_123"
SESSION_ID = "session_456"

# Initial state
INITIAL_STATE = {
    "topic": "AI safety",
    "max_length": 500,
    "user_preferences": {"style": "formal"}
}

# Setup session service
session_service = InMemorySessionService()

# Create session with initial state
session = await session_service.create_session(
    app_name=APP_NAME,
    user_id=USER_ID,
    session_id=SESSION_ID,
    state=INITIAL_STATE
)

# Create runner
runner = Runner(
    agent=my_agent,
    app_name=APP_NAME,
    session_service=session_service
)
```

### Accessing and Modifying Session State

```python
# Get current session
current_session = await session_service.get_session(
    app_name=APP_NAME,
    user_id=USER_ID,
    session_id=SESSION_ID
)

# Read state
topic = current_session.state.get("topic")

# Update state
current_session.state["topic"] = "Machine Learning"

# Run agent with updated session
content = types.Content(role='user', parts=[types.Part(text="Generate content")])
events = runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

async for event in events:
    if event.is_final_response():
        print(event.content.parts[0].text)
```

### Advanced: Stateless Agents

Use `include_contents='none'` for agents that don't need conversation history:

```python
stateless_agent = LlmAgent(
    name="StatelessProcessor",
    model="gemini-2.5-flash",
    instruction="Process the input based only on current request.",
    include_contents='none'  # No prior conversation history
)
```

---

## Event Escalation

Use event escalation to terminate loops or signal completion.

**Reference:** llms-full.txt lines 2081-2113, 2620-2741

### Pattern: Loop Termination with Escalation

```python
from google.adk.events import Event, EventActions
from google.adk.agents import LoopAgent, LlmAgent, BaseAgent

class CheckCondition(BaseAgent):
    """Custom agent to check state and escalate if done."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        status = ctx.session.state.get("status", "pending")
        is_done = (status == "completed")

        # Escalate if condition is met
        yield Event(author=self.name, actions=EventActions(escalate=is_done))

process_step = LlmAgent(
    name="ProcessingStep",
    instruction="Process data and update state['status'] to 'completed' when done.",
    output_key="result"
)

# Loop will stop when CheckCondition escalates OR after max_iterations
poller = LoopAgent(
    name="StatusPoller",
    max_iterations=10,
    sub_agents=[process_step, CheckCondition(name="Checker")]
)
```

### Pattern: Exit Loop Tool

```python
from google.adk.tools.tool_context import ToolContext

def exit_loop(tool_context: ToolContext):
    """Call this function to exit the loop."""
    tool_context.actions.escalate = True
    return {}

refiner_agent = LlmAgent(
    name="RefinerAgent",
    instruction="""
    If the critique indicates completion, call the exit_loop function.
    Otherwise, refine the document.
    """,
    tools=[exit_loop],
    output_key="refined_output"
)
```

---

## Additional Resources

- [Basic Agent Examples](../examples/basic_agent.py) - Simple LlmAgent patterns
- [Multi-Agent Examples](../examples/multi_agent.py) - Coordinator patterns
- [Workflow Agents](../examples/workflow_agents.py) - Sequential, Parallel, Loop
- [Custom Agent Example](../examples/custom_agent.py) - BaseAgent implementation
- [Multi-Agent Patterns Reference](./multi_agent_patterns.md) - Design patterns
- [State Management Reference](./state_management.md) - Session state guide

## See Also

- [Model Selection Guide](./model_selection.md)
- [Main README](../README.md)
- [Google ADK Documentation](https://google.github.io/adk-docs/)

# State Management in Google ADK

Comprehensive guide to managing state and data flow between agents in Google ADK. All examples are Python-only.

**Reference:** `google_adk_python/llms-full.txt` lines 918-1336, 2119-2144

## Table of Contents

- [Overview](#overview)
- [Session State Basics](#session-state-basics)
- [Reading from State](#reading-from-state)
- [Writing to State](#writing-to-state)
- [State Templates in Instructions](#state-templates-in-instructions)
- [Output Key Pattern](#output-key-pattern)
- [State in Workflows](#state-in-workflows)
- [Best Practices](#best-practices)
- [Common Patterns](#common-patterns)

---

## Overview

State management is the mechanism by which agents share data and communicate within a multi-agent system. In Google ADK, agents operating within the same invocation share a common `Session` object that contains a mutable `state` dictionary.

### Why State Management Matters

- **Data Passing:** Transfer results between agents in a pipeline
- **Context Preservation:** Maintain information across agent transitions
- **Workflow Coordination:** Enable agents to make decisions based on previous results
- **Stateful Conversations:** Track user preferences and conversation history

### Key Concepts

- **Session:** A persistent context for a conversation or workflow
- **State Dictionary:** A key-value store accessible to all agents in a session
- **InvocationContext:** Runtime context providing access to session and state
- **Output Key:** Automatic state-saving mechanism for agent responses

---

## Session State Basics

Every agent invocation receives an `InvocationContext` object that provides access to the shared session state.

**Accessing State in Custom Agents:**

```python
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from typing import AsyncGenerator

class MyCustomAgent(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # Access the session state dictionary
        state = ctx.session.state

        # Read a value
        user_name = state.get("user_name", "Guest")

        # Write a value
        state["processed"] = True

        # Yield events...
        yield Event(author=self.name, content="Processing complete")
```

**State Structure:**

- **Type:** Python dictionary (`dict`)
- **Scope:** Shared across all agents in the same invocation
- **Lifetime:** Persists for the duration of the session
- **Mutability:** Can be read and modified by any agent

**Reference:** llms-full.txt lines 2119-2127

---

## Reading from State

Agents can read values from the session state to access data set by previous agents or initial session configuration.

### Reading in Custom Agents

```python
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from typing import AsyncGenerator

class DataProcessor(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # Safe read with default value
        input_data = ctx.session.state.get("input_data", None)

        if input_data is None:
            yield Event(
                author=self.name,
                content="Error: No input data found in state"
            )
            return

        # Process the data
        result = self.process(input_data)

        # Store result for next agent
        ctx.session.state["processed_result"] = result

        yield Event(author=self.name, content=f"Processed: {result}")

    def process(self, data):
        return data.upper()  # Example processing
```

### Reading in LLM Agent Instructions

LLM agents can reference state variables directly in their instructions using template syntax.

```python
from google.adk.agents import LlmAgent

agent = LlmAgent(
    name="Analyzer",
    model="gemini-2.5-flash",
    instruction="""Analyze the data from the previous step.

    The data to analyze is: {input_data}

    Provide a detailed analysis."""
)

# When the agent runs:
# - ADK automatically replaces {input_data} with ctx.session.state['input_data']
# - If the state key doesn't exist, it raises an error
# - Use {input_data?} to ignore missing keys (optional syntax)
```

**Reference:** llms-full.txt lines 994-1000

---

## Writing to State

Agents write to state to pass data to subsequent agents or store intermediate results.

### Writing in Custom Agents

```python
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from typing import AsyncGenerator

class DataFetcher(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # Fetch data (example)
        data = {"temperature": 72, "humidity": 65}

        # Write to state
        ctx.session.state["weather_data"] = data

        # Can also write multiple keys
        ctx.session.state["fetch_timestamp"] = "2024-01-15 10:30:00"
        ctx.session.state["fetch_status"] = "success"

        yield Event(author=self.name, content="Data fetched successfully")
```

### Writing via Output Key (Automatic)

The `output_key` parameter on `LlmAgent` provides automatic state management.

```python
from google.adk.agents import LlmAgent

agent = LlmAgent(
    name="Summarizer",
    model="gemini-2.5-flash",
    instruction="Summarize the provided text concisely.",
    output_key="summary"  # Agent's response text is saved to state['summary']
)

# When the agent completes:
# ctx.session.state['summary'] = agent_response_text
# Subsequent agents can access state['summary']
```

**How `output_key` Works:**

1. Agent generates a response (text or structured data)
2. ADK extracts the text content from the final response
3. ADK automatically writes: `state[output_key] = response_text`
4. Next agents in the workflow can read this state key

**Reference:** llms-full.txt lines 1107-1109, 2124

---

## State Templates in Instructions

LLM agents support powerful template syntax for accessing state values directly in instructions.

### Basic Template Syntax

**Standard Variable:** `{var}`
- Inserts the value of `state['var']`
- Raises error if key doesn't exist

**Artifact Content:** `{artifact.var}`
- Inserts the text content of artifact named `var`
- Used for accessing uploaded files or generated artifacts

**Optional Variable:** `{var?}`
- Inserts the value of `state['var']` if it exists
- Silently ignores missing keys (no error)

### Examples

```python
from google.adk.agents import LlmAgent

# Example 1: Required state variable
agent1 = LlmAgent(
    name="Greeter",
    model="gemini-2.5-flash",
    instruction="""Greet the user by name.

    User name: {user_name}

    Provide a warm, personalized greeting."""
)
# Requires state['user_name'] to exist, otherwise raises error

# Example 2: Optional state variable
agent2 = LlmAgent(
    name="FlexibleGreeter",
    model="gemini-2.5-flash",
    instruction="""Greet the user.

    User name (if known): {user_name?}

    If name is provided, use it. Otherwise, use a generic greeting."""
)
# Works whether state['user_name'] exists or not

# Example 3: Multiple state variables
agent3 = LlmAgent(
    name="Reporter",
    model="gemini-2.5-flash",
    instruction="""Generate a report based on the following data:

    Temperature: {temperature}
    Humidity: {humidity}
    Wind Speed: {wind_speed?}

    Provide a weather summary."""
)
# Requires temperature and humidity, wind_speed is optional
```

**Reference:** llms-full.txt lines 994-1000

---

## Output Key Pattern

The `output_key` parameter is the recommended way to pass data between agents in workflows.

### Sequential Pipeline with Output Keys

```python
from google.adk.agents import SequentialAgent, LlmAgent

# Step 1: Fetch data
fetcher = LlmAgent(
    name="DataFetcher",
    model="gemini-2.5-flash",
    instruction="Fetch the latest sales data for Q4.",
    output_key="sales_data"  # Saves to state['sales_data']
)

# Step 2: Analyze data
analyzer = LlmAgent(
    name="DataAnalyzer",
    model="gemini-2.5-flash",
    instruction="""Analyze the sales data:

    {sales_data}

    Identify key trends and insights.""",
    output_key="analysis"  # Saves to state['analysis']
)

# Step 3: Generate report
reporter = LlmAgent(
    name="ReportGenerator",
    model="gemini-2.5-flash",
    instruction="""Generate a executive summary report:

    Analysis: {analysis}

    Format as a professional report.""",
    output_key="final_report"  # Saves to state['final_report']
)

# Create pipeline
pipeline = SequentialAgent(
    name="SalesReportPipeline",
    sub_agents=[fetcher, analyzer, reporter]
)

# Data flows automatically:
# fetcher -> state['sales_data']
# analyzer reads state['sales_data'] -> state['analysis']
# reporter reads state['analysis'] -> state['final_report']
```

**Reference:** llms-full.txt lines 2131-2140

---

## State in Workflows

Different workflow agents handle state in specific ways.

### SequentialAgent

**Behavior:**
- Passes the **same** `InvocationContext` to each sub-agent in order
- State modifications persist across agents
- Ideal for data pipelines

**Example:**

```python
from google.adk.agents import SequentialAgent, LlmAgent

validator = LlmAgent(
    name="Validator",
    model="gemini-2.5-flash",
    instruction="Validate the input. Set status to 'valid' or 'invalid'.",
    output_key="validation_status"
)

processor = LlmAgent(
    name="Processor",
    model="gemini-2.5-flash",
    instruction="If {validation_status} is 'valid', process the data.",
    output_key="result"
)

pipeline = SequentialAgent(name="Pipeline", sub_agents=[validator, processor])

# State flows sequentially:
# 1. validator runs -> state['validation_status'] = 'valid'
# 2. processor runs -> reads state['validation_status']
```

**Reference:** llms-full.txt lines 2039-2057

### ParallelAgent

**Behavior:**
- All sub-agents access the **same shared** `session.state`
- Agents run concurrently
- Use **distinct state keys** to avoid race conditions

**Example:**

```python
from google.adk.agents import ParallelAgent, LlmAgent

fetch_weather = LlmAgent(
    name="WeatherFetcher",
    model="gemini-2.5-flash",
    instruction="Fetch current weather.",
    output_key="weather"  # Writes to state['weather']
)

fetch_news = LlmAgent(
    name="NewsFetcher",
    model="gemini-2.5-flash",
    instruction="Fetch latest news headlines.",
    output_key="news"  # Writes to state['news']
)

parallel = ParallelAgent(name="Gatherer", sub_agents=[fetch_weather, fetch_news])

# Both agents run concurrently
# Use different keys: state['weather'] and state['news']
# Avoid using the same key to prevent race conditions
```

**Warning:** If multiple parallel agents write to the same state key, the final value is non-deterministic.

**Reference:** llms-full.txt lines 2059-2079

### LoopAgent

**Behavior:**
- Passes the **same** `InvocationContext` in each iteration
- State changes persist across loop iterations
- Useful for iterative refinement

**Example:**

```python
from google.adk.agents import LoopAgent, LlmAgent, BaseAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext
from typing import AsyncGenerator

# Refine the code
refiner = LlmAgent(
    name="CodeRefiner",
    model="gemini-2.5-flash",
    instruction="""Improve the code in {current_code?}.

    If no code exists yet, generate initial code based on {requirements}.

    Focus on quality and readability.""",
    output_key="current_code"  # Overwrites state['current_code'] each iteration
)

# Check quality
checker = LlmAgent(
    name="QualityChecker",
    model="gemini-2.5-flash",
    instruction="""Evaluate {current_code} against {requirements}.

    Output 'pass' or 'fail'.""",
    output_key="quality_status"
)

# Stop if quality check passes
class StopChecker(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        status = ctx.session.state.get("quality_status", "fail")
        should_stop = (status == "pass")
        yield Event(author=self.name, actions=EventActions(escalate=should_stop))

loop = LoopAgent(
    name="RefinementLoop",
    max_iterations=5,
    sub_agents=[refiner, checker, StopChecker(name="Stop")]
)

# State evolution across iterations:
# Iteration 1: refiner -> state['current_code'] = v1, checker -> state['quality_status'] = 'fail'
# Iteration 2: refiner reads state['current_code'] -> improves to v2, checker -> 'fail'
# Iteration 3: refiner -> v3, checker -> 'pass', StopChecker escalates (loop ends)
```

**Reference:** llms-full.txt lines 2081-2113

---

## Best Practices

### 1. Use Descriptive State Keys

```python
# Good
state["user_preferences"] = {...}
state["validation_result"] = "valid"
state["processed_data"] = [...]

# Bad
state["data"] = {...}  # Too generic
state["x"] = "valid"   # Not descriptive
state["temp"] = [...]  # Ambiguous
```

### 2. Document State Contract

Document what state keys each agent expects and produces.

```python
from google.adk.agents import LlmAgent

agent = LlmAgent(
    name="DataProcessor",
    model="gemini-2.5-flash",
    instruction="""Process the input data.

    Expects state keys:
    - raw_data: The unprocessed data

    Produces state keys:
    - processed_data: The cleaned and validated data
    - error_count: Number of errors encountered
    """,
    output_key="processed_data"
)
```

### 3. Handle Missing State Gracefully

```python
# In custom agents
async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
    # Use .get() with default values
    data = ctx.session.state.get("input_data", None)

    if data is None:
        yield Event(author=self.name, content="Error: No input data")
        return

    # Process data...

# In LLM agent instructions - use optional syntax
instruction = """Process the data.

Input: {data?}

If no data is provided, ask the user for input."""
```

### 4. Avoid State Key Collisions in Parallel Workflows

```python
from google.adk.agents import ParallelAgent, LlmAgent

# Good: Unique keys
agent1 = LlmAgent(..., output_key="source1_data")
agent2 = LlmAgent(..., output_key="source2_data")

parallel = ParallelAgent(name="Parallel", sub_agents=[agent1, agent2])

# Bad: Same key (race condition)
agent1 = LlmAgent(..., output_key="data")
agent2 = LlmAgent(..., output_key="data")  # Overwrites agent1's result!
```

### 5. Initialize State Before Workflows

```python
from google.adk import Runner
from google.adk.sessions import InMemorySessionService

# Create session with initial state
session_service = InMemorySessionService()
session = session_service.create_session(
    app_name="my_app",
    user_id="user123",
    session_id="session456"
)

# Initialize state
session.state["user_name"] = "Alice"
session.state["preferences"] = {"theme": "dark"}
session.state["requirements"] = "Generate a Python function"

# Run agent with initialized state
runner = Runner(agent=my_agent, session_service=session_service)
result = runner.run(user_id="user123", session_id="session456", new_message="Start")
```

### 6. Use output_key for Simple Cases

```python
# Prefer output_key for automatic state management
agent = LlmAgent(
    name="Summarizer",
    model="gemini-2.5-flash",
    instruction="Summarize the text.",
    output_key="summary"  # Simple and clean
)

# Use manual state management only when needed
class CustomAgent(BaseAgent):
    async def _run_async_impl(self, ctx: InvocationContext):
        # Manual control when you need it
        ctx.session.state["key1"] = value1
        ctx.session.state["key2"] = value2
```

---

## Common Patterns

### Pattern 1: Sequential Data Pipeline

**Use Case:** Multi-stage data processing where each stage depends on the previous.

```python
from google.adk.agents import SequentialAgent, LlmAgent

extractor = LlmAgent(
    name="Extractor",
    model="gemini-2.5-flash",
    instruction="Extract key entities from the text.",
    output_key="entities"
)

classifier = LlmAgent(
    name="Classifier",
    model="gemini-2.5-flash",
    instruction="Classify the entities: {entities}",
    output_key="classifications"
)

summarizer = LlmAgent(
    name="Summarizer",
    model="gemini-2.5-flash",
    instruction="Summarize findings: {classifications}",
    output_key="summary"
)

pipeline = SequentialAgent(
    name="NLPPipeline",
    sub_agents=[extractor, classifier, summarizer]
)
```

### Pattern 2: Conditional Execution

**Use Case:** Execute different logic based on state values.

```python
from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from typing import AsyncGenerator

class ConditionalRouter(BaseAgent):
    def __init__(self):
        super().__init__(name="Router")
        self.path_a = LlmAgent(name="PathA", model="gemini-2.5-flash", instruction="Handle case A")
        self.path_b = LlmAgent(name="PathB", model="gemini-2.5-flash", instruction="Handle case B")

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        condition = ctx.session.state.get("condition", "default")

        if condition == "A":
            async for event in self.path_a.run_async(ctx):
                yield event
        else:
            async for event in self.path_b.run_async(ctx):
                yield event
```

### Pattern 3: Accumulating Results

**Use Case:** Collect results from multiple agents into a list.

```python
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from typing import AsyncGenerator

class ResultAccumulator(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # Initialize results list if needed
        if "results" not in ctx.session.state:
            ctx.session.state["results"] = []

        # Add current result
        current_result = self.compute_result()
        ctx.session.state["results"].append(current_result)

        # Check if done
        if len(ctx.session.state["results"]) >= 5:
            ctx.session.state["status"] = "complete"

        yield Event(author=self.name, content=f"Result {current_result} added")

    def compute_result(self):
        return "some_value"
```

### Pattern 4: State-Based Loop Termination

**Use Case:** Loop until a condition in state is met.

```python
from google.adk.agents import LoopAgent, LlmAgent, BaseAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext
from typing import AsyncGenerator

worker = LlmAgent(
    name="Worker",
    model="gemini-2.5-flash",
    instruction="Perform work. Set state['done'] = True when complete.",
)

class TerminationChecker(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        is_done = ctx.session.state.get("done", False)
        yield Event(
            author=self.name,
            actions=EventActions(escalate=is_done)
        )

loop = LoopAgent(
    name="WorkLoop",
    max_iterations=10,
    sub_agents=[worker, TerminationChecker(name="Checker")]
)
```

---

## Structured Input/Output with State

### Using Pydantic Schemas

Define structured data formats with Pydantic models.

```python
from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field

class UserInput(BaseModel):
    name: str = Field(description="User's name")
    age: int = Field(description="User's age")

class AnalysisOutput(BaseModel):
    category: str = Field(description="User category")
    recommendation: str = Field(description="Personalized recommendation")

analyzer = LlmAgent(
    name="UserAnalyzer",
    model="gemini-2.5-flash",
    instruction="""Analyze the user data and provide a category and recommendation.

    Output must be JSON matching the schema.""",
    input_schema=UserInput,   # Expects JSON input
    output_schema=AnalysisOutput,  # Produces JSON output
    output_key="analysis_result"
)

# Input: {"name": "Alice", "age": 30}
# Output saved to state['analysis_result']: {"category": "adult", "recommendation": "..."}
```

**Note:** Using `output_schema` disables tool usage for that agent.

**Reference:** llms-full.txt lines 1098-1135

---

## Session Management

### Creating Sessions with Initial State

```python
from google.adk import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Create session service
session_service = InMemorySessionService()

# Create session with initial state
session = session_service.create_session(
    app_name="my_app",
    user_id="user123",
    session_id="session_abc"
)

# Set initial state
session.state["user_preferences"] = {"language": "en"}
session.state["context"] = "customer_support"

# Run agent with this session
runner = Runner(agent=my_agent, session_service=session_service)

user_content = types.Content(
    role="user",
    parts=[types.Part(text="Hello")]
)

result = runner.run(
    user_id="user123",
    session_id="session_abc",
    new_message=user_content
)
```

### Retrieving Session State

```python
# Get session
session = session_service.get_session(
    app_name="my_app",
    user_id="user123",
    session_id="session_abc"
)

# Read state
final_result = session.state.get("final_report")
all_results = session.state.get("results", [])

print(f"Final report: {final_result}")
print(f"All results: {all_results}")
```

---

## Additional Resources

- [Advanced Patterns Guide](./advanced_patterns.md) - Custom agents with state management
- [Multi-Agent Patterns](./multi_agent_patterns.md) - State flow in multi-agent systems
- [Model Selection Guide](./model_selection.md) - Choosing models for stateful agents
- [Main README](../README.md) - Getting started with Google ADK
- [Google ADK Documentation](https://google.github.io/adk-docs/)

---

## Summary

State management in Google ADK provides a powerful mechanism for agents to share data and coordinate workflows:

- **Session State Dictionary:** Shared key-value store accessible to all agents
- **Reading:** `ctx.session.state.get("key", default)` or `{key}` templates
- **Writing:** Manual (`ctx.session.state["key"] = value`) or automatic (`output_key`)
- **Templates:** Use `{var}`, `{artifact.var}`, `{var?}` in instructions
- **Workflows:** State behavior differs between Sequential, Parallel, and Loop agents

Master state management to build sophisticated, data-driven multi-agent applications.
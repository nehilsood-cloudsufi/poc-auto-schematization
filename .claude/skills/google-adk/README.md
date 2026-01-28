# Google ADK Claude Skill

Expert assistant for Google Agent Development Kit (ADK) - Python only

## Overview

This skill helps you create, configure, and run Google ADK agents using Python. It provides:

- Guided agent creation (single agents, multi-agent systems, custom agents)
- Tool integration (custom functions, built-in tools)
- Configuration assistance (models, parameters, environment)
- Deployment guidance (Cloud Run, Vertex AI)
- Troubleshooting support

## Installation

First, install Google ADK:

```bash
# Stable release (recommended)
pip install google-adk

# Development version
pip install git+https://github.com/google/adk-python.git@main
```

Set up your API key in `.env`:

```bash
GEMINI_API_KEY=your_api_key_here
```

## How to Use

Invoke the skill with:

```
/google-adk
```

or

```
/adk
```

## Common Use Cases

### 1. Create a Basic Agent

**You:** `/google-adk create a simple agent that answers questions`

**Skill will:**
- Generate complete Python code for a basic agent
- Include imports, configuration, and runner setup
- Provide example usage

### 2. Create a Multi-Agent System

**You:** `/google-adk I need a coordinator with two sub-agents`

**Skill will:**
- Create coordinator agent with sub-agents
- Show how agents communicate
- Explain routing logic

### 3. Add Tools to Agent

**You:** `/google-adk add function calling for time and date`

**Skill will:**
- Show how to define custom Python functions as tools
- Demonstrate tool integration with agents
- Provide working examples

### 4. Deploy Agent

**You:** `/google-adk deploy this to Cloud Run`

**Skill will:**
- Generate Dockerfile
- Create deployment configuration
- Provide deployment commands

### 5. Debug Issues

**You:** `/google-adk my agent isn't calling the function`

**Skill will:**
- Check configuration
- Verify function signatures
- Provide debugging steps

### 6. Learn About Concepts

**You:** `/google-adk how do I use LoopAgent?`

**Skill will:**
- Explain the concept with examples
- Reference documentation
- Show when to use it

## Example Templates

The skill includes Python-only example templates:

- [basic_agent.py](examples/basic_agent.py) - Simple LlmAgent
- [multi_agent.py](examples/multi_agent.py) - Coordinator with sub-agents
- [function_calling.py](examples/function_calling.py) - Agents with custom tools
- [workflow_agents.py](examples/workflow_agents.py) - Sequential, Parallel, Loop patterns
- [custom_agent.py](examples/custom_agent.py) - Advanced custom orchestration
- [deployment/](examples/deployment/) - Dockerfile and Cloud Run config

## Agent Types

### Basic Agent (Agent)

```python
from google.adk.agents import Agent

agent = Agent(
    name="assistant",
    model="gemini-2.5-flash",
    instruction="You are a helpful assistant.",
    tools=[...]  # Optional
)
```

### LLM Agent (LlmAgent)

```python
from google.adk.agents import LlmAgent

agent = LlmAgent(
    name="coordinator",
    model="gemini-2.5-flash",
    instruction="Route requests to sub-agents.",
    sub_agents=[agent1, agent2]
)
```

### Workflow Agents

```python
from google.adk.agents import SequentialAgent, ParallelAgent, LoopAgent

# Sequential: agents run one after another
sequential = SequentialAgent(name="Pipeline", sub_agents=[a1, a2, a3])

# Parallel: agents run simultaneously
parallel = ParallelAgent(name="Parallel", sub_agents=[a1, a2, a3])

# Loop: agents iterate multiple times
loop = LoopAgent(name="Loop", sub_agents=[a1, a2], max_iterations=3)
```

### Custom Agent (BaseAgent)

```python
from google.adk.agents import BaseAgent
from google.adk.context import InvocationContext
from typing import AsyncGenerator

class CustomAgent(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        # Custom orchestration logic
        pass
```

## Models

Available Gemini models:

- `gemini-2.5-flash` - Fast and efficient (default)
- `gemini-2.5-pro` - More capable
- `gemini-3-pro-preview` - Latest preview

## Tools

### Custom Function Tools

```python
def get_time() -> str:
    """Get the current time."""
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")

agent = Agent(
    name="time_agent",
    tools=[get_time]
)
```

### Pre-built Tools

```python
from google.adk.tools import google_search, code_execution

agent = Agent(
    name="search_agent",
    tools=[google_search, code_execution]
)
```

## Running Agents

```python
from google.adk import Runner

runner = Runner(root_agent=agent)
result = runner.run(user_message="Hello!")
print(result)
```

## Testing

```bash
# Run ADK eval
adk eval <agent_directory> <evalset_file.evalset.json>
```

## Deployment

### Local Development

```python
# Just run your Python file
python my_agent.py
```

### Cloud Run

```bash
# Build and deploy
docker build -t gcr.io/PROJECT_ID/agent:latest .
docker push gcr.io/PROJECT_ID/agent:latest
gcloud run deploy agent --image gcr.io/PROJECT_ID/agent:latest
```

### Vertex AI

See deployment examples for full configuration.

## Troubleshooting

### Agent Not Calling Functions

**Problem:** Agent doesn't invoke tools even when needed.

**Solutions:**
1. Ensure function has docstring (used as tool description)
2. Add type hints to all parameters
3. Mention the tool explicitly in agent instruction
4. Verify function is in agent's tools list
5. Check that tool name doesn't conflict with reserved names

**Reference:** `google_adk_python/llms-full.txt` lines 1029-1068

**Example Fix:**
```python
# Bad: no docstring, no type hints
def get_weather(city):
    return f"Weather in {city}"

# Good: docstring and type hints
def get_weather(city: str) -> str:
    """Get the current weather for a specified city."""
    return f"Weather in {city}: Sunny, 72°F"

agent = LlmAgent(
    name="weather_agent",
    instruction="Use the get_weather tool to fetch weather information.",
    tools=[get_weather]
)
```

### Import Errors

**Problem:** `ModuleNotFoundError` or `ImportError` when importing ADK modules.

**Solutions:**

```bash
# Install stable release
pip install google-adk

# Or install development version
pip install git+https://github.com/google/adk-python.git@main

# Verify installation
pip list | grep google-adk
```

### API Key Issues

**Problem:** Authentication errors or missing API key.

**Solutions:**

```bash
# Google AI Studio setup
export GOOGLE_API_KEY="your_api_key_here"
export GOOGLE_GENAI_USE_VERTEXAI=FALSE

# In .env file
GOOGLE_API_KEY=your_api_key_here
GOOGLE_GENAI_USE_VERTEXAI=FALSE

# Verify it's loaded
python -c "import os; print(os.getenv('GOOGLE_API_KEY'))"
```

**Reference:** See [Model Selection Guide](references/model_selection.md#google-ai-studio-setup)

### State Not Persisting Between Agents

**Problem:** Data set by one agent is not accessible to subsequent agents.

**Solutions:**
1. Use `output_key` parameter on LlmAgent for automatic state management
2. Verify you're using the same session across agents
3. Check state key names match exactly
4. Ensure you're not creating new sessions accidentally

**Example Fix:**
```python
# Agent 1: Sets state
agent1 = LlmAgent(
    name="Fetcher",
    instruction="Fetch the data.",
    output_key="data"  # Automatically saves to state['data']
)

# Agent 2: Reads state
agent2 = LlmAgent(
    name="Processor",
    instruction="Process the data: {data}"  # Reads state['data']
)

pipeline = SequentialAgent(name="Pipeline", sub_agents=[agent1, agent2])
```

**Reference:** [State Management Guide](references/state_management.md#output-key-pattern)

### Loop Not Terminating

**Problem:** LoopAgent runs forever or doesn't stop when expected.

**Solutions:**
1. Set `max_iterations` as a safety limit
2. Implement a checker agent that escalates when condition is met
3. Verify escalation logic is correct

**Example Fix:**
```python
from google.adk.agents import LoopAgent, BaseAgent
from google.adk.events import Event, EventActions

class StopChecker(BaseAgent):
    async def _run_async_impl(self, ctx):
        is_done = ctx.session.state.get("done", False)
        yield Event(
            author=self.name,
            actions=EventActions(escalate=is_done)  # Stop loop when done
        )

loop = LoopAgent(
    name="WorkLoop",
    max_iterations=10,  # Safety limit
    sub_agents=[worker, StopChecker(name="Checker")]
)
```

**Reference:** [Multi-Agent Patterns](references/multi_agent_patterns.md#iterative-refinement-pattern)

### Parallel Agents Overwriting Data

**Problem:** Parallel agents write to the same state key, causing data loss.

**Solutions:**
1. Use distinct output keys for each parallel agent
2. Design state keys to avoid collisions

**Example Fix:**
```python
# Bad: Both use the same key
agent1 = LlmAgent(..., output_key="data")
agent2 = LlmAgent(..., output_key="data")  # Overwrites agent1!

# Good: Distinct keys
agent1 = LlmAgent(..., output_key="source1_data")
agent2 = LlmAgent(..., output_key="source2_data")

parallel = ParallelAgent(name="Fetcher", sub_agents=[agent1, agent2])
```

**Reference:** [State Management Guide](references/state_management.md#state-in-workflows)

### Model Not Available / Quota Errors

**Problem:** Model not found or quota exceeded errors.

**Solutions:**
1. Verify model name is correct (e.g., "gemini-2.5-flash")
2. Check Google Cloud project has Vertex AI API enabled
3. Verify billing is enabled for your project
4. Check quota limits in Google Cloud Console
5. Try a different model if one is unavailable

**For Vertex AI:**
```bash
# Verify environment variables
echo $GOOGLE_CLOUD_PROJECT
echo $GOOGLE_CLOUD_LOCATION
echo $GOOGLE_GENAI_USE_VERTEXAI

# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com
```

**Reference:** [Model Selection Guide](references/model_selection.md#vertex-ai-setup)

## Complete API Reference

Comprehensive documentation for all Google ADK components.

### Core Agent Classes

#### BaseAgent

Base class for all agents in ADK. All agents inherit from this class.

**Key Method:**
- `_run_async_impl(ctx: InvocationContext) -> AsyncGenerator[Event, None]` - Implement custom agent logic

**Attributes:**
- `name` (str): Unique agent identifier
- `parent_agent` (BaseAgent): Parent agent in hierarchy
- `sub_agents` (list): Child agents

**See:** [Advanced Patterns Guide](references/advanced_patterns.md) for custom agent implementation

#### Agent / LlmAgent

Core agent powered by LLMs for reasoning, understanding, and decision-making.

**Required Parameters:**
- `name` (str): Unique identifier for the agent
- `model` (str): Model identifier (e.g., "gemini-2.5-flash", "gemini-2.5-pro")
- `instruction` (str): Agent's behavior guidance and instructions

**Optional Parameters:**
- `description` (str): Agent capability summary (used for routing in multi-agent systems)
- `tools` (list): Functions/tools the agent can use
- `generate_content_config` (GenerateContentConfig): LLM generation parameters (temperature, max_tokens, etc.)
- `input_schema` (BaseModel): Expected input structure (Pydantic model)
- `output_schema` (BaseModel): Desired output structure (Pydantic model)
- `output_key` (str): Key to store agent response in session state
- `include_contents` (str): 'default' or 'none' - controls conversation history
- `sub_agents` (list): Child agents for multi-agent systems

**State Template Syntax in Instructions:**
- `{var}` - Inserts value of state['var'] (raises error if missing)
- `{artifact.var}` - Inserts text content of artifact named 'var'
- `{var?}` - Inserts value if exists, silently ignores if missing

**Reference:** `google_adk_python/llms-full.txt` lines 919-1166

**See Also:**
- [Model Selection Guide](references/model_selection.md) - Choose the right model
- [State Management Guide](references/state_management.md) - Manage data flow

#### SequentialAgent

Workflow agent that executes sub-agents one after another in sequence.

**Parameters:**
- `name` (str): Agent name
- `sub_agents` (list): Agents to execute in order

**Behavior:**
- Passes the same `InvocationContext` to each sub-agent
- State modifications persist across agents
- Ideal for data pipelines and multi-stage workflows

**Example:**
```python
pipeline = SequentialAgent(
    name="DataPipeline",
    sub_agents=[validator, processor, reporter]
)
```

**See:** [Multi-Agent Patterns](references/multi_agent_patterns.md#sequential-pipeline-pattern)

#### ParallelAgent

Workflow agent that executes sub-agents concurrently.

**Parameters:**
- `name` (str): Agent name
- `sub_agents` (list): Agents to execute in parallel

**Behavior:**
- All sub-agents share the same session state
- Use distinct state keys to avoid race conditions
- Modifies `InvocationContext.branch` for each child

**Example:**
```python
parallel = ParallelAgent(
    name="ConcurrentFetch",
    sub_agents=[fetch_api1, fetch_api2]
)
```

**See:** [Multi-Agent Patterns](references/multi_agent_patterns.md#parallel-fan-outgather-pattern)

#### LoopAgent

Workflow agent that executes sub-agents repeatedly in a loop.

**Parameters:**
- `name` (str): Agent name
- `sub_agents` (list): Agents to execute in each iteration
- `max_iterations` (int): Maximum number of loops (optional)

**Termination:**
- Stops when `max_iterations` is reached
- Stops when any sub-agent returns Event with `escalate=True`

**Example:**
```python
loop = LoopAgent(
    name="RefinementLoop",
    sub_agents=[refiner, checker, stop_checker],
    max_iterations=5
)
```

**See:** [Multi-Agent Patterns](references/multi_agent_patterns.md#iterative-refinement-pattern)

### Runtime Context

#### InvocationContext

Runtime context for agent execution, providing access to session and state.

**Key Attributes:**
- `session` (Session): Current session object
- `session.state` (dict): Session state dictionary for data sharing
- `branch` (str): Branch identifier (used by ParallelAgent)

**Usage in Custom Agents:**
```python
async def _run_async_impl(self, ctx: InvocationContext):
    # Read from state
    data = ctx.session.state.get("key", default_value)

    # Write to state
    ctx.session.state["result"] = processed_data
```

**See:** [State Management Guide](references/state_management.md)

#### Session

Persistent context for a conversation or workflow.

**Key Attributes:**
- `state` (dict): Mutable dictionary for storing data
- `app_name` (str): Application identifier
- `user_id` (str): User identifier
- `session_id` (str): Session identifier

**See:** [State Management Guide](references/state_management.md#session-management)

### Events and Actions

#### Event

Represents an action or message from an agent.

**Key Attributes:**
- `author` (str): Name of agent that created the event
- `content` (Content): Event content (text, structured data, etc.)
- `actions` (EventActions): Actions to perform (escalate, etc.)

**Methods:**
- `is_final_response() -> bool`: Check if this is the final response

#### EventActions

Actions to perform with an event.

**Attributes:**
- `escalate` (bool): If True, stops LoopAgent execution

**Usage:**
```python
yield Event(
    author=self.name,
    actions=EventActions(escalate=True)  # Stop loop
)
```

### Execution

#### Runner

Executes agents and manages sessions.

**Parameters:**
- `agent` or `root_agent` (BaseAgent): The agent to run
- `app_name` (str): Application name (optional)
- `session_service` (SessionService): Session management service (optional)

**Methods:**
- `run(user_id, session_id, new_message) -> Response`: Run agent synchronously
- `run_async(user_id, session_id, new_message) -> AsyncGenerator[Event]`: Run agent asynchronously

**Example:**
```python
runner = Runner(agent=my_agent, app_name="my_app")
result = runner.run(
    user_id="user123",
    session_id="session456",
    new_message=user_content
)
```

#### InMemorySessionService

In-memory session storage for development and testing.

**Methods:**
- `create_session(app_name, user_id, session_id) -> Session`: Create new session
- `get_session(app_name, user_id, session_id) -> Session`: Retrieve existing session

**Example:**
```python
from google.adk.sessions import InMemorySessionService

session_service = InMemorySessionService()
session = session_service.create_session(
    app_name="my_app",
    user_id="user123",
    session_id="session456"
)
session.state["initial_data"] = "value"
```

### Tools

#### FunctionTool

Wrap a Python function as a tool for LlmAgent.

**Auto-wrapping:** In Python, functions are automatically wrapped when passed to `tools` parameter.

**Requirements:**
- Function must have docstring (used as tool description)
- Parameters must have type hints
- Return type should be specified

**Example:**
```python
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"Weather in {city}: Sunny, 72°F"

agent = LlmAgent(
    name="weather_agent",
    tools=[get_weather]  # Automatically wrapped
)
```

#### AgentTool

Wrap an agent as a tool for another agent (hierarchical invocation).

**Usage:**
```python
from google.adk.tools import agent_tool

specialist = LlmAgent(name="Specialist", ...)
specialist_tool = agent_tool.AgentTool(agent=specialist)

coordinator = LlmAgent(
    name="Coordinator",
    tools=[specialist_tool]  # Coordinator can call Specialist as a tool
)
```

**See:** [Multi-Agent Patterns](references/multi_agent_patterns.md#hierarchical-task-decomposition)

### Model Configuration

#### GenerateContentConfig

Configure LLM generation parameters.

**Parameters:**
- `temperature` (float): 0.0-1.0, controls randomness (higher = more creative)
- `max_output_tokens` (int): Maximum response length
- `top_p` (float): Nucleus sampling parameter
- `top_k` (int): Top-k sampling parameter

**Example:**
```python
from google.genai import types

agent = LlmAgent(
    name="precise_agent",
    model="gemini-2.5-pro",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.2,  # More deterministic
        max_output_tokens=1024
    )
)
```

**See:** [Model Selection Guide](references/model_selection.md)

---

## Reference Documentation

### Documentation Files

- [Advanced Patterns Guide](references/advanced_patterns.md) - Custom agents, StoryFlowAgent pattern, advanced orchestration
- [Model Selection Guide](references/model_selection.md) - Model comparison, environment setup, LiteLLM, Ollama
- [Multi-Agent Patterns](references/multi_agent_patterns.md) - Design patterns for multi-agent systems
- [State Management Guide](references/state_management.md) - Session state, data flow between agents
- [Official Documentation Links](references/documentation.md) - Comprehensive categorized list of all official Google ADK docs

### Source Documentation

- [google_adk_python/llms.txt](../../google_adk_python/llms.txt) - Primary Python docs (summary)
- [google_adk_python/llms-full.txt](../../google_adk_python/llms-full.txt) - Complete Python documentation
- [test_google_adk/](../../test_google_adk/) - Python test suite with examples
- [Google ADK Docs](https://google.github.io/adk-docs/) - Official documentation

## Configuration

### Agent Parameters

```python
agent = Agent(
    name="assistant",           # Required: agent name
    model="gemini-2.5-flash",   # Required: model name
    instruction="...",          # Required: agent instructions
    description="...",          # Optional: agent description
    tools=[...],                # Optional: list of tools
    temperature=0.7,            # Optional: 0.0-1.0
    max_output_tokens=1024      # Optional: max tokens
)
```

### Runner Configuration

```python
runner = Runner(root_agent=agent)

# With initial state
result = runner.run(
    user_message="Hello",
    session_state={"key": "value"}
)
```

## Best Practices

1. **Start Simple** - Use Agent or LlmAgent before custom agents
2. **Clear Instructions** - Give agents clear, specific instructions
3. **Tool Docstrings** - Always include docstrings for function tools
4. **Type Hints** - Use Python type hints for function parameters
5. **Error Handling** - Add try/except blocks in production code
6. **Test Locally** - Test agents locally before deploying
7. **Session State** - Use session state for agent communication
8. **Async/Await** - Follow async patterns for custom agents

## Contributing

Found an issue or want to improve the skill? See the [examples](examples/) directory for reference implementations.

## License

This skill references Google ADK which is licensed under Apache 2.0.

## Links

- [Google ADK Python Repository](https://github.com/google/adk-python)
- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [Python API Reference](https://google.github.io/adk-docs/api-reference/python/)
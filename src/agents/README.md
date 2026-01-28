# Google ADK Agent Patterns

This document provides patterns and best practices for implementing agents using the Google Agent Development Kit (ADK) in this project.

## Table of Contents

1. [Overview](#overview)
2. [Pattern 1: Simple BaseAgent](#pattern-1-simple-baseagent)
3. [Pattern 2: LlmAgent with Tools](#pattern-2-llmagent-with-tools)
4. [Pattern 3: Custom BaseAgent with Orchestration](#pattern-3-custom-baseagent-with-orchestration)
5. [State Management](#state-management)
6. [Testing Agents](#testing-agents)
7. [Common Pitfalls](#common-pitfalls)

---

## Overview

Google ADK provides several agent types:

- **BaseAgent**: Base class for custom agents with full control
- **LlmAgent**: Pre-built agent that wraps LLM calls with tool support
- **SequentialAgent**: Runs multiple agents in sequence
- **LoopAgent**: Runs agents in a loop with stop conditions
- **ParallelAgent**: Runs multiple agents concurrently

This project uses three main patterns based on agent complexity.

---

## Pattern 1: Simple BaseAgent

**Use for:** Non-LLM agents that perform deterministic operations (file discovery, validation, evaluation)

**Examples:** DiscoveryAgent, EvaluationAgent

### Implementation

```python
from pathlib import Path
from typing import AsyncGenerator, List

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from src.state.dataset_info import DatasetInfo


class DiscoveryAgent(BaseAgent):
    """
    Agent for discovering dataset files in input directory.

    ADK State Inputs:
        - input_dir: str - Path to input directory containing datasets

    ADK State Outputs:
        - datasets: List[DatasetInfo] - Discovered datasets with files
        - dataset_count: int - Number of datasets found
        - error: str | None - Error message if discovery failed
    """

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Run discovery logic using ADK pattern.

        Reads input_dir from ctx.session.state, discovers datasets,
        and writes results back to state.

        Args:
            ctx: ADK invocation context with session state

        Yields:
            Event with discovery results
        """
        # 1. Read input from state
        input_dir = ctx.session.state.get("input_dir")

        if not input_dir:
            # Write error to state
            ctx.session.state["error"] = "No input_dir specified in state"
            ctx.session.state["datasets"] = []
            ctx.session.state["dataset_count"] = 0

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Discovery failed: No input_dir in state")
                ])
            )
            return

        # 2. Perform discovery (call helper method)
        input_path = Path(input_dir)
        datasets = self._discover_datasets(input_path)

        # 3. Write results to state
        ctx.session.state["datasets"] = datasets
        ctx.session.state["dataset_count"] = len(datasets)
        ctx.session.state["error"] = None

        # 4. Yield event with result
        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text=f"Discovered {len(datasets)} datasets in {input_dir}")
            ])
        )

    def _discover_datasets(self, input_dir: Path) -> List[DatasetInfo]:
        """
        Helper method for dataset discovery (sync).

        This is a private sync method that contains the actual logic.
        Keep business logic in sync helper methods for easier testing.
        """
        datasets = []
        # ... discovery logic ...
        return datasets
```

### Key Points

1. **Inherit from BaseAgent**
2. **Implement `async def _run_async_impl(self, ctx: InvocationContext)`**
3. **Read state**: `ctx.session.state.get("key")`
4. **Write state**: `ctx.session.state["key"] = value`
5. **Yield Events**: Create with `types.Content(parts=[types.Part(text="message")])`
6. **Keep logic in sync helpers**: Easier to test and reason about

---

## Pattern 2: LlmAgent with Tools

**Use for:** Agents that primarily call an LLM with optional tool access

**Examples:** SamplingAgent, SchemaSelectionAgent

### Implementation

```python
from google.adk.agents import LlmAgent

# Define tools that the LLM can call
from src.tools.schema_tools import (
    get_schema_categories,
    generate_data_preview,
    copy_schema_files
)

schema_selection_agent = LlmAgent(
    name="SchemaSelectionAgent",
    model="gemini-2.5-flash",
    instruction="""
    You are a schema selection assistant. Your task is to:
    1. Get available schema categories
    2. Generate a data preview from the dataset
    3. Select the most appropriate schema category
    4. Copy the selected schema files to the dataset directory

    The dataset information is available in the state under 'current_dataset'.
    """,
    tools=[
        get_schema_categories,
        generate_data_preview,
        copy_schema_files
    ],
    output_key="schema_category",  # Automatically writes LLM output to state
)
```

### Key Points

1. **No custom class needed** - LlmAgent is pre-built
2. **Provide instruction**: Clear prompt for the LLM
3. **Specify tools**: Python functions the LLM can call
4. **Use template syntax**: Access state with `{current_dataset}` in instruction
5. **Set output_key**: Automatically stores LLM response in state
6. **Tools must be sync functions**: ADK tools are synchronous

### Tool Function Example

```python
def get_schema_categories(base_path: str = "schema_library") -> dict:
    """
    Get available schema categories from schema library.

    Args:
        base_path: Path to schema library directory

    Returns:
        Dict with status and list of categories
    """
    try:
        schema_path = Path(base_path)
        if not schema_path.exists():
            return {
                "success": False,
                "error": f"Schema library not found at {base_path}"
            }

        categories = [d.name for d in schema_path.iterdir() if d.is_dir()]

        return {
            "success": True,
            "categories": sorted(categories),
            "count": len(categories)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
```

---

## Pattern 3: Custom BaseAgent with Orchestration

**Use for:** Agents that need custom retry logic, validation loops, or orchestrate sub-agents

**Examples:** PVMAPGenerationAgent (with retry loop and validation)

### Implementation

```python
from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from typing import AsyncGenerator


class PVMAPGenerationAgent(BaseAgent):
    """
    Agent for generating PVMAP with retry loop and validation.

    This agent orchestrates:
    1. LLM generation of PVMAP
    2. Validation of output
    3. Retry with feedback if validation fails
    """

    def __init__(self, name: str, max_retries: int = 3):
        super().__init__(name=name)
        self.max_retries = max_retries

        # Create sub-agent for LLM generation
        self.generator = LlmAgent(
            name=f"{name}_Generator",
            model="gemini-2.5-flash",
            instruction="Generate PVMAP CSV based on data and schema...",
            output_key="pvmap_content"
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Run PVMAP generation with retry loop."""

        attempt = 0
        validation_passed = False

        while attempt < self.max_retries and not validation_passed:
            attempt += 1
            ctx.session.state["attempt_number"] = attempt

            # Generate PVMAP using sub-agent
            async for event in self.generator.run_async(ctx):
                yield event

            # Validate output
            validation_passed = self._validate_pvmap(
                ctx.session.state.get("pvmap_content")
            )

            if validation_passed:
                ctx.session.state["validation_passed"] = True
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"PVMAP generated successfully on attempt {attempt}")
                    ])
                )
                return
            else:
                # Prepare feedback for retry
                feedback = self._get_validation_feedback(ctx)
                ctx.session.state["error_feedback"] = feedback

                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Validation failed on attempt {attempt}. Retrying...")
                    ])
                )

        # Max retries exceeded
        ctx.session.state["validation_passed"] = False
        ctx.session.state["error"] = f"Failed after {self.max_retries} attempts"

        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text=f"PVMAP generation failed after {self.max_retries} attempts")
            ])
        )

    def _validate_pvmap(self, pvmap_content: str) -> bool:
        """Validate PVMAP content (sync helper)."""
        # Validation logic...
        return True

    def _get_validation_feedback(self, ctx: InvocationContext) -> str:
        """Extract feedback from validation errors."""
        # Feedback generation...
        return "feedback"
```

### Key Points

1. **Orchestrate sub-agents**: Create LlmAgent or other agents as instance variables
2. **Call sub-agents**: Use `async for event in sub_agent.run_async(ctx)`
3. **Custom logic**: Implement retry loops, validation, conditional flows
4. **State management**: Read/write state between sub-agent calls
5. **Yield events**: Report progress at each step

---

## State Management

### Reading State

```python
# Get with default
input_dir = ctx.session.state.get("input_dir", "default/path")

# Direct access (may raise KeyError)
dataset = ctx.session.state["current_dataset"]

# Check existence
if "datasets" in ctx.session.state:
    datasets = ctx.session.state["datasets"]
```

### Writing State

```python
# Set single value
ctx.session.state["dataset_count"] = 5

# Update multiple values
ctx.session.state["validation_passed"] = True
ctx.session.state["attempt_number"] = 1
ctx.session.state["error"] = None
```

### State Schema Reference

See `src/state/context.py` for complete STATE_SCHEMA documentation of all expected keys.

Key state conventions:
- **Inputs**: Read from previous agents (e.g., `input_dir`, `current_dataset`)
- **Outputs**: Write for next agents (e.g., `datasets`, `pvmap_content`)
- **Errors**: Use `error` key for error messages, `error_feedback` for retry feedback
- **Config**: Store configuration in state (e.g., `model`, `max_retries`, `skip_evaluation`)

---

## Testing Agents

### Async Test Pattern

```python
import pytest
from unittest.mock import Mock
from pathlib import Path

from src.agents.discovery_agent import DiscoveryAgent


@pytest.fixture
def mock_invocation_context(temp_dir):
    """Create mock ADK InvocationContext for testing."""
    ctx = Mock()
    ctx.session = Mock()
    ctx.session.state = {
        "input_dir": str(temp_dir)
    }
    ctx.session.id = "test-session-123"
    ctx.invocation_id = "test-invocation-456"
    ctx.agent = Mock()
    ctx.agent.name = "TestAgent"
    return ctx


@pytest.mark.asyncio
async def test_discovery_agent_success(mock_invocation_context, temp_dir):
    """Test successful discovery with ADK pattern."""
    # Setup test data
    dataset_dir = Path(mock_invocation_context.session.state["input_dir"]) / "test_dataset"
    dataset_dir.mkdir()

    # Run agent
    agent = DiscoveryAgent(name="DiscoveryAgent")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    # Verify state was updated
    assert mock_invocation_context.session.state["dataset_count"] == 1
    assert len(mock_invocation_context.session.state["datasets"]) == 1
    assert mock_invocation_context.session.state["error"] is None

    # Verify event
    assert len(events) == 1
    event_text = events[0].content.parts[0].text
    assert "Discovered 1 datasets" in event_text
```

### Testing LlmAgent

For LlmAgent, test the tools separately (they're sync functions) and use integration tests for the full agent.

---

## Common Pitfalls

### 1. Using string instead of Content for Events

❌ **Wrong:**
```python
yield Event(author=self.name, content="message")
```

✅ **Correct:**
```python
yield Event(
    author=self.name,
    content=types.Content(parts=[types.Part(text="message")])
)
```

### 2. Forgetting to await/async iterate

❌ **Wrong:**
```python
result = sub_agent.run_async(ctx)  # This returns AsyncGenerator, not result!
```

✅ **Correct:**
```python
async for event in sub_agent.run_async(ctx):
    yield event  # Propagate events from sub-agent
```

### 3. Using PipelineContext instead of ctx.session.state

❌ **Wrong (deprecated):**
```python
from src.state.context import PipelineContext
ctx = PipelineContext(dataset_info, config)
```

✅ **Correct:**
```python
# Use ADK's native state management
input_dir = ctx.session.state.get("input_dir")
ctx.session.state["datasets"] = datasets
```

### 4. Mixing sync and async incorrectly

❌ **Wrong:**
```python
async def _run_async_impl(self, ctx):
    result = self._some_sync_method()  # Blocking!
```

✅ **Correct:**
```python
async def _run_async_impl(self, ctx):
    # Sync helpers are fine for quick operations
    result = self._some_sync_method()

    # For I/O or long operations, use async
    result = await self._some_async_method()
```

### 5. Not documenting state inputs/outputs

❌ **Wrong:**
```python
class MyAgent(BaseAgent):
    """Does stuff."""
```

✅ **Correct:**
```python
class MyAgent(BaseAgent):
    """
    Agent for doing stuff.

    ADK State Inputs:
        - input_key: str - Description of input
        - another_input: List[str] - Another input

    ADK State Outputs:
        - output_key: dict - Description of output
        - status: bool - Success status
    """
```

### 6. Forgetting pytest-asyncio marker

❌ **Wrong:**
```python
def test_my_agent(mock_context):  # Missing @pytest.mark.asyncio
    async for event in agent._run_async_impl(mock_context):
        # This will fail!
```

✅ **Correct:**
```python
@pytest.mark.asyncio
async def test_my_agent(mock_context):
    async for event in agent._run_async_impl(mock_context):
        # Works correctly
```

---

## Additional Resources

- **ADK Documentation**: `.claude/skills/google-adk/README.md`
- **State Management**: `.claude/skills/google-adk/references/state_management.md`
- **Multi-Agent Patterns**: `.claude/skills/google-adk/references/multi_agent_patterns.md`
- **State Schema**: `src/state/context.py` (STATE_SCHEMA constant)
- **Example Tests**: `tests/agents/test_discovery_agent.py`

---

## Quick Reference

| Pattern | When to Use | Example |
|---------|-------------|---------|
| Simple BaseAgent | Non-LLM operations | DiscoveryAgent, EvaluationAgent |
| LlmAgent with Tools | LLM with function calling | SchemaSelectionAgent, SamplingAgent |
| Custom BaseAgent | Complex orchestration | PVMAPGenerationAgent (retry loop) |

**State Access:**
- Read: `ctx.session.state.get("key", default)`
- Write: `ctx.session.state["key"] = value`

**Event Creation:**
```python
yield Event(
    author=self.name,
    content=types.Content(parts=[types.Part(text="message")])
)
```

**Test Pattern:**
```python
@pytest.mark.asyncio
async def test_agent(mock_invocation_context):
    agent = MyAgent(name="Test")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)
    # Assertions...
```

# Multi-Agent System Patterns in Google ADK

Comprehensive guide to designing multi-agent systems using Google ADK. All examples are Python-only.

**Reference:** `google_adk_python/llms-full.txt` lines 1976-2535

## Table of Contents

- [Overview](#overview)
- [ADK Composition Primitives](#adk-composition-primitives)
- [Communication Mechanisms](#communication-mechanisms)
- [Common Patterns](#common-patterns)
  - [Coordinator/Dispatcher](#coordinatordispatcher-pattern)
  - [Sequential Pipeline](#sequential-pipeline-pattern)
  - [Parallel Fan-Out/Gather](#parallel-fan-outgather-pattern)
  - [Hierarchical Task Decomposition](#hierarchical-task-decomposition)
  - [Generator-Critic](#generatorcritic-pattern)
  - [Iterative Refinement](#iterative-refinement-pattern)
  - [Human-in-the-Loop](#human-in-the-loop-pattern)

---

## Overview

As agentic applications grow in complexity, structuring them as a single, monolithic agent becomes challenging to develop, maintain, and reason about. Google ADK supports building sophisticated applications by composing multiple distinct agents into a **Multi-Agent System (MAS)**.

### Benefits of Multi-Agent Systems

- **Modularity:** Each agent has a focused responsibility
- **Specialization:** Agents can be optimized for specific tasks
- **Reusability:** Agents can be reused across different workflows
- **Maintainability:** Easier to debug and update individual agents
- **Structured Control Flow:** Workflow agents provide deterministic execution patterns

### Agent Types in Multi-Agent Systems

You can compose various agent types:

- **LLM Agents:** Agents powered by large language models (LlmAgent, Agent)
- **Workflow Agents:** Specialized orchestrators (SequentialAgent, ParallelAgent, LoopAgent)
- **Custom Agents:** Your own agents inheriting from BaseAgent

---

## ADK Composition Primitives

ADK provides core building blocks for structuring multi-agent systems.

### 1. Agent Hierarchy (Parent-Child Relationships)

The foundation of multi-agent systems is the parent-child relationship defined in `BaseAgent`.

**Key Concepts:**

- **Establishing Hierarchy:** Pass a list of agent instances to the `sub_agents` parameter
- **Single Parent Rule:** An agent can only be added as a sub-agent once
- **Automatic Setup:** ADK automatically sets the `parent_agent` attribute
- **Navigation:** Use `agent.parent_agent` or `agent.find_agent(name)` to traverse the hierarchy

**Example:**

```python
from google.adk.agents import LlmAgent

# Define individual agents
greeter = LlmAgent(
    name="Greeter",
    model="gemini-2.5-flash",
    description="Greets users warmly."
)

task_executor = LlmAgent(
    name="TaskExecutor",
    model="gemini-2.5-flash",
    description="Executes tasks for users."
)

# Create parent agent with sub-agents
coordinator = LlmAgent(
    name="Coordinator",
    model="gemini-2.5-flash",
    instruction="Coordinate greetings and task execution.",
    description="Main coordinator agent.",
    sub_agents=[greeter, task_executor]  # Establish hierarchy
)

# Framework automatically sets:
# greeter.parent_agent == coordinator
# task_executor.parent_agent == coordinator
```

**Reference:** llms-full.txt lines 1997-2029

### 2. Workflow Agents as Orchestrators

ADK includes specialized agents that orchestrate the execution flow of their sub-agents.

#### SequentialAgent

Executes sub-agents one after another in the order they are listed.

- **Context:** Passes the same `InvocationContext` sequentially
- **Communication:** Agents pass results via shared session state
- **Use Case:** Multi-step pipelines where each step depends on the previous

**Example:**

```python
from google.adk.agents import SequentialAgent, LlmAgent

# Step 1: Fetch data
step1 = LlmAgent(
    name="Step1_Fetch",
    model="gemini-2.5-flash",
    instruction="Fetch the data from the source.",
    output_key="data"  # Saves output to state['data']
)

# Step 2: Process data
step2 = LlmAgent(
    name="Step2_Process",
    model="gemini-2.5-flash",
    instruction="Process the data from state key 'data'. Output the result.",
    output_key="result"
)

# Pipeline executes Step1 then Step2
pipeline = SequentialAgent(
    name="MyPipeline",
    sub_agents=[step1, step2]
)

# When pipeline runs:
# 1. Step1 executes, saves result to state['data']
# 2. Step2 executes, reads state['data'], processes it
```

**Reference:** llms-full.txt lines 2039-2057

#### ParallelAgent

Executes sub-agents in parallel. Events from sub-agents may be interleaved.

- **Context:** Modifies `InvocationContext.branch` for each child agent
- **State:** All parallel children access the same shared `session.state`
- **Use Case:** Independent tasks that can run concurrently
- **Warning:** Use distinct state keys to avoid race conditions

**Example:**

```python
from google.adk.agents import ParallelAgent, LlmAgent

# Fetch weather data
fetch_weather = LlmAgent(
    name="WeatherFetcher",
    model="gemini-2.5-flash",
    instruction="Fetch current weather information.",
    output_key="weather"
)

# Fetch news data
fetch_news = LlmAgent(
    name="NewsFetcher",
    model="gemini-2.5-flash",
    instruction="Fetch latest news headlines.",
    output_key="news"
)

# Run both fetchers concurrently
gatherer = ParallelAgent(
    name="InfoGatherer",
    sub_agents=[fetch_weather, fetch_news]
)

# When gatherer runs:
# - WeatherFetcher and NewsFetcher run concurrently
# - Results saved to state['weather'] and state['news']
# - A subsequent agent can read both state keys
```

**Reference:** llms-full.txt lines 2059-2079

#### LoopAgent

Executes sub-agents sequentially in a loop.

- **Termination:** Stops when `max_iterations` is reached or an agent escalates
- **Context & State:** Passes the same `InvocationContext` in each iteration
- **Use Case:** Retry logic, polling, iterative refinement
- **Escalation:** Any sub-agent can return `Event` with `escalate=True` to stop the loop

**Example:**

```python
from google.adk.agents import LoopAgent, LlmAgent, BaseAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext
from typing import AsyncGenerator

# Custom agent to check if work is complete
class CheckCondition(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        status = ctx.session.state.get("status", "pending")
        is_done = (status == "completed")
        # Escalate to stop loop if done
        yield Event(
            author=self.name,
            actions=EventActions(escalate=is_done)
        )

# Agent that performs work
process_step = LlmAgent(
    name="ProcessingStep",
    model="gemini-2.5-flash",
    instruction="Perform processing. Set state['status'] to 'completed' when done.",
)

# Loop until completed or 10 iterations
poller = LoopAgent(
    name="StatusPoller",
    max_iterations=10,
    sub_agents=[process_step, CheckCondition(name="Checker")]
)

# When poller runs:
# 1. ProcessingStep executes (may update state['status'])
# 2. Checker executes (escalates if status == 'completed')
# 3. Loop repeats until escalation or 10 iterations
```

**Reference:** llms-full.txt lines 2081-2113

---

## Communication Mechanisms

Agents within a multi-agent system need to exchange data and coordinate actions. ADK provides three primary mechanisms.

### 1. Shared Session State

The most fundamental way for agents to communicate passively.

**How It Works:**

- One agent writes to `ctx.session.state['key'] = value`
- Another agent reads with `ctx.session.state.get('key')`
- The `output_key` property on LlmAgent automatically saves output to state

**Characteristics:**

- Asynchronous, passive communication
- Ideal for pipelines and sequential workflows
- State changes tracked via callbacks

**Example:**

```python
from google.adk.agents import LlmAgent, SequentialAgent

# Agent A generates data
agent_a = LlmAgent(
    name="AgentA",
    model="gemini-2.5-flash",
    instruction="Find the capital of France.",
    output_key="capital_city"  # Auto-saves to state
)

# Agent B uses data from Agent A
agent_b = LlmAgent(
    name="AgentB",
    model="gemini-2.5-flash",
    instruction="Tell me about the city stored in state key 'capital_city'."
)

# Sequential execution
pipeline = SequentialAgent(
    name="CityInfo",
    sub_agents=[agent_a, agent_b]
)

# AgentA runs -> saves "Paris" to state['capital_city']
# AgentB runs -> reads state['capital_city'] -> "Paris"
```

**Reference:** llms-full.txt lines 2119-2144

### 2. LLM-Driven Delegation (Agent Transfer)

Leverages an LLM's understanding to dynamically route tasks to appropriate agents.

**How It Works:**

- The agent's LLM generates: `transfer_to_agent(agent_name='target_agent_name')`
- ADK's `AutoFlow` intercepts the call and routes execution
- Target agent is identified using `root_agent.find_agent()`

**Requirements:**

- Calling agent needs clear `instructions` on when to transfer
- Target agents need distinct `description`s for LLM decision-making
- Sub-agents or parent agents are valid transfer targets

**Characteristics:**

- Dynamic, flexible routing based on LLM interpretation
- Best for request routing and delegation

**Example:**

```python
from google.adk.agents import LlmAgent

# Specialized agents with clear descriptions
booking_agent = LlmAgent(
    name="Booker",
    model="gemini-2.5-flash",
    description="Handles flight and hotel bookings."
)

info_agent = LlmAgent(
    name="Info",
    model="gemini-2.5-flash",
    description="Provides general information and answers questions."
)

# Coordinator with delegation instructions
coordinator = LlmAgent(
    name="Coordinator",
    model="gemini-2.5-flash",
    instruction="You are an assistant. Delegate booking tasks to Booker and info requests to Info.",
    description="Main coordinator.",
    sub_agents=[booking_agent, info_agent]
)

# When coordinator receives "Book a flight":
# LLM generates: transfer_to_agent(agent_name='Booker')
# ADK routes execution to booking_agent

# When coordinator receives "What's the weather?":
# LLM generates: transfer_to_agent(agent_name='Info')
# ADK routes execution to info_agent
```

**Reference:** llms-full.txt lines 2146-2179

### 3. Explicit Invocation (AgentTool)

Allows an LlmAgent to treat another agent as a callable function/tool.

**How It Works:**

- Wrap target agent in `AgentTool`
- Include in parent agent's `tools` list
- Parent LLM can call it like any other function
- AgentTool executes the agent and returns its response

**Characteristics:**

- Synchronous (within parent's flow)
- Explicit, controlled invocation
- Useful for treating agents as reusable functions

**Example:**

```python
from google.adk.agents import LlmAgent, BaseAgent
from google.adk.tools import agent_tool
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from typing import AsyncGenerator

# Define a specialized agent
class ImageGeneratorAgent(BaseAgent):
    name: str = "ImageGen"
    description: str = "Generates an image based on a prompt."

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        prompt = ctx.session.state.get("image_prompt", "default prompt")
        # Generate image (simplified)
        image_bytes = b"..."  # Actual image generation logic here
        yield Event(
            author=self.name,
            content=types.Content(
                parts=[types.Part.from_bytes(image_bytes, "image/png")]
            )
        )

# Create the agent and wrap it as a tool
image_agent = ImageGeneratorAgent()
image_tool = agent_tool.AgentTool(agent=image_agent)

# Parent agent uses the AgentTool
artist_agent = LlmAgent(
    name="Artist",
    model="gemini-2.5-flash",
    instruction="Create a prompt and use the ImageGen tool to generate the image.",
    tools=[image_tool]  # Include AgentTool
)

# When artist_agent runs:
# 1. LLM generates: ImageGen(image_prompt='a cat wearing a hat')
# 2. Framework calls image_tool.run_async()
# 3. ImageGeneratorAgent executes and returns image
# 4. Image Part returned to artist_agent as tool result
```

**Reference:** llms-full.txt lines 2181-2228

---

## Common Patterns

By combining ADK's primitives, you can implement various multi-agent collaboration patterns.

### Coordinator/Dispatcher Pattern

**Purpose:** Route incoming requests to the appropriate specialist agent.

**Structure:**

- Central LlmAgent (Coordinator) manages several specialized sub-agents
- Uses LLM-Driven Delegation or Explicit Invocation (AgentTool)

**When to Use:**

- Help desk routing (billing, support, sales)
- Request classification systems
- Multi-domain assistants

**Example (LLM Transfer):**

```python
from google.adk.agents import LlmAgent

# Specialized agents
billing_agent = LlmAgent(
    name="Billing",
    model="gemini-2.5-flash",
    description="Handles billing inquiries and payment issues."
)

support_agent = LlmAgent(
    name="Support",
    model="gemini-2.5-flash",
    description="Handles technical support requests and troubleshooting."
)

# Coordinator with routing logic
coordinator = LlmAgent(
    name="HelpDeskCoordinator",
    model="gemini-2.5-flash",
    instruction="""Route user requests to the appropriate agent:
    - Use Billing agent for payment issues, invoices, billing questions
    - Use Support agent for technical problems, bugs, login issues""",
    description="Main help desk router.",
    sub_agents=[billing_agent, support_agent]
)

# User: "My payment failed"
# -> Coordinator calls: transfer_to_agent(agent_name='Billing')

# User: "I can't log in"
# -> Coordinator calls: transfer_to_agent(agent_name='Support')
```

**Reference:** llms-full.txt lines 2235-2266

---

### Sequential Pipeline Pattern

**Purpose:** Implement a multi-step process where output of one step feeds into the next.

**Structure:**

- SequentialAgent contains sub-agents executed in fixed order
- Uses Shared Session State for communication
- Earlier agents write results (via `output_key`), later agents read them

**When to Use:**

- Data processing pipelines
- Multi-stage content generation
- Validation → Processing → Reporting workflows

**Example:**

```python
from google.adk.agents import SequentialAgent, LlmAgent

# Step 1: Validate input
validator = LlmAgent(
    name="ValidateInput",
    model="gemini-2.5-flash",
    instruction="Validate the input data. Output 'valid' or 'invalid'.",
    output_key="validation_status"
)

# Step 2: Process if valid
processor = LlmAgent(
    name="ProcessData",
    model="gemini-2.5-flash",
    instruction="If state key 'validation_status' is 'valid', process the data. Otherwise skip.",
    output_key="result"
)

# Step 3: Report result
reporter = LlmAgent(
    name="ReportResult",
    model="gemini-2.5-flash",
    instruction="Report the result from state key 'result' to the user."
)

# Create pipeline
data_pipeline = SequentialAgent(
    name="DataPipeline",
    sub_agents=[validator, processor, reporter]
)

# Execution flow:
# 1. validator runs -> saves to state['validation_status']
# 2. processor runs -> reads state['validation_status'], saves to state['result']
# 3. reporter runs -> reads state['result'] and reports
```

**Reference:** llms-full.txt lines 2268-2297

---

### Parallel Fan-Out/Gather Pattern

**Purpose:** Execute independent tasks simultaneously to reduce latency, then combine outputs.

**Structure:**

- ParallelAgent runs multiple sub-agents concurrently (Fan-Out)
- Often followed by an aggregation agent (Gather)
- Uses SequentialAgent to combine parallel and sequential steps

**When to Use:**

- Fetching data from multiple APIs
- Running independent analyses
- Parallel web searches or tool calls

**Example:**

```python
from google.adk.agents import SequentialAgent, ParallelAgent, LlmAgent

# Parallel fetch agents
fetch_api1 = LlmAgent(
    name="API1Fetcher",
    model="gemini-2.5-flash",
    instruction="Fetch data from API 1.",
    output_key="api1_data"
)

fetch_api2 = LlmAgent(
    name="API2Fetcher",
    model="gemini-2.5-flash",
    instruction="Fetch data from API 2.",
    output_key="api2_data"
)

# Parallel execution (Fan-Out)
gather_concurrently = ParallelAgent(
    name="ConcurrentFetch",
    sub_agents=[fetch_api1, fetch_api2]
)

# Aggregation agent (Gather)
synthesizer = LlmAgent(
    name="Synthesizer",
    model="gemini-2.5-flash",
    instruction="Combine results from state keys 'api1_data' and 'api2_data' into a comprehensive report."
)

# Overall workflow: Parallel fetch -> Sequential synthesis
overall_workflow = SequentialAgent(
    name="FetchAndSynthesize",
    sub_agents=[gather_concurrently, synthesizer]
)

# Execution flow:
# 1. fetch_api1 and fetch_api2 run concurrently
# 2. Both save results to state
# 3. synthesizer runs after both complete
# 4. synthesizer reads state['api1_data'] and state['api2_data']
```

**Reference:** llms-full.txt lines 2299-2336

---

### Hierarchical Task Decomposition

**Purpose:** Solve complex problems by recursively breaking them down into simpler steps.

**Structure:**

- Multi-level tree of agents
- Higher-level agents break down goals and delegate to lower-level agents
- Uses LLM-Driven Delegation or Explicit Invocation

**When to Use:**

- Complex research tasks
- Software development workflows
- Multi-stage planning and execution

**Example:**

```python
from google.adk.agents import LlmAgent
from google.adk.tools import agent_tool

# Low-level tool agents
web_searcher = LlmAgent(
    name="WebSearch",
    model="gemini-2.5-flash",
    description="Performs web searches for facts."
)

summarizer = LlmAgent(
    name="Summarizer",
    model="gemini-2.5-flash",
    description="Summarizes text."
)

# Mid-level agent combining low-level tools
research_assistant = LlmAgent(
    name="ResearchAssistant",
    model="gemini-2.5-flash",
    description="Finds and summarizes information on a topic.",
    tools=[
        agent_tool.AgentTool(agent=web_searcher),
        agent_tool.AgentTool(agent=summarizer)
    ]
)

# High-level agent delegating to mid-level agent
report_writer = LlmAgent(
    name="ReportWriter",
    model="gemini-2.5-flash",
    instruction="Write a comprehensive report on topic X. Use the ResearchAssistant to gather information.",
    tools=[agent_tool.AgentTool(agent=research_assistant)]
)

# Execution flow:
# User -> ReportWriter
# ReportWriter calls ResearchAssistant
# ResearchAssistant calls WebSearch and Summarizer
# Results flow back up the hierarchy
```

**Reference:** llms-full.txt lines 2338-2381

---

### Generator-Critic Pattern

**Purpose:** Improve quality or validity of generated output through review.

**Structure:**

- SequentialAgent with two agents: Generator and Critic/Reviewer
- Generator creates output, Critic evaluates it
- Uses Shared Session State for communication

**When to Use:**

- Content quality assurance
- Fact-checking generated text
- Code review workflows
- Output validation

**Example:**

```python
from google.adk.agents import SequentialAgent, LlmAgent

# Generator agent
generator = LlmAgent(
    name="DraftWriter",
    model="gemini-2.5-flash",
    instruction="Write a short paragraph about subject X.",
    output_key="draft_text"
)

# Critic agent
reviewer = LlmAgent(
    name="FactChecker",
    model="gemini-2.5-flash",
    instruction="""Review the text in state key 'draft_text' for factual accuracy.
    Output 'valid' or 'invalid' with specific reasons.""",
    output_key="review_status"
)

# Optional: Reviser agent if review is negative
reviser = LlmAgent(
    name="Reviser",
    model="gemini-2.5-flash",
    instruction="""If state key 'review_status' is 'invalid', revise the text in state key 'draft_text'.
    Otherwise, confirm the text is ready."""
)

# Review pipeline
review_pipeline = SequentialAgent(
    name="WriteAndReview",
    sub_agents=[generator, reviewer, reviser]
)

# Execution flow:
# 1. generator runs -> saves draft to state['draft_text']
# 2. reviewer runs -> reads state['draft_text'], saves status to state['review_status']
# 3. reviser runs -> reads state['review_status'], may revise if invalid
```

**Reference:** llms-full.txt lines 2383-2421

---

### Iterative Refinement Pattern

**Purpose:** Progressively improve a result over multiple iterations until quality threshold is met.

**Structure:**

- LoopAgent containing refinement and quality checking agents
- Uses Shared Session State to store evolving result
- Terminates via `max_iterations` or escalation when quality is satisfactory

**When to Use:**

- Code refinement and optimization
- Text editing and polishing
- Design iteration
- Problem-solving with feedback loops

**Example:**

```python
from google.adk.agents import LoopAgent, LlmAgent, BaseAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext
from typing import AsyncGenerator

# Agent to refine code
code_refiner = LlmAgent(
    name="CodeRefiner",
    model="gemini-2.5-flash",
    instruction="""Read state['current_code'] (if exists) and state['requirements'].
    Generate or refine Python code to meet requirements.
    Focus on improving code quality, readability, and correctness.""",
    output_key="current_code"  # Overwrites previous code
)

# Agent to check quality
quality_checker = LlmAgent(
    name="QualityChecker",
    model="gemini-2.5-flash",
    instruction="""Evaluate the code in state['current_code'] against state['requirements'].
    Check for:
    - Correctness
    - Readability
    - Best practices
    Output 'pass' or 'fail' with specific feedback.""",
    output_key="quality_status"
)

# Custom agent to check status and escalate if pass
class CheckStatusAndEscalate(BaseAgent):
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        status = ctx.session.state.get("quality_status", "fail")
        should_stop = (status == "pass")
        yield Event(
            author=self.name,
            actions=EventActions(escalate=should_stop)
        )

# Refinement loop
refinement_loop = LoopAgent(
    name="CodeRefinementLoop",
    max_iterations=5,
    sub_agents=[
        code_refiner,
        quality_checker,
        CheckStatusAndEscalate(name="StopChecker")
    ]
)

# Execution flow:
# Iteration 1: Refiner -> Checker -> StopChecker (continue if fail)
# Iteration 2: Refiner (improves code) -> Checker -> StopChecker
# ...
# Loop stops when:
# - QualityChecker outputs 'pass' (StopChecker escalates)
# - OR 5 iterations complete
```

**Reference:** llms-full.txt lines 2423-2474

---

### Human-in-the-Loop Pattern

**Purpose:** Allow for human oversight, approval, correction, or tasks that AI cannot perform.

**Structure:**

- Integrates human intervention points using custom tools
- Tool pauses execution and sends request to external system
- Human provides input, tool returns response to agent

**When to Use:**

- Approval workflows
- Content moderation
- Complex decision-making
- Tasks requiring human expertise

**Example (Conceptual):**

```python
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool

# External approval function (conceptual - implement your own)
async def external_approval_tool(amount: float, reason: str) -> str:
    """
    Send approval request to human review system.

    Args:
        amount: Dollar amount requiring approval
        reason: Justification for the request

    Returns:
        Human's decision: 'approved' or 'rejected'
    """
    # 1. Send details to human review system (e.g., via API)
    # 2. Poll or wait for human response
    # 3. Return the decision
    pass  # Implementation depends on your system

approval_tool = FunctionTool(func=external_approval_tool)

# Agent that prepares the approval request
prepare_request = LlmAgent(
    name="PrepareApproval",
    model="gemini-2.5-flash",
    instruction="""Prepare the approval request details based on user input.
    Extract the amount and reason from the request.""",
    # Sets state['approval_amount'] and state['approval_reason']
)

# Agent that calls the human approval tool
request_approval = LlmAgent(
    name="RequestHumanApproval",
    model="gemini-2.5-flash",
    instruction="""Use the external_approval_tool with:
    - amount from state['approval_amount']
    - reason from state['approval_reason']""",
    tools=[approval_tool],
    output_key="human_decision"
)

# Agent that processes the decision
process_decision = LlmAgent(
    name="ProcessDecision",
    model="gemini-2.5-flash",
    instruction="""Check state key 'human_decision'.
    If 'approved', proceed with the action.
    If 'rejected', inform the user and explain next steps."""
)

# Approval workflow
approval_workflow = SequentialAgent(
    name="HumanApprovalWorkflow",
    sub_agents=[prepare_request, request_approval, process_decision]
)

# Execution flow:
# 1. prepare_request extracts details from user input
# 2. request_approval calls external_approval_tool (waits for human)
# 3. Human approves/rejects
# 4. process_decision acts on human's decision
```

**Note:** ADK doesn't have a built-in "Human Agent" type. This requires custom integration with your external systems (UI, ticketing system, API, etc.).

**Reference:** llms-full.txt lines 2476-2532

---

## Best Practices

### 1. Clear Agent Descriptions

When using LLM-Driven Delegation, provide clear `description`s for each agent:

```python
# Good
agent = LlmAgent(
    name="Billing",
    description="Handles billing inquiries, payment issues, and invoice questions."
)

# Bad
agent = LlmAgent(
    name="Billing",
    description="Agent 1"
)
```

### 2. Use Distinct State Keys

In parallel workflows, use unique state keys to avoid race conditions:

```python
# Good
fetch1 = LlmAgent(..., output_key="source1_data")
fetch2 = LlmAgent(..., output_key="source2_data")

# Bad (both write to same key)
fetch1 = LlmAgent(..., output_key="data")
fetch2 = LlmAgent(..., output_key="data")
```

### 3. Explicit Termination in Loops

Always define clear termination conditions for LoopAgent:

```python
# Good: max_iterations + escalation logic
loop = LoopAgent(
    max_iterations=10,  # Safety limit
    sub_agents=[worker, checker]  # checker escalates when done
)

# Bad: no termination condition
loop = LoopAgent(sub_agents=[worker])  # Runs forever!
```

### 4. State Management

Use `output_key` for automatic state management:

```python
# Good: automatic state management
agent = LlmAgent(..., output_key="result")

# Also Good: manual state management when needed
# In custom agent: ctx.session.state['result'] = value
```

### 5. Appropriate Pattern Selection

Choose the right pattern for your use case:

- **Simple routing:** Coordinator/Dispatcher
- **Fixed steps:** Sequential Pipeline
- **Independent tasks:** Parallel Fan-Out/Gather
- **Complex decomposition:** Hierarchical Task Decomposition
- **Quality assurance:** Generator-Critic
- **Iterative improvement:** Iterative Refinement
- **Human oversight:** Human-in-the-Loop

---

## Additional Resources

- [Advanced Patterns Guide](./advanced_patterns.md) - Custom agents and complex orchestration
- [Model Selection Guide](./model_selection.md) - Choosing the right model for each agent
- [State Management Guide](./state_management.md) - Managing data flow between agents
- [Main README](../README.md) - Getting started with Google ADK
- [Google ADK Documentation](https://google.github.io/adk-docs/)

---

## Summary

Multi-agent systems in Google ADK provide powerful patterns for building complex, maintainable agentic applications. By combining:

- **Agent Hierarchy** for structure
- **Workflow Agents** for orchestration
- **Communication Mechanisms** for data flow

You can implement sophisticated patterns that are modular, reusable, and easy to reason about.

Start simple with Sequential Pipelines or Coordinator patterns, then grow into more complex hierarchical or iterative patterns as your application evolves.
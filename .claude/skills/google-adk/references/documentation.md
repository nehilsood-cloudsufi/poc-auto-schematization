# Official Google ADK Documentation Links

Comprehensive reference to all official Google Agent Development Kit (ADK) documentation pages. Use this as a quick reference to find specific topics in the official docs.

**Source:** Extracted from `google_adk_python/llms.txt` lines 169-228

## Table of Contents

- [Getting Started](#getting-started)
- [Agents](#agents)
- [Tools](#tools)
- [Deployment](#deployment)
- [Sessions & State](#sessions--state)
- [Streaming](#streaming)
- [Advanced Topics](#advanced-topics)
- [Community & Tutorials](#community--tutorials)

---

## Getting Started

Essential documentation for getting started with Google ADK.

### [What is Agent Development Kit?](https://github.com/google/adk-docs/blob/main/docs/index.md)
Overview of ADK, its purpose, and core concepts. Start here to understand what ADK offers.

### [Get Started](https://github.com/google/adk-docs/blob/main/docs/get-started/index.md)
Main entry point for getting started with ADK development.

### [Agent Development Kit (ADK) About](https://github.com/google/adk-docs/blob/main/docs/get-started/about.md)
Detailed introduction to ADK architecture and philosophy.

### [Installing ADK](https://github.com/google/adk-docs/blob/main/docs/get-started/installation.md)
Step-by-step installation instructions for Python and Java SDKs.

### [Quickstart](https://github.com/google/adk-docs/blob/main/docs/get-started/quickstart.md)
Build your first ADK agent in minutes with this hands-on guide.

### [Testing your Agents](https://github.com/google/adk-docs/blob/main/docs/get-started/testing.md)
Best practices for testing ADK agents during development.

---

## Agents

Documentation for creating and configuring different types of agents.

### [Agents Overview](https://github.com/google/adk-docs/blob/main/docs/agents/index.md)
Introduction to agents in ADK - the core building blocks of your application.

### [LLM Agent](https://github.com/google/adk-docs/blob/main/docs/agents/llm-agents.md)
Comprehensive guide to LLM-powered agents with instructions, tools, and configuration.

### [Custom Agents](https://github.com/google/adk-docs/blob/main/docs/agents/custom-agents.md)
Build custom agents by inheriting from BaseAgent for advanced orchestration logic.

### [Multi-Agent Systems in ADK](https://github.com/google/adk-docs/blob/main/docs/agents/multi-agents.md)
Design patterns and best practices for building multi-agent systems with hierarchies and delegation.

### [Using Different Models with ADK](https://github.com/google/adk-docs/blob/main/docs/agents/models.md)
Configure Gemini models, use LiteLLM for other providers, or run local models with Ollama.

---

## Workflow Agents

Specialized agents for controlling execution flow.

### [Workflow Agents Overview](https://github.com/google/adk-docs/blob/main/docs/agents/workflow-agents/index.md)
Introduction to workflow agents: Sequential, Parallel, and Loop agents for orchestration.

### [Sequential Agents](https://github.com/google/adk-docs/blob/main/docs/agents/workflow-agents/sequential-agents.md)
Execute agents one after another in a fixed order - ideal for pipelines.

### [Parallel Agents](https://github.com/google/adk-docs/blob/main/docs/agents/workflow-agents/parallel-agents.md)
Run multiple agents concurrently to reduce latency and improve throughput.

### [Loop Agents](https://github.com/google/adk-docs/blob/main/docs/agents/workflow-agents/loop-agents.md)
Iterate over agents repeatedly with termination conditions - perfect for refinement workflows.

---

## Tools

Extend agent capabilities with tools and function calling.

### [Tools Overview](https://github.com/google/adk-docs/blob/main/docs/tools/index.md)
Introduction to tools in ADK - giving agents the ability to take actions.

### [Function Tools](https://github.com/google/adk-docs/blob/main/docs/tools/function-tools.md)
Convert Python functions into tools that agents can call with automatic schema generation.

### [Built-in Tools](https://github.com/google/adk-docs/blob/main/docs/tools/built-in-tools.md)
Pre-built tools for Google Search, code execution, and other common tasks.

### [Google Cloud Tools](https://github.com/google/adk-docs/blob/main/docs/tools/google-cloud-tools.md)
Integration with Google Cloud services like BigQuery, Cloud Storage, and more.

### [OpenAPI Integration](https://github.com/google/adk-docs/blob/main/docs/tools/openapi-tools.md)
Automatically generate tools from OpenAPI specifications for REST API integration.

### [Model Context Protocol Tools](https://github.com/google/adk-docs/blob/main/docs/tools/mcp-tools.md)
Use MCP tools to extend agent capabilities with external services.

### [Third Party Tools](https://github.com/google/adk-docs/blob/main/docs/tools/third-party-tools.md)
Integration guides for popular third-party tools and services.

### [Authenticating with Tools](https://github.com/google/adk-docs/blob/main/docs/tools/authentication.md)
Securely authenticate tools that require API keys or OAuth credentials.

---

## Deployment

Deploy your agents to production environments.

### [Deploying Your Agent](https://github.com/google/adk-docs/blob/main/docs/deploy/index.md)
Overview of deployment options and best practices.

### [Deploy to Cloud Run](https://github.com/google/adk-docs/blob/main/docs/deploy/cloud-run.md)
Deploy agents as serverless containers on Google Cloud Run.

### [Deploy to Vertex AI Agent Engine](https://github.com/google/adk-docs/blob/main/docs/deploy/agent-engine.md)
Deploy to Vertex AI Agent Engine for enterprise-grade agent management.

### [Deploy to GKE](https://github.com/google/adk-docs/blob/main/docs/deploy/gke.md)
Deploy agents to Google Kubernetes Engine for full control over infrastructure.

---

## Sessions & State

Manage conversational context and data flow.

### [Introduction to Conversational Context: Session, State, and Memory](https://github.com/google/adk-docs/blob/main/docs/sessions/index.md)
Overview of how ADK manages conversational context across turns.

### [Session: Tracking Individual Conversations](https://github.com/google/adk-docs/blob/main/docs/sessions/session.md)
Create and manage sessions to track individual user conversations.

### [State: The Session's Scratchpad](https://github.com/google/adk-docs/blob/main/docs/sessions/state.md)
Use session state as a key-value store for passing data between agents.

### [Memory: Long-Term Knowledge with MemoryService](https://github.com/google/adk-docs/blob/main/docs/sessions/memory.md)
Implement long-term memory for agents to remember information across sessions.

---

## Streaming

Real-time streaming and bi-directional communication.

### [Bidi-streaming (Live) in ADK](https://github.com/google/adk-docs/blob/main/docs/streaming/index.md)
Overview of bidirectional streaming capabilities in ADK.

### [Streaming Quickstarts Overview](https://github.com/google/adk-docs/blob/main/docs/get-started/streaming/index.md)
Quick start guides for streaming functionality.

### [Quickstart (Streaming / Python)](https://github.com/google/adk-docs/blob/main/docs/get-started/streaming/quickstart-streaming.md)
Build a streaming agent in Python with real-time responses.

### [Quickstart (Streaming / Java)](https://github.com/google/adk-docs/blob/main/docs/get-started/streaming/quickstart-streaming-java.md)
Build a streaming agent in Java with real-time responses.

### [Configuring Streaming Behaviour](https://github.com/google/adk-docs/blob/main/docs/streaming/configuration.md)
Configure streaming parameters like buffer size, timeout, and more.

### [Custom Audio Streaming app (SSE)](https://github.com/google/adk-docs/blob/main/docs/streaming/custom-streaming.md)
Build custom audio streaming applications using Server-Sent Events.

### [Custom Audio Streaming app (WebSocket)](https://github.com/google/adk-docs/blob/main/docs/streaming/custom-streaming-ws.md)
Build custom audio streaming applications using WebSockets.

### [Streaming Tools](https://github.com/google/adk-docs/blob/main/docs/streaming/streaming-tools.md)
Tools designed specifically for streaming scenarios.

### [ADK Bidi-streaming Development Guide: Part 1 - Introduction](https://github.com/google/adk-docs/blob/main/docs/streaming/dev-guide/part1.md)
In-depth guide to building bidirectional streaming applications.

---

## Advanced Topics

Deep dives into advanced ADK features.

### [Context](https://github.com/google/adk-docs/blob/main/docs/context/index.md)
Understand InvocationContext and how it flows through agent execution.

### [Events](https://github.com/google/adk-docs/blob/main/docs/events/index.md)
Work with events for fine-grained control over agent execution.

### [Artifacts](https://github.com/google/adk-docs/blob/main/docs/artifacts/index.md)
Manage artifacts like files, images, and structured data in agent workflows.

### [Runtime](https://github.com/google/adk-docs/blob/main/docs/runtime/index.md)
Configure the ADK runtime environment.

### [Runtime Configuration](https://github.com/google/adk-docs/blob/main/docs/runtime/runconfig.md)
Advanced runtime configuration options.

### [Model Context Protocol (MCP)](https://github.com/google/adk-docs/blob/main/docs/mcp/index.md)
Learn about the Model Context Protocol for tool integration.

---

## Callbacks & Observability

Monitor and customize agent behavior.

### [Callbacks: Observe, Customize, and Control Agent Behavior](https://github.com/google/adk-docs/blob/main/docs/callbacks/index.md)
Introduction to callbacks for observing and controlling agent execution.

### [Types of Callbacks](https://github.com/google/adk-docs/blob/main/docs/callbacks/types-of-callbacks.md)
Different callback types and when to use each one.

### [Design Patterns and Best Practices for Callbacks](https://github.com/google/adk-docs/blob/main/docs/callbacks/design-patterns-and-best-practices.md)
Proven patterns for implementing effective callbacks.

### [Agent Observability with Phoenix](https://github.com/google/adk-docs/blob/main/docs/observability/phoenix.md)
Integrate Phoenix for agent observability and debugging.

### [Agent Observability with Arize AX](https://github.com/google/adk-docs/blob/main/docs/observability/arize-ax.md)
Use Arize AX for production monitoring and observability.

---

## Safety & Evaluation

Ensure agent safety and quality.

### [Safety & Security for AI Agents](https://github.com/google/adk-docs/blob/main/docs/safety/index.md)
Best practices for building safe and secure AI agents.

### [Why Evaluate Agents](https://github.com/google/adk-docs/blob/main/docs/evaluate/index.md)
Importance of agent evaluation and testing strategies.

---

## Community & Tutorials

Learn from examples and connect with the community.

### [ADK Tutorials!](https://github.com/google/adk-docs/blob/main/docs/tutorials/index.md)
Collection of tutorials for learning ADK patterns.

### [Build Your First Intelligent Agent Team: A Progressive Weather Bot with ADK](https://github.com/google/adk-docs/blob/main/docs/tutorials/agent-team.md)
Step-by-step tutorial building a multi-agent weather bot.

### [Community Resources](https://github.com/google/adk-docs/blob/main/docs/community.md)
Links to community forums, discussions, and resources.

### [Contributing Guide](https://github.com/google/adk-docs/blob/main/docs/contributing-guide.md)
How to contribute to the ADK project on GitHub.

---

## API Reference

### [API Reference](https://github.com/google/adk-docs/blob/main/docs/api-reference/index.md)
Complete API reference for all ADK components.

### [Python API Reference](https://github.com/google/adk-docs/blob/main/docs/api-reference/python/)
Detailed Python API documentation with all classes, methods, and parameters.

---

## Quick Reference by Use Case

### I want to...

**Build a basic agent:**
- Start: [Quickstart](https://github.com/google/adk-docs/blob/main/docs/get-started/quickstart.md)
- Learn: [LLM Agent](https://github.com/google/adk-docs/blob/main/docs/agents/llm-agents.md)

**Add tools to my agent:**
- Start: [Function Tools](https://github.com/google/adk-docs/blob/main/docs/tools/function-tools.md)
- Explore: [Built-in Tools](https://github.com/google/adk-docs/blob/main/docs/tools/built-in-tools.md)

**Build a multi-agent system:**
- Start: [Multi-Agent Systems](https://github.com/google/adk-docs/blob/main/docs/agents/multi-agents.md)
- Learn: [Workflow Agents](https://github.com/google/adk-docs/blob/main/docs/agents/workflow-agents/index.md)

**Deploy to production:**
- Start: [Deploying Your Agent](https://github.com/google/adk-docs/blob/main/docs/deploy/index.md)
- Choose: [Cloud Run](https://github.com/google/adk-docs/blob/main/docs/deploy/cloud-run.md) or [Vertex AI](https://github.com/google/adk-docs/blob/main/docs/deploy/agent-engine.md)

**Pass data between agents:**
- Learn: [State: The Session's Scratchpad](https://github.com/google/adk-docs/blob/main/docs/sessions/state.md)
- See: [State Management Guide](./state_management.md)

**Use different models:**
- Configure: [Using Different Models with ADK](https://github.com/google/adk-docs/blob/main/docs/agents/models.md)
- See: [Model Selection Guide](./model_selection.md)

**Build custom orchestration:**
- Start: [Custom Agents](https://github.com/google/adk-docs/blob/main/docs/agents/custom-agents.md)
- See: [Advanced Patterns Guide](./advanced_patterns.md)

---

## Additional Resources

- [Model Selection Guide](./model_selection.md) - Choose the right model for your use case
- [Multi-Agent Patterns](./multi_agent_patterns.md) - Design patterns for multi-agent systems
- [State Management Guide](./state_management.md) - Manage data flow between agents
- [Advanced Patterns Guide](./advanced_patterns.md) - Custom agents and complex orchestration
- [Main README](../README.md) - Google ADK Skill overview

---

## Note on Documentation

All links point to the official Google ADK documentation on GitHub. The documentation is actively maintained and may be updated with new features and examples. Always refer to the official docs for the most current information.

For local reference, see:
- `google_adk_python/llms.txt` - Summarized Python documentation
- `google_adk_python/llms-full.txt` - Complete Python documentation with detailed examples
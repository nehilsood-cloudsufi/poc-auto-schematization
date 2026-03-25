# Model Selection Guide for Google ADK

This guide helps you choose and configure the right model for your Google ADK agents. All examples are Python-only.

**Reference:** `google_adk_python/llms-full.txt` lines 1338-1999

## Table of Contents

- [Available Gemini Models](#available-gemini-models)
- [Model Comparison](#model-comparison)
- [Google AI Studio Setup](#google-ai-studio-setup)
- [Vertex AI Setup](#vertex-ai-setup)
- [LiteLLM for Other Models](#litellm-for-other-models)
- [Ollama for Local Models](#ollama-for-local-models)
- [Environment Variables Reference](#environment-variables-reference)

---

## Available Gemini Models

Google provides several Gemini models optimized for different use cases.

### gemini-2.5-flash

**Best For:** Most applications, rapid prototyping, high-throughput scenarios

**Characteristics:**
- Fast response times
- Cost-effective
- Good balance of capability and speed
- Suitable for production workloads

**Example:**
```python
from google.adk.agents import LlmAgent

agent = LlmAgent(
    name="fast_agent",
    model="gemini-2.5-flash",  # Fast and efficient
    instruction="You are a helpful assistant."
)
```

### gemini-2.5-pro

**Best For:** Complex reasoning, detailed analysis, high-quality outputs

**Characteristics:**
- More capable than Flash
- Better at complex tasks
- Slower and more expensive than Flash
- Recommended for tasks requiring deep understanding

**Example:**
```python
agent = LlmAgent(
    name="pro_agent",
    model="gemini-2.5-pro",  # More powerful
    instruction="You are an expert analyst. Provide detailed insights."
)
```

### gemini-3-pro-preview

**Best For:** Cutting-edge features, testing new capabilities

**Characteristics:**
- Latest model with newest features
- Preview version - may have different availability
- Check documentation for specific capabilities
- May have quota limitations

**Example:**
```python
agent = LlmAgent(
    name="preview_agent",
    model="gemini-3-pro-preview",
    instruction="Use the latest Gemini capabilities."
)
```

---

## Model Comparison

| Feature | gemini-2.5-flash | gemini-2.5-pro | gemini-3-pro-preview |
|---------|------------------|----------------|----------------------|
| **Speed** | ⚡⚡⚡ Very Fast | ⚡⚡ Fast | ⚡⚡ Fast |
| **Cost** | 💰 Low | 💰💰 Medium | 💰💰 Medium |
| **Reasoning** | ⭐⭐⭐ Good | ⭐⭐⭐⭐ Excellent | ⭐⭐⭐⭐⭐ Best |
| **Use Case** | General purpose, production | Complex tasks, analysis | Experimental, latest features |
| **Recommended For** | Most applications | Detailed work | Testing new capabilities |

### Choosing the Right Model

**Use gemini-2.5-flash when:**
- Building prototypes or MVPs
- Need fast response times
- Cost is a concern
- Task doesn't require deep reasoning
- High request volume

**Use gemini-2.5-pro when:**
- Task requires complex reasoning
- Output quality is critical
- Need detailed analysis or synthesis
- Working with complex multi-step problems
- Accuracy is more important than speed

**Use gemini-3-pro-preview when:**
- Testing newest Gemini features
- Exploring cutting-edge capabilities
- Need specific features only in preview
- Willing to handle preview limitations

---

## Google AI Studio Setup

**Reference:** llms-full.txt lines 1387-1403

Google AI Studio is the easiest way to get started with Gemini. Best for rapid prototyping and development.

### 1. Get API Key

1. Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create a new API key
3. Copy the key

### 2. Set Environment Variables

```bash
# Set your API key
export GOOGLE_API_KEY="your_api_key_here"

# Explicitly use Google AI Studio (not Vertex AI)
export GOOGLE_GENAI_USE_VERTEXAI=FALSE
```

### 3. Install Dependencies

```bash
pip install google-adk
```

### 4. Use in Code

```python
from google.adk.agents import LlmAgent

# No additional configuration needed - uses GOOGLE_API_KEY from environment
agent = LlmAgent(
    name="ai_studio_agent",
    model="gemini-2.5-flash",
    instruction="You are a helpful assistant using Google AI Studio."
)
```

### Alternative: Explicit Client Configuration

```python
from google.genai import Client

# Create client with API key
client = Client(api_key="your_api_key_here")

# Use with agent (if needed for custom configuration)
```

---

## Vertex AI Setup

**Reference:** llms-full.txt lines 1404-1432

Recommended for production applications. Provides enterprise-grade features, security, and compliance.

### 1. Prerequisites

- Google Cloud Project
- Billing enabled
- Vertex AI API enabled

### 2. Authenticate

```bash
# Login and set up Application Default Credentials (ADC)
gcloud auth application-default login
```

### 3. Set Environment Variables

```bash
# Set your Google Cloud project
export GOOGLE_CLOUD_PROJECT="your-project-id"

# Set your Vertex AI location (region)
export GOOGLE_CLOUD_LOCATION="us-central1"  # or your preferred region

# Explicitly use Vertex AI
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
```

### 4. Install Dependencies

```bash
pip install google-adk
```

### 5. Use in Code

```python
from google.adk.agents import LlmAgent

# Uses Vertex AI automatically via environment variables
agent = LlmAgent(
    name="vertex_agent",
    model="gemini-2.5-flash",  # Same model names work
    instruction="You are a helpful assistant using Vertex AI."
)
```

### Advanced: Generation Configuration

```python
from google.adk.agents import LlmAgent
from google.genai import types

agent = LlmAgent(
    name="configured_agent",
    model="gemini-2.5-pro",
    instruction="You are a helpful assistant.",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.7,  # 0.0-1.0, higher = more creative
        max_output_tokens=2048,  # Maximum response length
        top_p=0.95,  # Nucleus sampling
        top_k=40  # Top-k sampling
    )
)
```

---

## LiteLLM for Other Models

**Reference:** llms-full.txt lines 1493-1574

Use LiteLLM to access models from OpenAI, Anthropic, Cohere, and 100+ other providers.

### 1. Install LiteLLM

```bash
pip install litellm
```

### 2. Set Provider API Keys

```bash
# For OpenAI
export OPENAI_API_KEY="your_openai_key"

# For Anthropic (direct API, not Vertex)
export ANTHROPIC_API_KEY="your_anthropic_key"

# For other providers, see: https://docs.litellm.ai/docs/providers
```

### 3. Use with ADK

```python
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

# OpenAI GPT-4o
openai_agent = LlmAgent(
    model=LiteLlm(model="openai/gpt-4o"),
    name="openai_agent",
    instruction="You are powered by GPT-4o."
)

# Anthropic Claude (via direct API)
claude_agent = LlmAgent(
    model=LiteLlm(model="anthropic/claude-3-haiku-20240307"),
    name="claude_agent",
    instruction="You are powered by Claude Haiku."
)
```

### Model String Format

LiteLLM uses the format: `provider/model_name`

Examples:
- `openai/gpt-4o`
- `anthropic/claude-3-sonnet-20240229`
- `cohere/command-r-plus`
- `together_ai/meta-llama/Llama-3-70b-chat-hf`

---

## Ollama for Local Models

**Reference:** llms-full.txt lines 1576-1741

Run open-source models locally using Ollama.

### 1. Install Ollama

```bash
# Visit https://ollama.com/ for installation instructions
```

### 2. Pull a Model

```bash
# Choose a model with tool support
ollama pull mistral-small3.1
```

### 3. Verify Tool Support

```bash
ollama show mistral-small3.1

# Look for 'tools' in Capabilities section
```

### 4. Set Environment Variable

```bash
# Point to local Ollama server
export OLLAMA_API_BASE="http://localhost:11434"
```

### 5. Use with ADK (ollama_chat provider)

```python
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

agent = Agent(
    model=LiteLlm(model="ollama_chat/mistral-small3.1"),
    name="local_agent",
    instruction="You are running locally via Ollama.",
    tools=[...]
)
```

**Important:** Use `ollama_chat` provider (not `ollama`) to avoid infinite tool call loops.

### Alternative: OpenAI-Compatible API

```bash
# Set OpenAI-compatible endpoint
export OPENAI_API_BASE="http://localhost:11434/v1"
export OPENAI_API_KEY="anything"  # Ollama doesn't require key
```

```python
agent = Agent(
    model=LiteLlm(model="openai/mistral-small3.1"),
    name="local_agent_openai",
    instruction="You are running locally via Ollama."
)
```

### Debugging Ollama

```python
# Add debug logging
import litellm
litellm._turn_on_debug()

# Now run your agent - requests will be logged
```

### Model Selection for Ollama

**Recommended models with tool support:**
- `mistral-small3.1` - Good balance of size and capability
- `llama3.2` - Meta's latest, good performance
- Check [Ollama website](https://ollama.com/search?c=tools) for updated list

**Customizing Model Templates:**

```bash
# Export model file
ollama show --modelfile llama3.2 > model_file_to_modify

# Edit the template to prevent infinite tool loops

# Create new model
ollama create llama3.2-modified -f model_file_to_modify
```

---

## Environment Variables Reference

### Google AI Studio

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `GOOGLE_API_KEY` | Yes | Your API key from AI Studio | `AIza...` |
| `GOOGLE_GENAI_USE_VERTEXAI` | No | Set to FALSE for AI Studio | `FALSE` |

### Vertex AI

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `GOOGLE_CLOUD_PROJECT` | Yes | Your GCP project ID | `my-project-123` |
| `GOOGLE_CLOUD_LOCATION` | Yes | Vertex AI region | `us-central1` |
| `GOOGLE_GENAI_USE_VERTEXAI` | Yes | Set to TRUE for Vertex AI | `TRUE` |

### LiteLLM (OpenAI)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `OPENAI_API_KEY` | Yes | Your OpenAI API key | `sk-...` |

### LiteLLM (Anthropic)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key | `sk-ant-...` |

### Ollama

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `OLLAMA_API_BASE` | Yes | Ollama server URL | `http://localhost:11434` |

### Ollama (OpenAI-compatible)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `OPENAI_API_BASE` | Yes | Ollama OpenAI endpoint | `http://localhost:11434/v1` |
| `OPENAI_API_KEY` | Yes | Any value (not validated) | `anything` |

---

## Complete Setup Examples

### Example 1: Google AI Studio (Quick Start)

```bash
# Set API key
export GOOGLE_API_KEY="your_key_here"
export GOOGLE_GENAI_USE_VERTEXAI=FALSE

# Install
pip install google-adk

# Create .env file
echo "GOOGLE_API_KEY=your_key_here" > .env
echo "GOOGLE_GENAI_USE_VERTEXAI=FALSE" >> .env
```

```python
# agent.py
from google.adk.agents import LlmAgent
from google.adk import Runner

agent = LlmAgent(
    name="my_agent",
    model="gemini-2.5-flash",
    instruction="You are a helpful assistant."
)

runner = Runner(root_agent=agent)
result = runner.run(user_message="Hello!")
print(result)
```

### Example 2: Vertex AI (Production)

```bash
# Authenticate
gcloud auth application-default login

# Set environment
export GOOGLE_CLOUD_PROJECT="my-production-project"
export GOOGLE_CLOUD_LOCATION="us-central1"
export GOOGLE_GENAI_USE_VERTEXAI=TRUE

# Install
pip install google-adk
```

```python
# agent.py
from google.adk.agents import LlmAgent
from google.genai import types

agent = LlmAgent(
    name="production_agent",
    model="gemini-2.5-pro",
    instruction="You are a production assistant.",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.2,  # More deterministic for production
        max_output_tokens=1024
    )
)
```

### Example 3: Ollama (Local Development)

```bash
# Start Ollama
ollama serve

# Pull model (in another terminal)
ollama pull mistral-small3.1

# Set environment
export OLLAMA_API_BASE="http://localhost:11434"

# Install
pip install google-adk litellm
```

```python
# agent.py
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

agent = Agent(
    model=LiteLlm(model="ollama_chat/mistral-small3.1"),
    name="local_dev_agent",
    instruction="You are running locally for development.",
    tools=[...]
)
```

---

## Best Practices

### 1. Start with Google AI Studio
- Use for prototyping and development
- Easy setup with just an API key
- Switch to Vertex AI for production

### 2. Use Vertex AI for Production
- Enterprise security and compliance
- Better quotas and SLAs
- Integration with Google Cloud services

### 3. Tune Generation Parameters
- Start with defaults
- Adjust temperature for creativity vs consistency
- Set max_output_tokens to control costs

### 4. Test Locally with Ollama
- Develop offline without API costs
- Faster iteration during development
- Good for testing agent logic before cloud deployment

### 5. Monitor Costs
- Flash is more cost-effective than Pro
- Set max_output_tokens appropriately
- Consider caching strategies for repeated queries

---

## Additional Resources

- [Advanced Patterns Guide](./advanced_patterns.md)
- [Multi-Agent Patterns](./multi_agent_patterns.md)
- [State Management Guide](./state_management.md)
- [Main README](../README.md)
- [Google AI Studio](https://aistudio.google.com)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [LiteLLM Providers](https://docs.litellm.ai/docs/providers)
- [Ollama Models](https://ollama.com/library)
# MCP Integration Testing

This directory contains tests to validate that the Data Commons MCP server works correctly with Google ADK in your environment.

## Test Results (Verified)

All tests pass as of the initial integration:

| Test File | Status | Description |
|-----------|--------|-------------|
| test_mcp_connection.py | PASS | Basic MCP server lifecycle |
| test_mcp_tools.py | PASS | ADK MCPToolset integration |
| test_dc_query_agent.py | PASS | DC Query Agent with MCP |
| test_mcp_server_manager.py | PASS | Production MCPServerManager |
| test_pipeline_pattern.py | PASS | Pipeline integration patterns |

## Prerequisites

### 1. Install datacommons-mcp

```bash
pip install datacommons-mcp
```

### 2. Get a Data Commons API Key

1. Go to https://apikeys.datacommons.org/
2. Sign in with your Google account
3. Create a new API key
4. Set it in your environment:

```bash
export DC_API_KEY="your-api-key-here"
```

Or add to your `.env` file:
```
DC_API_KEY=your-api-key-here
```

### 3. Verify google-adk is installed

```bash
pip show google-adk
```

## Running Tests

### Test 1: Basic MCP Connection

Tests that the MCP server can start, respond to health checks, and stop cleanly.

```bash
cd /Users/nehilsood/work/poc-auto-schematization
python tests/mcp/test_mcp_connection.py
```

### Test 2: MCP Tools via ADK

Tests using MCP tools (search_indicators, get_observations) through ADK's MCPToolset.

```bash
cd /Users/nehilsood/work/poc-auto-schematization
python tests/mcp/test_mcp_tools.py
```

### Test 3: DC Query Agent

Tests the full DC Query Agent that wraps MCP tools in an LLM agent.

```bash
cd /Users/nehilsood/work/poc-auto-schematization
python tests/mcp/test_dc_query_agent.py
```

## Expected Output

### Successful test_mcp_connection.py output:
```
[PASS] datacommons-mcp package installed
[PASS] DC_API_KEY environment variable set
[PASS] MCP server started successfully
[PASS] Health check passed
[PASS] MCP server stopped cleanly

All tests passed!
```

### Successful test_mcp_tools.py output:
```
[PASS] MCPToolset created successfully
[PASS] search_indicators tool available
[PASS] get_observations tool available
[PASS] search_indicators returned results for "population California"

All tests passed!
```

## Troubleshooting

### "datacommons-mcp not found"
```bash
pip install datacommons-mcp
```

### "DC_API_KEY not set"
Get an API key from https://apikeys.datacommons.org/ and set it:
```bash
export DC_API_KEY="your-key"
```

### "MCP server failed to start"
1. Check if port 3000 is already in use: `lsof -i :3000`
2. Try a different port: `MCP_PORT=3001 python test_mcp_connection.py`

### "google-adk import error"
```bash
pip install google-adk
```

## File Structure

```
tests/mcp/
├── __init__.py                  # Package marker
├── README.md                    # This file
├── test_mcp_connection.py       # Basic MCP server connectivity test
├── test_mcp_tools.py            # MCP tools via ADK MCPToolset
├── test_dc_query_agent.py       # Full DC Query Agent test
├── test_mcp_server_manager.py   # Production MCPServerManager tests
├── test_pipeline_pattern.py     # Pipeline integration patterns
├── test_statvar_discovery.py    # StatVar discovery tests
├── test_full_integration.py     # Full integration tests
└── sample_output/               # Test outputs
```

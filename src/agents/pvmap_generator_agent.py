"""
PVMAP Generator Agent using ADK LlmAgent with output_schema.

This agent uses ADK's structured output feature to guarantee valid JSON
responses that can be deterministically converted to CSV.

Key ADK features used:
- output_schema: Pydantic model for structured output
- output_key: Stores output in session state automatically
- Instruction templating with {var?} for optional state variables
"""

import os
from pathlib import Path
from typing import Optional

from google.adk.agents import LlmAgent

from src.agents.pvmap_generation.schemas import PVMAPOutput


# ============================================================================
# Generator Instruction (includes structured output guidance)
# ============================================================================

PVMAP_GENERATOR_INSTRUCTION = """You are an expert Data Commons PVMAP generator.

Your task: Generate a Property-Value Map (PVMAP) that transforms input data columns into Data Commons StatVarObservations.

## Data Context (from Sampling Analysis)
{skeleton_summary}

## Schema Examples
{schema_examples}

## Sampled Data
{sampled_data}

## Metadata Configuration
{metadata}

## Discovered StatVars (from Data Commons)
{statvar_summary}

{mcp_tools_instruction}

## Previous Feedback (if retrying)
{error_feedback}

---

# CRITICAL RULES

## 1. Detect Pre-Formatted Data Commons Data

**Check if data is ALREADY in Data Commons format:**
- Has `variableMeasured` column with DCIDs like `dcid:Count_Person_Female`
- Has `observationAbout` column with place DCIDs like `country/USA`, `geoId/06`
- Has `observationDate` column with dates like `2020`, `2020-01-15`
- Has `value` column with measurements

**If pre-formatted:** Set `format_detected: "pre-formatted"` and use passthrough mappings where value is the literal string [DATA] or [NUMBER]:
```
observationAbout -> [DATA]
observationDate -> [DATA]
variableMeasured -> [DATA]
value -> [NUMBER]
```

## 2. Key Matching Rules

- **EXACT MATCH**: Keys must match column headers or cell values EXACTLY (case-sensitive)
- **Column:Value syntax**: Use `COLUMN:VALUE` for specific cell mappings
- **Quote special characters**: Keys with commas need quotes: `"ICD-10:#Heart"`

## 3. Required Properties

Every PVMAP must have mappings for:
- `observationAbout` - Geographic entity (from place column)
- `observationDate` - Time reference (from date/year column)
- `value` - The measurement value (from numeric column)

StatVar properties (for raw data):
- `populationType` - What is being measured (Person, Household, etc.)
- `measuredProperty` - What property (count, income, rate, etc.)
- `statType` - Type of statistic (measuredValue, median, etc.)

## 4. Value Placeholders (Use EXACTLY as shown in JSON)

In the JSON output, use these EXACT strings as values:
- [DATA] - Pass through the cell value as string (will become curly-brace Data)
- [NUMBER] - Pass through as numeric value (will become curly-brace Number)
- `dcid:XXXXX` - Data Commons DCID reference (use as-is)

## 5. Error Correction (if retrying)

If error_feedback is present, it contains analysis of what went wrong on the previous attempt
(either validation failure or low quality). Follow the specific fixes provided.

**How to interpret value patterns in feedback:**
- `state_code` pattern (e.g., 'AL', 'CA', 'TX') → State column not mapped. Fix: Map state codes to DCIDs or use State FIPS column instead
- `place_name` pattern (e.g., 'ALBERTVILLE CITY') → Place names need DCID resolution. Fix: Use FIPS codes or add dcid:geoId/ prefix
- `numeric_id` pattern (e.g., '10000500879') → ID column not in PVMAP keys. Check if NCESID, SCHID, or similar column is mapped
- `year` pattern (e.g., '2010', '2020') → Year column not mapped to observationDate
- `fips_code` pattern (e.g., '01', '06') → FIPS codes may need zero-padding: dcid:geoId/[DATA]
- `enum` pattern → Categorical column values need explicit mappings

**Fix strategy:**
1. Read the feedback carefully for specific fixes
2. Focus on the "High-Impact Fixes" section
3. Ensure keys match EXACT column headers (case-sensitive)
4. Verify required properties are mapped (observationAbout, observationDate, value)
5. If pattern issues are mentioned, fix ALL affected rows

IMPORTANT: Apply the specific fixes from the feedback. Do not repeat previous mistakes.

---

# OUTPUT FORMAT

Return a JSON object with this structure:

```json
{
  "format_detected": "raw",
  "pvmap_rows": [
    {
      "key": "Year",
      "mappings": [
        {"property": "observationDate", "value": "[DATA]"}
      ]
    },
    {
      "key": "State FIPS",
      "mappings": [
        {"property": "observationAbout", "value": "dcid:geoId/[DATA]"}
      ]
    },
    {
      "key": "Population",
      "mappings": [
        {"property": "value", "value": "[NUMBER]"},
        {"property": "populationType", "value": "dcid:Person"},
        {"property": "measuredProperty", "value": "dcid:count"},
        {"property": "statType", "value": "dcid:measuredValue"}
      ]
    }
  ],
  "validation_notes": "Brief notes about mapping decisions...",
  "confidence": "high"
}
```

**IMPORTANT:**
- Each key should match input data EXACTLY (case-sensitive)
- Each mapping has exactly two fields: "property" and "value"
- Use dcid: prefix for Data Commons identifiers
- Use [DATA] for string pass-through, [NUMBER] for numeric values
- If skeleton_summary identifies dimension columns, ensure they are properly mapped
- If discovered StatVars are provided, use HIGH confidence matches directly and reference MEDIUM matches for naming conventions

Generate the PVMAP now."""


def create_pvmap_generator(
    model: str = "gemini-2.5-flash",
    name: str = "PVMAPGenerator",
    enable_mcp: bool = False,
    mcp_url: Optional[str] = None,
) -> LlmAgent:
    """
    Create PVMAP generator agent with structured output.

    This agent uses ADK's output_schema feature to guarantee structured JSON
    output that matches the PVMAPOutput Pydantic model.

    When MCP is enabled, the generator gets direct access to Data Commons
    MCP tools (search_indicators, get_observations) for live verification.

    Args:
        model: Gemini model to use (default: gemini-2.5-flash)
        name: Agent name (default: PVMAPGenerator)
        enable_mcp: Enable MCP tools on the generator (default: False)
        mcp_url: MCP server URL (required if enable_mcp=True)

    Returns:
        Configured LlmAgent with output_schema

    State Inputs (read from session.state via instruction templating):
        - schema_examples: str - Schema example content
        - sampled_data: str - Sampled CSV data
        - metadata: str - Metadata configuration
        - skeleton_summary: str (optional) - Data context from SamplingAgent
        - statvar_summary: str (optional) - Discovered StatVars from MCP
        - mcp_tools_instruction: str (optional) - MCP tool usage guidance
        - error_feedback: str (optional) - Feedback from validation failure or quality issues

    State Outputs (written via output_key):
        - pvmap_output: dict - Structured PVMAP output (JSON dict matching PVMAPOutput)
    """
    # Get model from environment override if available
    model = os.getenv("PVMAP_GENERATOR_MODEL", model)

    # Build tools list
    tools = []
    if enable_mcp and mcp_url:
        from src.data_commons.api.mcp_toolset_factory import create_dc_mcp_toolset
        mcp_toolset = create_dc_mcp_toolset(mcp_url=mcp_url)
        tools.append(mcp_toolset)

    kwargs = dict(
        name=name,
        model=model,
        instruction=PVMAP_GENERATOR_INSTRUCTION,
        output_schema=PVMAPOutput,
        output_key="pvmap_output",
    )

    if tools:
        kwargs["tools"] = tools

    return LlmAgent(**kwargs)


def create_pvmap_generator_without_schema(
    model: str = "gemini-2.5-flash",
    name: str = "PVMAPGenerator",
) -> LlmAgent:
    """
    Create PVMAP generator agent WITHOUT output_schema for fallback.

    Some models may not support structured output. This variant uses
    the same instruction but allows free-form output that must be
    parsed manually.

    Args:
        model: Gemini model to use
        name: Agent name

    Returns:
        Configured LlmAgent without output_schema
    """
    model = os.getenv("PVMAP_GENERATOR_MODEL", model)

    return LlmAgent(
        name=name,
        model=model,
        instruction=PVMAP_GENERATOR_INSTRUCTION,
        output_key="pvmap_raw_output",  # Store raw output for parsing
    )


# ============================================================================
# Module exports
# ============================================================================

__all__ = [
    'create_pvmap_generator',
    'create_pvmap_generator_without_schema',
    'PVMAP_GENERATOR_INSTRUCTION',
]

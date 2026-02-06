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
from google.genai import types

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

## Discovered StatVars (Reference Only - from MCP)
{statvar_summary}

## Previous Validation Error Feedback (if retrying after validation failure)
{error_feedback}

## Previous Quality Improvement Feedback (if retrying after low quality score)
{quality_feedback}

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

### If error_feedback is present (validation failed):
The error_feedback contains **Unmapped Value Analysis** with detected patterns.

**How to interpret value patterns:**
- `state_code` pattern (e.g., 'AL', 'CA', 'TX') → State column not mapped. Fix: Map state codes to DCIDs or use State FIPS column instead
- `place_name` pattern (e.g., 'ALBERTVILLE CITY') → Place names need DCID resolution. Fix: Use FIPS codes or add dcid:geoId/ prefix
- `numeric_id` pattern (e.g., '10000500879') → ID column not in PVMAP keys. Check if NCESID, SCHID, or similar column is mapped
- `year` pattern (e.g., '2010', '2020') → Year column not mapped to observationDate
- `fips_code` pattern (e.g., '01', '06') → FIPS codes may need zero-padding: dcid:geoId/{Data:02d}
- `enum` pattern → Categorical column values need explicit mappings

**Fix strategy:**
1. Identify which column the pattern values come from (check the sampled data)
2. Add that column to PVMAP keys with appropriate mapping
3. Ensure keys match EXACT column headers (case-sensitive)
4. Verify required properties are mapped (observationAbout, observationDate, value)

### If quality_feedback is present (validation passed but low quality):
The previous PVMAP passed validation but has low accuracy compared to expected output:
1. Read the quality feedback carefully for specific fixes
2. Focus on the "High-Impact Fixes" section
3. If pattern issues are mentioned, fix ALL affected rows
4. Pay attention to any diff showing expected vs actual mappings

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
- If discovered StatVars are provided, ONLY use them if they EXACTLY match your data

Generate the PVMAP now."""


def create_pvmap_generator(
    model: str = "gemini-2.5-flash",
    name: str = "PVMAPGenerator",
) -> LlmAgent:
    """
    Create PVMAP generator agent with structured output.

    This agent uses ADK's output_schema feature to guarantee structured JSON
    output that matches the PVMAPOutput Pydantic model.

    Args:
        model: Gemini model to use (default: gemini-2.5-flash)
        name: Agent name (default: PVMAPGenerator)

    Returns:
        Configured LlmAgent with output_schema

    State Inputs (read from session.state via instruction templating):
        - schema_examples: str - Schema example content
        - sampled_data: str - Sampled CSV data
        - metadata: str - Metadata configuration
        - skeleton_summary: str (optional) - Data context from SamplingAgent
        - statvar_summary: str (optional) - Discovered StatVars from MCP
        - error_feedback: str (optional) - Error feedback from validation failure
        - quality_feedback: str (optional) - Feedback for quality improvement

    State Outputs (written via output_key):
        - pvmap_output: dict - Structured PVMAP output (JSON dict matching PVMAPOutput)
    """
    # Get model from environment override if available
    model = os.getenv("PVMAP_GENERATOR_MODEL", model)

    return LlmAgent(
        name=name,
        model=model,
        instruction=PVMAP_GENERATOR_INSTRUCTION,
        output_schema=PVMAPOutput,  # Enforces structured JSON output
        output_key="pvmap_output",  # Automatically saves to session state
    )


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

"""
Feedback Agent for ADK pipeline retry loop.

This LlmAgent analyzes validation errors and generates actionable feedback
for the next PVMAP generation attempt.

Key ADK features used:
- LlmAgent for intelligent error analysis
- output_key to store feedback in session state
- Instruction templating to read validation_error and pvmap_csv from state
"""

import os
from pathlib import Path

from google.adk.agents import LlmAgent


# ============================================================================
# Feedback Agent Instruction
# ============================================================================

FEEDBACK_AGENT_INSTRUCTION = """You are an error analysis expert for Data Commons PVMAP validation.

Your task: Analyze the validation error and provide SPECIFIC, ACTIONABLE feedback for the next generation attempt.

## Validation Error
{validation_error}

## Generated PVMAP CSV
```csv
{pvmap_csv}
```

## Original Sampled Data (Reference)
{sampled_data}

## Structure Warnings (if any)
{structure_warnings}

---

# ANALYSIS GUIDELINES

## 1. Identify Root Cause

Look for these common error patterns:

### Key Mismatch Errors
- "Key not found" → Key in PVMAP doesn't match column header exactly
- Check case sensitivity: "Year" vs "year" vs "YEAR"
- Check for whitespace: "Year " vs "Year"
- Check for special characters being escaped incorrectly

### Missing Required Properties
- "observationAbout not found" → No place column mapped
- "value not mapped" → Numeric column not mapped with [NUMBER]
- "observationDate not found" → Date/year column not mapped

### DCID Format Errors
- Missing "dcid:" prefix for Data Commons identifiers
- Wrong DCID format (e.g., "Person" should be "dcid:Person")
- Invalid DCID reference

### Column Mapping Errors
- Wrong column mapped to observationAbout (needs place/geo column)
- Wrong column mapped to observationDate (needs date/year column)
- Dimension column treated as value or vice versa

## 2. Provide Specific Fixes

Be CONCRETE and SPECIFIC:

**Instead of:** "Fix the key mapping"
**Say:** "Change key 'year' to 'Year' to match the exact column header in the data"

**Instead of:** "Add observationAbout mapping"
**Say:** "Add a mapping for the 'State FIPS' column with observationAbout property: key='State FIPS', property='observationAbout', value='dcid:geoId/[DATA]'"

## 3. Pattern Detection

Note if the error is SYSTEMATIC:
- All place mappings using wrong column
- All DCID values missing prefix
- Format detection wrong (treating pre-formatted as raw or vice versa)

---

# OUTPUT FORMAT

Provide your analysis in this structure:

1. **Root Cause**: What specific issue caused the validation failure

2. **Affected Rows**: Which PVMAP rows have the problem

3. **Specific Fix**: Exact changes needed (with concrete values)

4. **Pattern Issue**: Is this a systematic error affecting multiple rows?

5. **Corrected Example**: Show what the fixed row(s) should look like

Keep your response focused and actionable. The generator will read this feedback directly."""


def create_feedback_agent(
    model: str = "gemini-2.5-flash",
    name: str = "FeedbackAgent",
) -> LlmAgent:
    """
    Create feedback agent for error analysis between retry attempts.

    This agent analyzes validation failures and generates actionable
    feedback that gets injected into the next generation attempt.

    Args:
        model: Gemini model to use (default: gemini-2.5-flash)
        name: Agent name (default: FeedbackAgent)

    Returns:
        Configured LlmAgent for error analysis

    State Inputs (read via instruction templating):
        - validation_error: str - Error message from validation
        - pvmap_csv: str - Generated PVMAP CSV that failed
        - sampled_data: str - Original sampled data for reference
        - structure_warnings: str - Structure validation warnings

    State Outputs (written via output_key):
        - error_feedback: str - Actionable feedback for next attempt
    """
    # Get model from environment override if available
    model = os.getenv("FEEDBACK_AGENT_MODEL", model)

    return LlmAgent(
        name=name,
        model=model,
        instruction=FEEDBACK_AGENT_INSTRUCTION,
        output_key="error_feedback",  # Generator reads this on retry
    )


# ============================================================================
# Module exports
# ============================================================================

__all__ = [
    'create_feedback_agent',
    'FEEDBACK_AGENT_INSTRUCTION',
]

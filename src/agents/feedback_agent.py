"""
Unified Feedback Agent for ADK pipeline retry loop.

This LlmAgent analyzes both validation errors AND quality issues, generating
actionable feedback for the next PVMAP generation attempt.

Replaces the previous split between FeedbackAgent (error path) and
QualityFeedbackAgent (quality path) with a single agent that handles both.

Key ADK features used:
- LlmAgent for intelligent error/quality analysis
- output_key to store feedback in session state
- Instruction templating to read validation_error, quality metrics, and
  counter summary from state
"""

import os
from pathlib import Path

from google.adk.agents import LlmAgent


# ============================================================================
# Unified Feedback Agent Instruction
# ============================================================================

FEEDBACK_AGENT_INSTRUCTION = """You are an expert analyst for Data Commons PVMAP generation feedback.

Your task: Analyze the PVMAP's issues and provide SPECIFIC, ACTIONABLE feedback for the next generation attempt.

## Feedback Mode
{feedback_mode}

## Validation Error (if validation failed)
{validation_error}

## Quality Metrics (if validation passed but quality low)
Score: {quality_score}/100
{quality_metrics}

## Quality Issues (if validation passed but quality low)
{quality_diff_summary}

## Ground Truth Accuracy (if available)
{gt_score_section}

## Validation Processing Metrics (from stat_var_processor counters)
{validation_counter_summary}

## Generated PVMAP CSV
```csv
{pvmap_csv}
```

## Original Sampled Data (Reference)
{sampled_data}

## Structure Warnings (if any)
{structure_warnings}

## MCP Error Resolution Context (if available)
{mcp_resolved_context}

## Schema Domain Context
Category: {schema_category}

### Valid Properties & Values for this Domain
{schema_vocab_content}

## Data Structure Context (from sampling analysis)
{skeleton_summary}

## Generated StatVar Analysis (from validation output)
{validation_statvar_analysis}

## Key Match Report (PVMAP keys vs actual column headers)
{key_match_report}

---

# ANALYSIS GUIDELINES

## 1. Identify Root Cause

### If Validation Failed (error analysis)

Look for these common error patterns:

#### Key Mismatch Errors
- "Key not found" → Key in PVMAP doesn't match column header exactly
- Check case sensitivity: "Year" vs "year" vs "YEAR"
- Check for whitespace: "Year " vs "Year"
- Check for special characters being escaped incorrectly

#### Missing Required Properties
- "observationAbout not found" → No place column mapped
- "value not mapped" → Numeric column not mapped with [NUMBER]
- "observationDate not found" → Date/year column not mapped

#### DCID Format Errors
- Missing "dcid:" prefix for Data Commons identifiers
- Wrong DCID format (e.g., "Person" should be "dcid:Person")

#### Column Mapping Errors
- Wrong column mapped to observationAbout (needs place/geo column)
- Wrong column mapped to observationDate (needs date/year column)
- Dimension column treated as value or vice versa

### If Validation Passed but Quality Low (quality analysis)

Look at the heuristic score breakdown to identify weak areas:
- Low row coverage: Are there missing dimension mappings?
- Low property coverage: Are observationAbout/observationDate/value mapped?
- Low column coverage: Which data columns weren't mapped?
- Low format score: Are [DATA]/[NUMBER] placeholders used correctly?

If Ground Truth Accuracy scores are available, use them as a signal:
- Low node accuracy means many PVMAP rows don't match expected patterns
- Low PV accuracy means property-value pairs within rows are incorrect
- If PV ACCURACY LOW: cross-reference StatVar analysis with schema vocab for fixes
- If QUALITY LOW: focus on structural improvements (coverage, format)

### If PV Accuracy Low (feedback_mode mentions "PV ACCURACY LOW")

The PVMAP structure is OK but property-value pairs don't match expected patterns.
Use the Schema Domain Context and StatVar Analysis above to identify specific issues:

#### Cross-Reference with Schema Vocab
- Compare generated properties against the property_vocabulary in the schema vocab
- Check if dimension values use proper DCIDs from the vocabulary, or if raw data strings are
  being passed through when enum DCIDs are expected
- Verify populationType matches one of the stat_var_skeletons for this domain

#### Analyze Generated StatVars
- Check the StatVar Analysis for corrupted or malformed values (broken CSV parsing, misplaced commas)
- Flag properties where raw data strings appear instead of dcid: references
- Identify dimension properties with suspiciously few unique values

#### Provide Enum Mapping Fixes
If the StatVar analysis shows raw strings on dimension properties that should use DCIDs:
- Suggest explicit Column:Value mappings instead of [DATA] passthrough
- Reference the schema_vocab property_vocabulary for valid DCID values in this domain
- Do NOT hardcode specific values — use the vocabulary as the source of truth

### Key Match Report Analysis
If the Key Match Report is provided above, use it to identify key issues:
- **UNMATCHED keys**: These PVMAP keys don't match any column header. Use the suggested correct header.
- **Unmapped columns**: These data columns aren't referenced in the PVMAP. Determine if they should be mapped:
  - Place/geo columns → MUST be mapped to observationAbout
  - Time/date columns → MUST be mapped to observationDate
  - Value/numeric columns → Should be mapped with value,[NUMBER]
  - Dimension columns → Should use COLUMN:VALUE enumeration
  - Metadata columns (source, notes) → Can be safely ignored

## 2. Interpret Processing Metrics

If processing metrics are provided above, use them to pinpoint issues:

### Coverage Analysis
- **0% coverage** (0 output rows): PVMAP keys don't match any input data. Check exact column headers.
- **< 50% coverage**: Major mapping gaps. Check which columns are unmapped using value patterns.
- **50-90% coverage**: Partial success — some mappings work but specific value types are failing.
- **Coverage 100%**: All input rows produced observations — focus on property/format/quality issues.

### Unmapped Value Pattern Interpretation
These patterns reveal which input columns aren't being mapped:
- **`state_code`** pattern (e.g., 'AL', 'CA', 'TX'): A state column is in the data but not mapped. Fix: Map to DCIDs using `dcid:geoId/[DATA]` with FIPS codes, or use the State FIPS column instead.
- **`place_name`** pattern (e.g., 'ALBERTVILLE CITY'): Place names can't resolve to DCIDs directly. Fix: Use FIPS code columns instead of name columns for observationAbout.
- **`year`** pattern (e.g., '2010', '2020'): A year/date column exists but isn't mapped to observationDate. Fix: Add `observationDate` mapping for the year column.
- **`fips_code`** pattern (e.g., '01', '06'): FIPS codes present but may need zero-padding. Fix: Use `dcid:geoId/[DATA]` and ensure 2-digit state or 5-digit county format.
- **`numeric_id`** pattern (e.g., '10000500879'): Long numeric IDs (NCESID, SCHID, LEAID) not mapped. Fix: Check if these ID columns should be mapped or excluded.
- **`enum`** pattern: Categorical values not mapped. Fix: Add explicit PVMAP rows for each categorical value, or map the column header.
- **`numeric`** pattern: Numeric values not captured. Fix: Check if a value column needs `[NUMBER]` mapping.

### Error Type Priorities
- **pvmap dropped undefined property**: Keys in PVMAP don't match data columns (most common)
- **unresolved place**: observationAbout values can't be resolved as DC places
- **missing property**: Required properties (observationAbout, observationDate, value) not mapped
- **duplicate statvars**: Multiple PVMAP rows generating identical StatVars

### StatVar Generation Analysis
- **Low unique StatVar count** with many observations: Good — compact schema.
- **Low unique StatVar count** with few observations: Bad — dimension columns not creating distinct variables.
- **High unique StatVar count**: Check if over-fragmentation of dimensions.

### Warning Signals
- **Unresolved places**: Switch from names to FIPS/DCID codes for observationAbout.
- **Missing place observations**: Check observationAbout mapping completeness.
- **Spell check errors**: Generated StatVar DCIDs may have typos.

## 3. Provide Specific Fixes

Be CONCRETE and SPECIFIC:

**Instead of:** "Fix the key mapping"
**Say:** "Change key 'year' to 'Year' to match the exact column header in the data"

**Instead of:** "Add observationAbout mapping"
**Say:** "Add a mapping for the 'State FIPS' column: key='State FIPS', property='observationAbout', value='dcid:geoId/[DATA]'"

## 4. Pattern Detection

Note if the error is SYSTEMATIC:
- All place mappings using wrong column
- All DCID values missing prefix
- Format detection wrong (treating pre-formatted as raw or vice versa)

---

# OUTPUT FORMAT

Provide your analysis in this structure:

1. **Root Cause**: What specific issue caused the failure or low quality

2. **Affected Rows**: Which PVMAP rows have the problem

3. **High-Impact Fixes** (prioritized list of 3-5 specific changes):
   - Fix 1: [Specific change with exact values]
   - Fix 2: [Specific change with exact values]
   - Fix 3: [Specific change with exact values]

4. **Pattern Issues**: Any systematic problems affecting multiple rows

5. **Corrected Example**: Show what the fixed row(s) should look like

6. **Rows to PRESERVE**: Identify which existing PVMAP rows are correct and should NOT be changed

Keep your response focused and actionable. The generator will read this feedback directly."""


def create_feedback_agent(
    model: str = "gemini-2.5-flash",
    name: str = "FeedbackAgent",
) -> LlmAgent:
    """
    Create unified feedback agent for error/quality analysis between retry attempts.

    This agent analyzes both validation failures and quality issues, generating
    actionable feedback that gets injected into the next generation attempt.

    Args:
        model: Gemini model to use (default: gemini-2.5-flash)
        name: Agent name (default: FeedbackAgent)

    Returns:
        Configured LlmAgent for error/quality analysis

    State Inputs (read via instruction templating):
        - feedback_mode: str - "VALIDATION FAILED", "QUALITY LOW", or "PV ACCURACY LOW"
        - validation_error: str - Error message from validation
        - pvmap_csv: str - Generated PVMAP CSV that failed
        - sampled_data: str - Original sampled data for reference
        - structure_warnings: str - Structure validation warnings
        - mcp_resolved_context: str - MCP error resolution context
        - quality_score: float - Heuristic quality score
        - quality_metrics: str - Formatted quality metrics
        - quality_diff_summary: str - Quality issues summary
        - gt_score_section: str - Ground truth accuracy section
        - validation_counter_summary: str - Counter summary from stat_var_processor
        - schema_category: str - Selected schema category (Health, Economy, etc.)
        - schema_vocab_content: str - Compressed schema vocabulary for domain
        - skeleton_summary: str - Column classification from sampling analysis
        - validation_statvar_analysis: str - StatVar analysis from MCF output

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
